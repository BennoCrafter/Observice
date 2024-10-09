from src.config.config_models import ImageConfig
from src.image.image import Image
from src.image.create_image import create_image
from src.utils.get_current_timestamp import get_current_timestamp
from src.utils.response import Response
from src.image.image_queue import ImageQueue

from pathlib import Path


class ImageManagement:
    def __init__(self, image_config: ImageConfig) -> None:
        self.image_queue: ImageQueue = ImageQueue(max_queue_length=10)
        self.image_config: ImageConfig = image_config
        self.load_existing_images()

    def load_existing_images(self):
        """Load existing image in images library"""
        for file in self.image_config.images_dir.iterdir():
            if file.is_file() and (file.suffix.lower() == f'.{self.image_config.type}'):
                self.image_queue.add(Image(file))

    def create_new_image(self) -> Response:
        image_creation_resp, path = create_image(image_config=self.image_config, image_name=get_current_timestamp())

        if not image_creation_resp.is_success():
            return image_creation_resp

        self.image_queue.add(Image(source_path=path))

        return Response(success=True)

    def get_latest_image(self) -> Image:
        return self.image_queue.get_latest_image()
