from abc import ABC
import asyncio
from typing import Optional
from src.image_sender.image_sender import ImageSender
from src.config import CONFIG
from src.task.task import Task



class ImageReceiverTask(Task):
    def __init__(self, image_sender: ImageSender):
        super().__init__(CONFIG.image_receiver.refresh_rate)
        self.image_sender = image_sender

    def check(self) -> bool:
        ...

    async def process(self):
        ...

    async def run(self, frame: Optional[int]):
        if self.check():
            await self.process()
