import asyncio
from pathlib import Path

from src.config.models.image_config import ImageConfig
from src.logger.logger import setup_logger
from src.utils.response import Response

logger = setup_logger()

# logger.warn(f"Capture image: Warning: Wrong image type. '{image_type}' is not a valid format. Using jpeg instead.")


async def create_image(image_config: ImageConfig, image_name: str) -> tuple[Response, Path]:
    img_path = Path(image_config.images_dir / (image_name + "." + image_config.type))

    # Build the command for fswebcamw
    command = f"fswebcam --{image_config.type} {image_config.quality} -S 2 --save {img_path}"
    command = f"imagesnap -w 2 {img_path}"
    try:
        # Run the command asynchronously and wait for it to finish
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Wait for the command to complete and get the output
        stdout, stderr = await process.communicate()

        # Check if the process was successful
        if process.returncode == 0:
            return Response(success=True, message="Took picture!"), img_path
        else:
            # Capture and return any error message from stderr
            error_message = stderr.decode().strip() if stderr else "Unknown error"
            return Response(success=False, message=f"Error capturing image: {error_message}"), img_path

    except Exception as e:
        return Response(
            success=False,
            message=f"Error capturing image. Please ensure that fswebcam is installed. ({e})",
        ), img_path
