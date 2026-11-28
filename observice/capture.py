import logging
import platform
import threading
from collections import deque
from pathlib import Path
from typing import Callable

import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstRtspServer", "1.0")
from gi.repository import Gst, GstRtspServer  # noqa: E402

import numpy as np  # noqa: E402

from observice.config import CameraConfig  # noqa: E402

Gst.init(None)

logger = logging.getLogger("observice")

# H.264 encoding
BITRATE = 2000  # kbit/s
KEY_INT_MAX = 30  # keyframe interval; clips and new RTSP clients start on a keyframe
SPEED_PRESET = "ultrafast"  # fastest encoding, lowest CPU, largest bitrate
TUNE = "zerolatency"  # minimize latency for live streaming

# RTP
CONFIG_INTERVAL = 1
RTP_PAYLOAD_TYPE = 96

# Change detection works on small grayscale frames: cheap on a Pi 3, plenty for "did something move".
DETECT_WIDTH = 320
DETECT_FPS = 2

H264_CAPS = "video/x-h264,stream-format=byte-stream,alignment=au"
FLIP_METHODS = {90: "clockwise", 180: "rotate-180", 270: "counterclockwise"}


def camera_device(camera: CameraConfig) -> str:
    return camera.device or "/dev/video0"


def _source_clause(camera: CameraConfig) -> str:
    system = platform.system()
    if system == "Darwin":
        return "avfvideosrc device-index=0"
    if system == "Linux":
        return f"v4l2src device={camera_device(camera)}"
    raise RuntimeError(f"Unsupported platform: {system}")


def _encoder_clause() -> str:
    # Raspberry Pi (up to 4) has a hardware H.264 encoder; software x264 is far too slow there.
    if Gst.ElementFactory.find("v4l2h264enc"):
        return (
            "videoconvert ! video/x-raw,format=I420 ! "
            f'v4l2h264enc extra-controls="controls,video_bitrate={BITRATE * 1000},h264_i_frame_period={KEY_INT_MAX}" ! '
            "video/x-h264,level=(string)4"
        )
    return f"videoconvert ! x264enc tune={TUNE} bitrate={BITRATE} speed-preset={SPEED_PRESET} key-int-max={KEY_INT_MAX}"


def _jpeg_clause(quality: int) -> str:
    if Gst.ElementFactory.find("v4l2jpegenc"):  # Pi hardware JPEG encoder
        return f'v4l2jpegenc extra-controls="c,compression_quality={quality}"'
    return f"jpegenc quality={quality}"


def _flip_clause(camera: CameraConfig) -> str:
    # Only added when needed: rotating 720p in software costs real CPU on a Pi 3.
    clause = ""
    if camera.rotation in FLIP_METHODS:
        clause += f"videoflip method={FLIP_METHODS[camera.rotation]} ! "
    if camera.mirror:
        clause += "videoflip method=horizontal-flip ! "
    return clause


def build_pipeline(camera: CameraConfig) -> str:
    size = f"width={camera.width},height={camera.height},framerate={camera.framerate}/1"
    # Accept raw or MJPEG: USB webcams often only reach higher resolutions/fps as MJPEG.
    # One tee feeds the H.264 stream (RTSP + clips), change detection and snapshots.
    return (
        f"{_source_clause(camera)} ! video/x-raw,{size};image/jpeg,{size} ! decodebin ! {_flip_clause(camera)}"
        "tee name=t "
        f"t. ! queue ! {_encoder_clause()} ! h264parse config-interval=-1 ! {H264_CAPS} ! "
        "appsink name=h264 emit-signals=true sync=false "
        f"t. ! queue leaky=downstream max-size-buffers=1 ! videorate drop-only=true max-rate={DETECT_FPS} ! "
        f"videoscale ! videoconvert ! video/x-raw,format=GRAY8,width={DETECT_WIDTH},pixel-aspect-ratio=1/1 ! "
        "appsink name=detect emit-signals=true sync=false max-buffers=1 drop=true "
        f"t. ! queue leaky=downstream max-size-buffers=1 ! videorate drop-only=true max-rate={DETECT_FPS} ! "
        f"videoconvert ! {_jpeg_clause(85)} ! appsink name=snapshot emit-signals=true sync=false max-buffers=1 drop=true"
    )


def _copy_untimed(buffer: Gst.Buffer) -> Gst.Buffer:
    # A new buffer sharing the data, without timestamps. (Buffer.copy() from Python returns the same
    # buffer, so changing its timestamps would change them for the clip recorder too.)
    return buffer.copy_region(Gst.BufferCopyFlags.FLAGS | Gst.BufferCopyFlags.MEMORY, 0, buffer.get_size())


class RTSPServer:
    """Serves the H.264 stream at rtsp://<host>:<port>/cam.

    Fed by the capture pipeline instead of opening the camera itself, so the camera
    keeps running for detection and recording whether or not anyone is watching.
    Must be attached to a running GLib main loop (see observice/main.py).
    """

    def __init__(self, port: int):
        self.port = port
        self.sources: list = []
        self.server = GstRtspServer.RTSPServer()
        self.server.set_service(str(port))
        factory = GstRtspServer.RTSPMediaFactory()
        factory.set_launch(
            f"( appsrc name=src is-live=true format=time do-timestamp=true caps={H264_CAPS} ! "
            f"h264parse ! rtph264pay config-interval={CONFIG_INTERVAL} name=pay0 pt={RTP_PAYLOAD_TYPE} )"
        )
        factory.set_shared(True)
        factory.connect("media-configure", self._on_media_configure)
        self.server.get_mount_points().add_factory("/cam", factory)
        self.server.attach(None)

    def _on_media_configure(self, factory, media) -> None:
        src = media.get_element().get_by_name("src")
        self.sources.append(src)
        media.connect("unprepared", lambda *_: self.sources.remove(src))

    def push(self, buffer: Gst.Buffer) -> None:
        for src in list(self.sources):
            src.emit("push-buffer", _copy_untimed(buffer))


