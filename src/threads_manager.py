import threading
import asyncio
from typing import Callable, List, Tuple, Dict
from src.logger.logger import setup_logger

logger = setup_logger()


class ThreadsManager:
    def __init__(self) -> None:
        self.threads: List[threading.Thread] = []

    def add_new_thread(
        self, target: Callable, name: str, args: Tuple = (), kwargs: Dict = {}
    ):
        if asyncio.iscoroutinefunction(target):
            wrapped_target = self._async_target_wrapper(target)
        else:
            wrapped_target = self._auto_restart(target)

        new_thread = threading.Thread(
            target=wrapped_target, name=name, args=args, kwargs=kwargs
        )
        self.threads.append(new_thread)

    def start_threads(self):
        for t in self.threads:
            logger.info(f'Thread "{t.name}" started.')
            t.start()
        for t in self.threads:
            t.join()

    def _async_target_wrapper(self, target: Callable):
        def wrapped_target(*args, **kwargs):
            try:
                asyncio.run(target(*args, **kwargs))
            except Exception as e:
                print(f"Error in async thread {threading.current_thread().name}: {e}")

        return wrapped_target

    def _auto_restart(self, target: Callable):
        def wrapped_target(*args, **kwargs):
            while True:
                try:
                    target(*args, **kwargs)
                    break
                except Exception as e:
                    print(
                        f"Error in thread {threading.current_thread().name}: {e}. Restarting..."
                    )

        return wrapped_target
