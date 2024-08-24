import threading
from typing import Callable, Dict, List, Tuple

class ThreadsManager:
    def __init__(self) -> None:
        self.threads: List[threading.Thread] = []
        self.thread_metadata: Dict[threading.Thread, Tuple[Callable, Tuple, Dict]] = {}

    def add_new_thread(self, target: Callable, name: str, args: Tuple = (), kwargs: Dict = {}):
        # Create a new thread with the wrapped target
        wrapped_target = self._auto_restart(target)
        new_thread = threading.Thread(target=wrapped_target, name=name, args=args, kwargs=kwargs)
        self.threads.append(new_thread)
        self.thread_metadata[new_thread] = (target, args, kwargs)

    def start_threads(self):
        for t in self.threads:
            t.start()
            t.join()

    def stop_threads(self):
        for t in self.threads:
            t.join()

    def _auto_restart(self, target: Callable):
        def wrapped_target(*args, **kwargs):
            while True:
                try:
                    print(f"Starting thread {threading.current_thread().name}")
                    target(*args, **kwargs)
                    break  # Exit the loop if the thread completes without exception
                except Exception as e:
                    print(f"Thread {threading.current_thread().name} encountered an error: {e}. Restarting...")

        return wrapped_target
