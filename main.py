import asyncio
import subprocess
import time
from pathlib import Path
from typing import Optional

import schedule

from src.config import CONFIG
from src.config.models.image_config import ImageConfig
from src.detect_change import ChangeDetectorTask
from src.image.create_image import ImageProviderFactory
from src.image.image_management import ImageManagement
from src.image_receiver.discord_image_receiver import DiscordImageReceiverTask
from src.image_sender.discord_image_sender import DiscordImageSender
from src.logger.logger import setup_logger
from src.observice import Observice
from src.task.task import Task

logger = setup_logger()


def restart():
    subprocess.call(["sudo", "reboot"])


class AutoRestartTask(Task):
    def __init__(self):
        super().__init__(30)

    async def run(self, frame: Optional[int]):
        if time.localtime().tm_hour == 4 and time.localtime().tm_min == 0:
            restart()


def auto_restarting():
    time.sleep(70)

    schedule.every().day.at("04:00").do(restart)

    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute


async def create_on_startup_image():
    logger.info("Creating startup image")

    p = Path("temp")
    p.mkdir(exist_ok=True)
    image_config = ImageConfig(images_dir=Path("temp"), quality="100", type="jpeg")
    resp, temp_img_path = await ImageProviderFactory.get_provider().create_image(
        image_config=image_config, image_name="temp_img"
    )
    if not resp.is_success():
        logger.error(f"Could not create image for startup: {resp.message}")
        return

    time.sleep(3)
    temp_img_path.unlink()


if __name__ == "__main__":
    logger.info("Starting Observice")
    asyncio.run(create_on_startup_image())

    image_management = ImageManagement(image_config=CONFIG.image)

    tasks = [
        AutoRestartTask(),
        ChangeDetectorTask(image_sender=DiscordImageSender()),
        DiscordImageReceiverTask(image_sender=DiscordImageSender()),
    ]
    observice = Observice(tasks=tasks)

    try:
        asyncio.run(observice.start())
    except KeyboardInterrupt:
        logger.info("Observice stopped")
        observice.close()
    except Exception as e:
        logger.error(f"Observice stopped with error: {e}")
        observice.close()
