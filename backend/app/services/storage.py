"""Where uploaded files live. Local disk in development; the interface is what R2
(or S3) will implement when the app is deployed."""

import secrets
from pathlib import Path
from typing import Protocol

from app.config import get_settings


class Storage(Protocol):
    def put(self, data: bytes, *, suffix: str) -> str:
        """Store `data` and return the key to read it back with."""

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):  # keys are ours, but never trust a path
            raise ValueError(f"Bad storage key: {key}")
        return path

    def put(self, data: bytes, *, suffix: str) -> str:
        # Random names: the user's filename never touches the filesystem.
        key = f"{secrets.token_hex(16)}{suffix}"
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


def get_storage() -> Storage:
    return LocalStorage(get_settings().upload_dir)
