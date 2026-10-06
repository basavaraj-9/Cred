from __future__ import annotations

import json
import logging
import re
import threading
from collections import defaultdict
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

context: ContextVar[dict[str, str]] = ContextVar("runtime_context", default={})
SENSITIVE = re.compile(r"password|secret|token|authorization|api.key|database.url|cookie", re.I)
_secrets: set[str] = set()


def register_secrets(values: list[str]) -> None:
    _secrets.update(value for value in values if value)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if SENSITIVE.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [redact(item) for item in value]
    if not isinstance(value, str):
        return value
    for secret in sorted(_secrets, key=len, reverse=True):
        value = value.replace(secret, "[REDACTED]")
    value = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~-]+", "Bearer [REDACTED]", value)
    value = re.sub(r"(://)[^\s/@]+:[^\s/@]+@", r"\1[REDACTED]@", value)
    return re.sub(
        r"(?i)(password|secret|token|authorization|api_key|database_url|cookie)([\s'\"]*[:=][\s'\"]*)[^\s,}]+",
        r"\1\2[REDACTED]",
        value,
    )


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "service": "company-intelligence-api",
            "environment": getattr(record, "environment", "unknown"),
            "request_id": None,
            "user_id": None,
            "company_id": None,
            "job_id": None,
            "route": None,
            "duration": None,
            "status": None,
            **context.get(),
            "event": record.getMessage(),
        }
        payload.update(getattr(record, "runtime", {}))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(redact(payload), default=str)


class MetricsSink:
    """Process-local adapter; production scrapers aggregate workers independently."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.values: dict[tuple[str, str], float] = defaultdict(float)

    def add(self, name: str, value: float = 1, category: str = "all") -> None:
        # Only code-defined categories, never identifiers/URLs, are accepted.
        allowed = {
            "all",
            "success",
            "failure",
            "REPORT_360",
            "RESEARCH",
            "STOCK_DATASET",
            "STOCK_TRAIN",
            "MONITORING",
            "PARSE",
        }
        if category not in allowed:
            raise ValueError("Metric category must be bounded")
        with self.lock:
            self.values[(name, category)] += value

    def render(self) -> str:
        with self.lock:
            return (
                "\n".join(
                    f'{name}{{category="{category}"}} {value}'
                    for (name, category), value in sorted(self.values.items())
                )
                + "\n"
            )


metrics = MetricsSink()
