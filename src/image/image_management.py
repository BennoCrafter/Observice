from src.config.config_models import ImageConfig
from src.image.image import Image
from src.image.create_image import create_image
from src.utils.get_current_timestamp import get_current_timestamp
from src.utils.response import Response
from src.image.image_queue import ImageQueue
from src.decorators.singleton import singleton


@singleton
class ImageManagement:
    def __init__(self, image_config: ImageConfig | None = None) -> None:
        if hasattr(self, '_initialized'):
            return

        self._initialized = True

        self.image_queue: ImageQueue = ImageQueue(max_queue_length=10)

        if image_config is None:
              raise ValueError("image_config cannot be None")
        self.image_config: ImageConfig = image_config
        self.load_existing_images()

    def load_existing_images(self):
        """Load existing image in images library"""
        for file in self.image_config.images_dir.iterdir():
            if file.is_file() and (file.suffix.lower() == f'.{self.image_config.type}'):
                self.image_queue.add(Image(file))

    async def create_new_image(self) -> tuple[Response, Image | None]:
        image_creation_resp, path = await create_image(image_config=self.image_config, image_name=get_current_timestamp())

        if not image_creation_resp.is_success():
            return image_creation_resp, None

        i = Image(source_path=path)
        self.image_queue.add(i)

        return Response(success=True), i

    def get_latest_image(self) -> Image:
        return self.image_queue.get_latest_image()
