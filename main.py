from threading import Thread
import time
from src.threads_manager import ThreadsManager
from src.discord.discord_bot import start_discord_bot

if __name__ == '__main__':
    threads_manager = ThreadsManager()
    threads_manager.add_new_thread(target=start_discord_bot, name="DiscordBot")
    threads_manager.start_threads()
