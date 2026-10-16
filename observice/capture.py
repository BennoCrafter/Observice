import platform

import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstRtspServer", "1.0")
from gi.repository import Gst, GstRtspServer  # noqa: E402

from observice.config import CameraConfig  # noqa: E402

Gst.init(None)

# H.264 encoding
BITRATE = 2000  # kbit/s
KEY_INT_MAX = 30  # keyframe interval
SPEED_PRESET = "ultrafast"  # fastest encoding, lowest CPU, largest bitrate
TUNE = "zerolatency"  # minimize latency for live streaming

# RTP
CONFIG_INTERVAL = 1
RTP_PAYLOAD_TYPE = 96


def _source_clause(camera: CameraConfig) -> str:
    system = platform.system()
    if system == "Darwin":
        return "avfvideosrc device-index=0"
    if system == "Linux":
        return f"v4l2src device={camera.device or '/dev/video0'}"
    raise RuntimeError(f"Unsupported platform: {system}")


def _encoder_clause() -> str:
    # Raspberry Pi (up to 4) has a hardware H.264 encoder; software x264 is far too slow there.
    if Gst.ElementFactory.find("v4l2h264enc"):
        return (
            "videoconvert ! video/x-raw,format=I420 ! "
            f'v4l2h264enc extra-controls="controls,video_bitrate={BITRATE * 1000},h264_i_frame_period={KEY_INT_MAX}" ! '
            "video/x-h264,level=(string)4 ! h264parse"
        )
    return f"videoconvert ! x264enc tune={TUNE} bitrate={BITRATE} speed-preset={SPEED_PRESET} key-int-max={KEY_INT_MAX}"


def build_pipeline(camera: CameraConfig) -> str:
    size = f"width={camera.width},height={camera.height},framerate={camera.framerate}/1"
    # Accept raw or MJPEG: USB webcams often only reach higher resolutions/fps as MJPEG.
    return (
        f"( {_source_clause(camera)} ! video/x-raw,{size};image/jpeg,{size} ! decodebin ! "
        f"{_encoder_clause()} ! "
        f"rtph264pay config-interval={CONFIG_INTERVAL} name=pay0 pt={RTP_PAYLOAD_TYPE} )"
    )


class RTSPServer:
    """Serves the camera as an RTSP stream at rtsp://<host>:<port>/cam.

    Must be attached to a running GLib main loop (see observice/main.py).
    """

    def __init__(self, camera: CameraConfig):
        self.port = camera.rtsp_port
        self.server = GstRtspServer.RTSPServer()
        self.server.set_service(str(camera.rtsp_port))

        factory = GstRtspServer.RTSPMediaFactory()
        factory.set_launch(build_pipeline(camera))
        factory.set_shared(True)

        self.server.get_mount_points().add_factory("/cam", factory)
        self.server.attach(None)
