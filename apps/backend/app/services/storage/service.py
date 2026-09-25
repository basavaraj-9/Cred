from fastapi import Request

from app.services.storage.base import StorageBackend
from app.services.storage.local import LocalStorage


def get_storage(request: Request) -> StorageBackend:
    return LocalStorage(request.app.state.settings.storage_root)


def check_storage(request: Request) -> str:
    storage = get_storage(request)
    return (
        "ready" if isinstance(storage, LocalStorage) and storage.ensure_ready() else "unavailable"
    )