class ClipRecorder:
    """Keeps the last few seconds of H.264 and writes clips (pre-roll + live) to MP4 without re-encoding."""

    def __init__(self, pre_roll_seconds: int):
        self.pre_roll_ns = pre_roll_seconds * Gst.SECOND
        self.gops: deque[list[Gst.Buffer]] = deque()  # each starts with a keyframe
        self.lock = threading.Lock()
        self.writer: Gst.Pipeline | None = None
        self.base_pts = 0

    def push(self, buffer: Gst.Buffer) -> None:
        keyframe = not buffer.has_flags(Gst.BufferFlags.DELTA_UNIT)
        with self.lock:
            if keyframe:
                self.gops.append([buffer])
                # Drop the oldest GOP once the next one alone still covers the pre-roll.
                cutoff = buffer.pts - self.pre_roll_ns
                while len(self.gops) > 1 and self.gops[1][0].pts <= cutoff:
                    self.gops.popleft()
            elif self.gops:
                self.gops[-1].append(buffer)
            if self.writer:
                self._write(buffer)

    def start(self, path: Path) -> None:
        with self.lock:
            if self.writer or not self.gops:
                return
            self.path = path
            self.writer = Gst.parse_launch(
                f"appsrc name=src format=time caps={H264_CAPS} ! h264parse ! mp4mux faststart=true ! "
                f"filesink location={path.with_suffix('.mp4.part')}"
            )
            self.writer.set_state(Gst.State.PLAYING)
            self.base_pts = self.gops[0][0].pts
            for gop in self.gops:
                for buffer in gop:
                    self._write(buffer)

    def _write(self, buffer: Gst.Buffer) -> None:
        copy = _copy_untimed(buffer)
        copy.pts = copy.dts = buffer.pts - self.base_pts
        self.writer.get_by_name("src").emit("push-buffer", copy)

    def stop(self) -> Callable[[], bool]:
        """Stops feeding the clip right away, so the next one can start at once.

        Returns a blocking finish() that completes the MP4 and returns True if it was saved.
        """
        with self.lock:
            writer, path, self.writer = self.writer, getattr(self, "path", None), None

        def finish() -> bool:
            if not writer:
                return False
            writer.get_by_name("src").emit("end-of-stream")
            msg = writer.get_bus().timed_pop_filtered(10 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR)
            writer.set_state(Gst.State.NULL)
            part = path.with_suffix(".mp4.part")
            if msg is None or msg.type == Gst.MessageType.ERROR:
                logger.error("Could not write clip %s: %s", path.name, msg.parse_error()[0].message if msg else "timeout")
                part.unlink(missing_ok=True)
                return False
            part.replace(path.with_suffix(".mp4"))
            return True

        return finish


class Camera:
    """The one capture pipeline: feeds RTSP, the clip recorder, change detection and snapshots."""

    def __init__(self, camera: CameraConfig, pre_roll_seconds: int, on_frame: Callable[[np.ndarray], None]):
        self.rtsp = RTSPServer(camera.rtsp_port)
        self.recorder = ClipRecorder(pre_roll_seconds)
        self.on_frame = on_frame
        self.latest_jpeg: bytes | None = None
        self.pipeline = Gst.parse_launch(build_pipeline(camera))
        self.pipeline.get_by_name("h264").connect("new-sample", self._on_h264)
        self.pipeline.get_by_name("detect").connect("new-sample", self._on_detect)
        self.pipeline.get_by_name("snapshot").connect("new-sample", self._on_snapshot)

    def start(self) -> None:
        self.pipeline.set_state(Gst.State.PLAYING)

    def stop(self) -> None:
        self.pipeline.set_state(Gst.State.NULL)

    def _on_h264(self, sink) -> Gst.FlowReturn:
        buffer = sink.emit("pull-sample").get_buffer()
        self.rtsp.push(buffer)
        self.recorder.push(buffer)
        return Gst.FlowReturn.OK

    def _on_detect(self, sink) -> Gst.FlowReturn:
        sample = sink.emit("pull-sample")
        caps = sample.get_caps().get_structure(0)
        width, height = caps.get_value("width"), caps.get_value("height")
        buffer = sample.get_buffer()
        data = buffer.extract_dup(0, buffer.get_size())
        stride = len(data) // height  # GStreamer pads rows to 4 bytes
        frame = np.frombuffer(data, np.uint8).reshape(height, stride)[:, :width]
        self.on_frame(frame)
        return Gst.FlowReturn.OK

    def _on_snapshot(self, sink) -> Gst.FlowReturn:
        buffer = sink.emit("pull-sample").get_buffer()
        self.latest_jpeg = buffer.extract_dup(0, buffer.get_size())
        return Gst.FlowReturn.OK
