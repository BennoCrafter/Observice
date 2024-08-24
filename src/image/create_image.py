import os
from src.utils.response import Response


valid_image_formats = ["jpeg", "png"]


def create_image(images_dir: str, image_name: str, image_type: str, quality: str) -> Response:
    # conflict --scale causes conflics
    # command = f"fswebcam {image_path}/{image_name} --scale {str(img_data['scale']['width'])}x{str(img_data['scale']['height'])} --{image_type}"

    if image_type not in valid_image_formats:
        print(f"Capture image: Warning: Wrong image type. '{image_type}' is not a valid format. Using jpeg instead.")
        image_type = "jpeg"

    command = f"fswebcam --{image_type} {quality} -S 2 --save {images_dir}/{image_name}.{image_type}"


    # Execute the command using os.system()
    try:
        os.system(command)
        return Response(success=True)
    except Exception as e:
        return Response(success=False, message="Error capturing image. Please ensure that fswebcam is installed.")
