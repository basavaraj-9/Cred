from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path, PureWindowsPath

from app.core.exceptions import AppError


def safe_path(root: Path, relative: str) -> Path:
    raw = Path(relative)
    if (
        raw.is_absolute()
        or PureWindowsPath(relative).is_absolute()
        or bool(PureWindowsPath(relative).drive)
        or ":" in relative
        or ".." in relative.replace("\\", "/").split("/")
    ):
        raise AppError("ARTIFACT_ACCESS_DENIED", "Invalid artifact reference", 403)
    target = (root.resolve() / raw).resolve()
    if not target.is_relative_to(root.resolve()) or target == root.resolve():
        raise AppError("ARTIFACT_ACCESS_DENIED", "Invalid artifact reference", 403)
    return target


def checked_artifact(root: Path, relative: str, digest: str) -> Path:
    target = safe_path(root, relative)
    if not target.is_file():
        raise AppError("ARTIFACT_UNAVAILABLE", "Artifact is unavailable", 404)
    with target.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != digest:
        raise AppError("INTEGRITY_ERROR", "Artifact integrity check failed", 409)
    return target


def cleanup_temporary(root: Path, retention_hours: int) -> int:
    directory = safe_path(root, ".runtime-temporary")
    if not directory.exists():
        return 0
    cutoff = (datetime.now(UTC) - timedelta(hours=retention_hours)).timestamp()
    removed = 0
    for item in directory.glob("*.temporary"):
        if (
            not item.is_symlink()
            and item.is_file()
            and item.resolve().is_relative_to(directory)
            and item.stat().st_mtime < cutoff
        ):
            item.unlink()
            removed += 1
    return removed
