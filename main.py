from threading import Thread
import time
from src.threads_manager import ThreadsManager

if __name__ == '__main__':
    threads_manager = ThreadsManager()
    threads_manager.start_threads()
