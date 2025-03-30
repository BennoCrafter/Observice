import asyncio
from pathlib import Path
import cv2
import platform

from src.config.models.image_config import ImageConfig
from src.logger.logger import setup_logger
from src.utils.response import Response

logger = setup_logger()


class ImageCaptureProvider:
    async def create_image(
        self, image_config: ImageConfig, image_name: str
    ) -> tuple[Response, Path]: ...


class ImageProviderFactory:
    @staticmethod
    def get_provider() -> ImageCaptureProvider:
        system = platform.system().lower()
        if system == "darwin":
            return OpenCVProvider()
        elif system == "linux":
            return FSWebcamProvider()
        else:
            return OpenCVProvider()


class OpenCVProvider(ImageCaptureProvider):
    async def create_image(
        self, image_config: ImageConfig, image_name: str
    ) -> tuple[Response, Path]:
        img_path = Path(
            image_config.images_dir / (image_name + "." + image_config.type)
        )

        try:
            cap = cv2.VideoCapture(0)
            ret, frame = cap.read()
            cap.release()

            if ret:
                cv2.imwrite(str(img_path), frame)
                return Response(success=True, message="Took picture!"), img_path
            else:
                return Response(
                    success=False, message="Failed to capture image with OpenCV"
                ), img_path

        except Exception as e:
            return Response(
                success=False,
                message=f"Error capturing image with OpenCV. ({e})",
            ), img_path


class FSWebcamProvider(ImageCaptureProvider):
    async def create_image(
        self, image_config: ImageConfig, image_name: str
    ) -> tuple[Response, Path]:
        img_path = Path(
            image_config.images_dir / (image_name + "." + image_config.type)
        )

        command = f"fswebcam --{image_config.type} {image_config.quality} -S 2 --save {img_path}"

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return Response(success=True, message="Took picture!"), img_path
            else:
                error_message = stderr.decode().strip() if stderr else "Unknown error"
                return Response(
                    success=False, message=f"Error capturing image: {error_message}"
                ), img_path

        except Exception as e:
            return Response(
                success=False,
                message=f"Error capturing image. Please ensure that fswebcam is installed. ({e})",
            ), img_path
