import schedule
import time
import subprocess
from pathlib import Path
import asyncio

from src.config.models.image_config import ImageConfig
from src.config import CONFIG
from src.image.create_image import create_image
from src.threads_manager import ThreadsManager
from src.image.image_management import ImageManagement
from src.detect_change import change_detector_loop
from src.image_receiver.discord_image_receiver import DiscordImageReceiver
from src.image_sender.discord_image_sender import DiscordImageSender
from src.logger.logger import setup_logger

logger = setup_logger()

def restart():
    subprocess.call(["sudo", "reboot"])

def auto_restarting():
    schedule.every().day.at("04:00").do(restart)

    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

async def create_on_startup_image():
    logger.info("Creating startup image")

    p = Path("temp")
    p.mkdir(exist_ok=True)

    image_config = ImageConfig(images_dir=Path("temp"), quality="100", type="jpeg")
    resp, temp_img_path = await create_image(image_config=image_config, image_name="temp_img")
    if not resp.is_success():
        logger.error(f"Could'nt create image for startup: {resp.message}")
        return

    time.sleep(3)
    temp_img_path.unlink()


if __name__ == '__main__':
    asyncio.run(create_on_startup_image())

    image_management = ImageManagement(image_config=CONFIG.image_config)

    threads_manager = ThreadsManager()
    threads_manager.add_new_thread(target=auto_restarting, name="Auto restarting at 4 am.")
    threads_manager.add_new_thread(target=change_detector_loop, kwargs={"image_sender": DiscordImageSender()}, name="Change detector")
    threads_manager.add_new_thread(target=DiscordImageReceiver(image_sender = DiscordImageSender()).loop, name="Discord image receiver")

    threads_manager.start_threads()
