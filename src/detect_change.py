import asyncio

import requests
import json
from src.image.image_management import ImageManagement
from src.change_detector.image_comparator import ImageComparator
from src.logger.logger import setup_logger
from src.config.config_loader import ConfigLoader

logger = setup_logger(logger_name=__name__, log_file="logs/observice_log.log")

async def send_message_to_discord_channel(message: str, webhook_url: str):
    if not webhook_url.startswith("http"):
        print("Invalid webhook URL")
        return
    try:
        # Send POST request to the webhook URL
        response = requests.post(webhook_url, data=json.dumps({"content": message}), headers={"Content-Type": "application/json"})

        if response.status_code != 204:
            print(f"Unexpected status code: {response.status_code}")
        else:
            print("Message sent successfully!")

    except requests.exceptions.RequestException as e:
        print(f"Error sending message: {e}")

def minutes(sec):
    return sec * 60

async def change_detector_loop():
    ic = ImageComparator()
    im = ImageManagement()
    config = ConfigLoader()
    webhook = config.config["discord"]["webhook"]

    while True:
        await asyncio.sleep(10)

        prev_image = im.get_latest_image()
        response, image = im.create_new_image()

        if not response.success or image == None:
            logger.error("Could'nt take image for change detector!")
            continue

        similarity = ic.similarity(prev_image.source_path, image.source_path)
        changed = ic.changed(prev_image.source_path, image.source_path)

        logger.info(f"Took image for change detector. Similarity: {similarity}")
        if changed:
            logger.info("Detected a change! Sending image...")
            await send_message_to_discord_channel("latest", webhook)


if __name__ == "__main__":
    asyncio.run(change_detector_loop())
