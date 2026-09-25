import os
import re
import shutil
from pathlib import Path
from typing import BinaryIO

from app.core.exceptions import AppError

STORED_NAME = re.compile(r"^[0-9a-f]{32}\.pdf$")
URI_PREFIX = "local://uploads/"


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.upload_dir = self.root / "uploads"

    def ensure_ready(self) -> bool:
        try:
            self.upload_dir.mkdir(parents=True, exist_ok=True)
            return self.upload_dir.resolve().is_relative_to(self.root) and os.access(
                self.upload_dir, os.W_OK
            )
        except OSError:
            return False

    def _path_for_name(self, stored_filename: str) -> Path:
        if not STORED_NAME.fullmatch(stored_filename):
            raise AppError("INVALID_STORAGE_KEY", "Invalid storage key")
        path = self.upload_dir / stored_filename
        if not path.parent.resolve().is_relative_to(self.root):
            raise AppError("INVALID_STORAGE_KEY", "Invalid storage key")
        return path

    def _path_for_uri(self, uri: str) -> Path:
        if not uri.startswith(URI_PREFIX):
            raise AppError("INVALID_STORAGE_URI", "Invalid storage URI")
        return self._path_for_name(uri.removeprefix(URI_PREFIX))

    def save_file(self, source: BinaryIO, stored_filename: str) -> str:
        if not self.ensure_ready():
            raise AppError("STORAGE_UNAVAILABLE", "Local storage is unavailable", 503)
        path = self._path_for_name(stored_filename)
        created = False
        try:
            with path.open("xb") as destination:
                created = True
                shutil.copyfileobj(source, destination, length=1024 * 1024)
        except Exception:
            if created:
                path.unlink(missing_ok=True)
            raise
        return URI_PREFIX + stored_filename

    def delete_file(self, uri: str) -> None:
        self._path_for_uri(uri).unlink(missing_ok=True)

    def exists(self, uri: str) -> bool:
        return self._path_for_uri(uri).is_file()

    def get_file_path(self, uri: str) -> Path:
        return self._path_for_uri(uri)
