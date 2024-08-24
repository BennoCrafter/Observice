class Response:
    def __init__(self, success: bool = True, message: str = "") -> None:
        self.success = success
        self.message = message

    def is_success(self) -> bool:
        return self.success
