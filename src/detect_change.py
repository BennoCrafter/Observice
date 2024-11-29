import asyncio

import requests
from src.image.image_management import ImageManagement
from src.change_detector.image_comparator import ImageComparator
from src.logger.logger import setup_logger
from src.config.config_loader import ConfigLoader
from pathlib import Path


logger = setup_logger(logger_name=__name__, log_file="logs/observice_log.log")

async def send_message_to_discord_channel(webhook_url: str, image_path: Path):
    if not webhook_url.startswith("http"):
        logger.error(f"Invalid webhook URL: {webhook_url}")
        return

    try:
        # If there's an image path provided, open the image and add it as a file
        with open(image_path, 'rb') as image_file:
            files = {
                'file': (str(image_path), image_file, 'image/jpeg')  # Change mime type based on the image format
            }
            # Send the POST request with image attached
            response = requests.post(webhook_url, files=files)

        # Check if the response was successful
        if response.status_code != 200:
            logger.error(f"Unexpected status code {response.status_code} when sending message to Discord")
        else:
            logger.info("Message sent successfully with image!")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending message to Discord: {e}")

def minutes(sec):
    return sec * 60

async def change_detector_loop():
    ic = ImageComparator()
    im = ImageManagement()
    config = ConfigLoader()
    webhook = config.config["discord"]["webhook"]

    while True:
        await asyncio.sleep(minutes(1))

        prev_image = im.get_latest_image()
        response, image = await im.create_new_image()

        if not response.success or image == None:
            logger.error("Could'nt take image for change detector!")
            continue

        similarity = ic.similarity(prev_image.source_path, image.source_path)
        changed = ic.changed(prev_image.source_path, image.source_path)

        logger.info(f"Took image for change detector. Similarity: {similarity}")
        if changed:
            logger.info("Detected a change! Sending image...")
            await send_message_to_discord_channel(webhook, image.source_path)


if __name__ == "__main__":
    asyncio.run(change_detector_loop())
