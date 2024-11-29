from pathlib import Path

class Image:
    def __init__(self, source_path: Path) -> None:
        self.source_path: Path = source_path

    def delete_image(self) -> None:
        self.source_path.unlink()
