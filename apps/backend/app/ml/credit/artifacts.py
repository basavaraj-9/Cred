from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import joblib  # type: ignore[import-untyped]


class ArtifactError(RuntimeError):
    pass


def artifact_path(storage_root: Path, version: str) -> Path:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", version):
        raise ValueError("Model version contains unsupported characters")
    return storage_root / "models" / "credit" / version / "pipeline.joblib"


def save_artifact(
    storage_root: Path, version: str, bundle: dict[str, object], metadata: dict[str, object]
) -> tuple[str, str]:
    path = artifact_path(storage_root, version)
    if path.exists():
        raise ValueError(f"Credit model artifact version already exists: {version}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    joblib.dump(bundle, temporary)
    digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
    os.replace(temporary, path)
    metadata = {**metadata, "artifact_sha256": digest}
    (path.parent / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
    )
    return f"local://models/credit/{version}/pipeline.joblib", digest


def load_verified_artifact(storage_root: Path, uri: str, expected_hash: str) -> dict[str, Any]:
    prefix = "local://models/credit/"
    if not uri.startswith(prefix):
        raise ArtifactError("MODEL_METADATA_MISMATCH")
    path = (storage_root / uri.removeprefix("local://")).resolve()
    if not path.is_relative_to(storage_root.resolve()) or not path.is_file():
        raise ArtifactError("MODEL_ARTIFACT_UNAVAILABLE")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_hash:
        raise ArtifactError("MODEL_ARTIFACT_INTEGRITY_FAILED")
    bundle = joblib.load(path)
    if not isinstance(bundle, dict) or "model" not in bundle or "feature_names" not in bundle:
        raise ArtifactError("MODEL_METADATA_MISMATCH")
    return bundle
