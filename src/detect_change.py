import asyncio

from src.image.image_management import ImageManagement
from src.change_detector.image_comparator import ImageComparator
from src.image_sender.image_sender import ImageSender
from src.logger.logger import setup_logger
from src.config import CONFIG


logger = setup_logger()

def minutes(sec):
    return sec * 60

async def change_detector_loop(image_sender: ImageSender):
    ic = ImageComparator()
    im = ImageManagement()
    webhook = CONFIG.discord_config.webhook_url

    while True:
        await asyncio.sleep(minutes(1))

        prev_image = im.get_latest_image()
        response, image = await im.create_new_image()

        if not response.success or image == None:
            logger.error("Could'nt take image for change detector!")
            continue

        # similarity = ic.similarity(prev_image.source_path, image.source_path)
        changed = ic.changed(prev_image.source_path, image.source_path)

        # logger.debug(f"Took image for change detector. Similarity: {similarity}")
        if changed:
            logger.info("Detected a change! Sending image...")
            await image_sender.send_image(image.source_path, webhook=webhook)
