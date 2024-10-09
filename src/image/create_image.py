import os
from src.config.config_models import ImageConfig
from src.logger.logger import setup_logger
from src.utils.response import Response
from pathlib import Path

logger = setup_logger(logger_name=__name__, log_file="logs/observice_log.log")

# logger.warn(f"Capture image: Warning: Wrong image type. '{image_type}' is not a valid format. Using jpeg instead.")


def create_image(image_config: ImageConfig, image_name: str) -> tuple[Response, Path]:
    # conflict --scale not working properly
    # command = f"fswebcam {image_path}/{image_name} --scale {str(img_data['scale']['width'])}x{str(img_data['scale']['height'])} --{image_type}"
    #
    img_path = Path(image_config.images_dir / (image_name + "." + image_config.type))
    command = f"fswebcam --{image_config.type} {image_config.quality} -S 2 --save {img_path}"

    # Execute command with os.system
    try:
        os.system(command)
        return Response(success=True, message="Took picture!"), img_path
    except Exception as e:
        return Response(success=False, message="Error capturing image. Please ensure that fswebcam is installed."), img_path
