import schedule
import time
import subprocess
from pathlib import Path
import asyncio

from src.config.config_models import ImageConfig
from src.image.create_image import create_image
from src.threads_manager import ThreadsManager
from src.config.config_loader import ConfigLoader
from src.image.image_management import ImageManagement
from src.detect_change import change_detector_loop

def restart():
    subprocess.call(["sudo", "reboot"])

def auto_restarting():
    schedule.every().day.at("04:00").do(restart)

    print("Scheduler started. The computer will restart at 4 AM daily.")

    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

async def create_on_startup_image():
    p = Path("temp")
    p.mkdir(exist_ok=True)

    image_config = ImageConfig(images_dir=Path("temp"), quality="100", type="jpeg")
    resp, temp_img_path = await create_image(image_config=image_config, image_name="temp_img")
    time.sleep(3)
    temp_img_path.unlink()


if __name__ == '__main__':
    asyncio.run(create_on_startup_image())
    config = ConfigLoader()

    # temp solution only
    dict_img_config = config.config["imageConfig"]
    img_config = ImageConfig(images_dir=Path(dict_img_config["imagesDir"]) , quality=dict_img_config["quality"] , type=dict_img_config["type"])
    image_management = ImageManagement(image_config=img_config)

    threads_manager = ThreadsManager()
    threads_manager.add_new_thread(target=auto_restarting, name="Auto restarting at 4 am.")
    threads_manager.add_new_thread(target=change_detector_loop, name="Change detector")

    threads_manager.start_threads()
