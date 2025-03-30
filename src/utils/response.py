class Response:
    def __init__(self, success: bool = True, message: str = "") -> None:
        self.success = success
        self.message = message

    def is_success(self) -> bool:
        return self.success

    def is_error(self) -> bool:
        return not self.success

    def __str__(self) -> str:
        msg_string = (
            f"Message: {self.message}"
            if self.success
            else f"Error Message: {self.message}"
        )
        return f"Sucess: {self.success}, {msg_string}"


# Testing
if __name__ == "__main__":
    resp = Response(True, "Worked!")
    resp2 = Response(False, "Oh no!")

    print(resp)
    print(resp2)
