"""Safe operator readiness command; configuration values and exceptions are never printed."""

import json

from app.core.config import get_settings
from app.runtime.health import dependency_status


def main() -> None:
    try:
        states = dependency_status(get_settings())
    except Exception:
        print(json.dumps({"status": "NOT_READY", "configuration": "INVALID"}))
        raise SystemExit(1) from None
    failed = "NOT_READY" in states.values()
    print(
        json.dumps(
            {
                "status": "NOT_READY"
                if failed
                else "WARN"
                if "WARN" in states.values()
                else "READY",
                "dependencies": states,
            }
        )
    )
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
