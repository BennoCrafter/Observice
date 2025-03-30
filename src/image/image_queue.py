from typing import Optional
from src.image.image import Image


class ImageQueue:
    def __init__(self, images: list[Image] = [], max_queue_length: int = 10) -> None:
        self.images = images
        self.max_queue_length: int = max_queue_length

    def add(self, img: Image) -> None:
        self.images.append(img)
        self.update_queue()

    def update_queue(self) -> None:
        # If the queue exceeds max_queue_length, remove excess images and perform cleanup
        while len(self.images) > self.max_queue_length:
            image_to_remove = self.images.pop(0)
            image_to_remove.delete_image()

    def image_queue_length_reached(self) -> bool:
        return len(self.images) >= self.max_queue_length

    def get_latest_image(self) -> Optional[Image]:
        return self.images[-1] if self.images else None
