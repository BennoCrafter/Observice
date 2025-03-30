from typing import Optional
from src.task.task import Task
import asyncio
from src.logger.logger import setup_logger

logger = setup_logger()


class Observice:
    def __init__(
        self,
        tasks: list[Task],
        loop_running: bool = True,
        frame_limit: int = 1000,
        step: int = 1,
    ) -> None:
        self.tasks = tasks
        self.frame_limit = frame_limit
        self.step = step
        self.loop_running = loop_running

        self._current_frame: int = step
        tasks_exceeds_limit, target_task = self.check_tasks_if_exceeding_limit()
        if tasks_exceeds_limit:
            if target_task is not None:
                raise ValueError(
                    f"The target tasks exceeds the limit from {self.frame_limit} ({target_task.run_every})"
                )
            else:
                raise ValueError(f"A task exceeds the limit from {self.frame_limit}")

    def check_tasks_if_exceeding_limit(self) -> tuple[bool, Optional[Task]]:
        for task in self.tasks:
            if task.run_every > self.frame_limit:
                return True, task
        return False, None

    def increase_frame(self) -> None:
        if self._current_frame == self.frame_limit:
            self._current_frame = 1
            return

        self._current_frame += self.step

    async def execute_tasks(self):
        for task in self.tasks:
            if self._current_frame % task.run_every == 0:
                try:
                    await task.run(self._current_frame)
                except Exception as e:
                    logger.error(f"Error executing task {task}: {e}")

    def get_current_frame(self) -> int:
        return self._current_frame

    async def loop(self):
        while self.loop_running:
            # print(f"\n--- Frame {self._current_frame} ---")
            await self.execute_tasks()
            self.increase_frame()
            await asyncio.sleep(1)

    async def start(self):
        await self.loop()

    def close(self):
        self.loop_running = False
