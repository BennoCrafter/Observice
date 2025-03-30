from typing import Optional


class Task:
    """Base class for all tasks."""

    def __init__(self, run_every: int):
        self.run_every = run_every  # Run every X frames

    async def run(self, frame: Optional[int]): ...
