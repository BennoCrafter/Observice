import asyncio
from typing import Optional

from src.change_detector.image_comparator import ImageComparator
from src.config import CONFIG
from src.image.image_management import ImageManagement
from src.image_sender.image_sender import ImageSender
from src.logger.logger import setup_logger
from src.task.task import Task
from src.task.task_result import TaskResult

logger = setup_logger()

class ChangeDetectorTask(Task):
    def __init__(self, image_sender: ImageSender):
        super().__init__(run_every=CONFIG.change_detector.refresh_rate)
        self.image_sender = image_sender

        self.ic = ImageComparator()
        self.im = ImageManagement()

    async def run(self, frame: Optional[int]):
        ic = ImageComparator()
        webhook = CONFIG.discord.webhook_url

        prev_image = self.im.get_latest_image()
        response, image = await self.im.create_new_image()

        if response.is_error() or image is None:
            logger.error(f"Could not take image for change detector! {response.message}")
            return

        # similarity = ic.similarity(prev_image.source_path, image.source_path)
        if prev_image is None:
            logger.info("No previous image found. Sending new image...")
            await self.image_sender.send_image(image.source_path, webhook=webhook)
            return

        changed = ic.changed(prev_image.source_path, image.source_path)

        # logger.debug(f"Took image for change detector. Similarity: {similarity}")
        if changed:
            logger.info("Detected a change! Sending image...")
            await self.image_sender.send_image(image.source_path, webhook=webhook)
