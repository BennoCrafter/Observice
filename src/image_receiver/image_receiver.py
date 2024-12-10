from abc import ABC
import asyncio
from src.image_sender.image_sender import ImageSender
from src.config import CONFIG


class ImageReceiver(ABC):
    def __init__(self, image_sender: ImageSender):
        self.image_sender = image_sender

    def check(self) -> bool:
        return False

    async def process(self):
        pass

    async def loop(self):
        while True:
            if self.check():
                await self.process()
            else:
                await asyncio.sleep(CONFIG.image_receiver.refresh_rate)
