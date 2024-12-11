import asyncio

from src.change_detector.image_comparator import ImageComparator
from src.config import CONFIG
from src.image.image_management import ImageManagement
from src.image_sender.image_sender import ImageSender
from src.logger.logger import setup_logger

logger = setup_logger()


async def change_detector_loop(image_sender: ImageSender):
    ic = ImageComparator()
    im = ImageManagement()
    webhook = CONFIG.discord.webhook_url
    while True:
        await asyncio.sleep(CONFIG.change_detector.refresh_rate)

        prev_image = im.get_latest_image()
        response, image = await im.create_new_image()

        if response.is_error() or image is None:
            logger.error(f"Could'nt take image for change detector! {response.message}")
            continue

        # similarity = ic.similarity(prev_image.source_path, image.source_path)
        changed = ic.changed(prev_image.source_path, image.source_path)

        # logger.debug(f"Took image for change detector. Similarity: {similarity}")
        if changed:
            logger.info("Detected a change! Sending image...")
            await image_sender.send_image(image.source_path, webhook=webhook)
