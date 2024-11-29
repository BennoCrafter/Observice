import threading
import asyncio
from typing import Callable, Dict, List, Tuple

class ThreadsManager:
    def __init__(self) -> None:
        self.threads: List[threading.Thread] = []
        self.thread_metadata: Dict[threading.Thread, Tuple[Callable, Tuple, Dict]] = {}

    def add_new_thread(self, target: Callable, name: str, args: Tuple = (), kwargs: Dict = {}):
        # Wrap async functions to run them with asyncio within a thread
        if asyncio.iscoroutinefunction(target):
            wrapped_target = self._async_target_wrapper(target)
        else:
            wrapped_target = self._auto_restart(target)

        new_thread = threading.Thread(target=wrapped_target, name=name, args=args, kwargs=kwargs)
        self.threads.append(new_thread)
        self.thread_metadata[new_thread] = (target, args, kwargs)

    def start_threads(self):
        for t in self.threads:
            t.start()
        for t in self.threads:
            t.join()

    def _async_target_wrapper(self, target: Callable):
        # This method runs the async function inside a new asyncio event loop
        def wrapped_target(*args, **kwargs):
            while True:
                try:
                    print(f"Starting async thread {threading.current_thread().name}")
                    asyncio.run(target(*args, **kwargs))
                    break  # Exit the loop if the async function completes without exception
                except Exception as e:
                    print(f"Async thread {threading.current_thread().name} encountered an error: {e}. Restarting...")

        return wrapped_target

    def _auto_restart(self, target: Callable):
        # This method wraps the sync target to restart on failure
        def wrapped_target(*args, **kwargs):
            while True:
                try:
                    print(f"Starting thread {threading.current_thread().name}")
                    target(*args, **kwargs)
                    break  # Exit the loop if the thread completes without exception
                except Exception as e:
                    print(f"Thread {threading.current_thread().name} encountered an error: {e}. Restarting...")

        return wrapped_target
