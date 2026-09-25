from __future__ import annotations

# ruff: noqa: E501
import time
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.services.external_research.security import (
    MAX_FETCH_BYTES,
    validate_content,
    validate_public_url,
)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: object, fp: object, code: int, msg: str, headers: object, newurl: str
    ) -> None:
        return None


class SafeHttpFetcher:
    """Bounded fetch primitive for a configured provider; it is not a search engine."""

    def __init__(
        self, timeout_seconds: float = 8, retries: int = 1, backoff_seconds: float = 0.2
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.backoff_seconds = backoff_seconds

    def fetch(self, url: str) -> tuple[bytes, str]:
        safe_url = validate_public_url(url)
        opener = build_opener(_NoRedirect())
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with opener.open(
                    Request(safe_url, headers={"User-Agent": "CompanyIntelligence/1.0"}),
                    timeout=self.timeout_seconds,
                ) as response:
                    content_type = response.headers.get_content_type()
                    declared = int(response.headers.get("Content-Length", "0") or 0)
                    validate_content(content_type, declared)
                    data = response.read(MAX_FETCH_BYTES + 1)
                    validate_content(content_type, len(data))
                    return data, content_type
            except (OSError, URLError, ValueError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(self.backoff_seconds * (attempt + 1))
        raise ValueError("RESEARCH_SOURCE_FETCH_FAILED") from last_error
