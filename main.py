from threading import Thread
import time
from src.threads_manager import ThreadsManager
from src.discord.discord_bot import start_discord_bot

def test():
    while True:
        print("Test 0")
        time.sleep(1)

def test1():
    num = 2
    while True:
        print(f"Test 1 {10/num}")
        num -= 1
        time.sleep(1)

if __name__ == '__main__':
    threads_manager = ThreadsManager()
    # threads_manager.add_new_thread(Thread(target=start_discord_bot))
    threads_manager.add_new_thread(target=test, name="Test0")
    threads_manager.add_new_thread(target=test1, name="Test1")
    threads_manager.start_threads()
