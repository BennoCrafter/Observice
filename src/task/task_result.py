from typing import Optional


class TaskResult:
    """Represents the result of a task execution."""

    def __init__(self, success: bool = True, error_message: Optional[str] = None):
        self.success = success
        self.error_message = error_message
