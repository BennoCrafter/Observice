import os

class Image:
    def __init__(self, source_path: str) -> None:
        self.source_path: str = source_path

    def delete_image(self) -> None:
        os.remove(self.source_path)
