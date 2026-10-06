import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.core.config import Settings


def validate_startup(settings: Settings) -> None:
    directory = Path(__file__).parent
    for name in (
        "authorization_policy_v1.json",
        "job_retry_policy_v1.json",
        "production_runtime_policy_v1.json",
    ):
        try:
            policy = json.loads((directory / name).read_text(encoding="utf-8"))
            if not isinstance(policy, dict) or not policy.get("version"):
                raise ValueError("Invalid policy")
            if name == "production_runtime_policy_v1.json":
                for flag in (
                    "auto_credit_approval",
                    "live_stock_predictions",
                    "automated_trading",
                    "production_stock_model",
                ):
                    if policy.get(flag) is not False:
                        raise ValueError("Prohibited production capability")
        except (OSError, ValueError) as exc:
            raise RuntimeError("Runtime policy validation failed") from exc
    if settings.controlled_environment:
        try:
            settings.storage_root.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(
                dir=settings.storage_root, prefix=".startup-", suffix=".temporary"
            ) as temporary:
                temporary.write(b"storage-check")
                temporary.flush()
        except OSError:
            raise RuntimeError("Artifact storage is not writable") from None
