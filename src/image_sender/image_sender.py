from abc import ABC
from pathlib import Path

from src.utils.response import Response


class ImageSender(ABC):
    def __init__(self):
        pass

    async def send_image(self, image_path: Path | str, **kwargs) -> Response:
        return Response(False, "Can't use base class")
