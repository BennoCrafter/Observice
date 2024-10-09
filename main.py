import schedule
import time
import subprocess
from threading import Thread
from pathlib import Path

from src.config.config_models import ImageConfig
from src.image.create_image import create_image
from src.threads_manager import ThreadsManager


def restart():
    subprocess.call(["sudo", "reboot"])

def auto_restarting():
    schedule.every().day.at("04:00").do(restart)

    print("Scheduler started. The computer will restart at 4 AM daily.")

    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

def create_on_startup_image():
    image_config = ImageConfig(images_dir=Path("temp"), quality="100", type="jpeg")
    resp, temp_img_path = create_image(image_config=image_config, image_name="temp_img")
    time.sleep(3)
    temp_img_path.unlink()


if __name__ == '__main__':
    create_on_startup_image()

    threads_manager = ThreadsManager()
    threads_manager.add_new_thread(target=auto_restarting, name="Auto restarting at 4 am.")
    threads_manager.start_threads()
