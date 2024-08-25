from src.image.image import Image
from src.image.create_image import create_image
from src.utils.get_current_timestamp import get_current_timestamp
from src.utils.response import Response

class ImageManagement:
    def __init__(self, image_config) -> None:
        self.max_queue_length: int = 10
        self.image_queue: list[Image] = []
        self.image_config = image_config

    def create_new_image(self) -> Response:
        timestamp = get_current_timestamp()
        path = self.image_config["imagesDir"] + "/" + timestamp + "." + self.image_config['type']
        image_creation_resp = create_image(images_dir=self.image_config['imagesDir'], image_name=timestamp, image_type=self.image_config['type'], quality=self.image_config['quality'])

        if not image_creation_resp.is_success():
            return image_creation_resp

        self.image_queue.append(Image(source_path=path))
        self.manage_queue()

        return Response(success=True)

    def manage_queue(self):
        # If the queue exceeds max_queue_length, remove excess images and perform cleanup
        while len(self.image_queue) > self.max_queue_length:
            image_to_remove = self.image_queue.pop(0)  # Remove the oldest image
            image_to_remove.delete_image()

    def image_queue_length_reached(self) -> bool:
        return len(self.image_queue) >= self.max_queue_length

    def get_latest_image(self) -> Image:
        return self.image_queue[-1]
