from threading import Thread
import time
from src.threads_manager import ThreadsManager
import schedule
import subprocess


def restart():
    subprocess.call(["sudo", "reboot"])

def auto_restarting():
    schedule.every().day.at("04:00").do(restart)

    print("Scheduler started. The computer will restart at 4 AM daily.")

    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == '__main__':
    threads_manager = ThreadsManager()
    threads_manager.add_new_thread(target=auto_restarting, name="Auto restarting at 4 am.")
    threads_manager.start_threads()
