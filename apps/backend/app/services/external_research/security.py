from __future__ import annotations

# ruff: noqa: E501
import ipaddress
import socket
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_KEYS = {
    "fbclid",
    "gclid",
    "ref",
    "source",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}
ALLOWED_CONTENT_TYPES = {"text/html", "text/plain", "application/pdf"}
MAX_FETCH_BYTES = 2 * 1024 * 1024


def normalize_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if scheme not in {"http", "https"} or not host:
        raise ValueError("RESEARCH_URL_SCHEME_BLOCKED")
    port = f":{parsed.port}" if parsed.port and parsed.port not in {80, 443} else ""
    query = urlencode(
        sorted((k, v) for k, v in parse_qsl(parsed.query) if k.lower() not in TRACKING_KEYS)
    )
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((scheme, host + port, path, query, ""))


def validate_public_url(value: str, *, resolve_dns: bool = True) -> str:
    canonical = normalize_url(value)
    host = urlsplit(canonical).hostname or ""
    if host in {"localhost", "metadata.google.internal"} or host.endswith((".local", ".internal")):
        raise ValueError("RESEARCH_URL_PRIVATE_HOST_BLOCKED")
    candidates: set[str] = set()
    try:
        candidates.add(str(ipaddress.ip_address(host)))
    except ValueError:
        if resolve_dns:
            candidates.update(str(item[4][0]) for item in socket.getaddrinfo(host, None))
    for raw in candidates:
        ip = ipaddress.ip_address(raw)
        if not ip.is_global:
            raise ValueError("RESEARCH_URL_PRIVATE_IP_BLOCKED")
    return canonical


def validate_content(content_type: str, size: int) -> None:
    mime = content_type.split(";", 1)[0].strip().lower()
    if mime not in ALLOWED_CONTENT_TYPES:
        raise ValueError("RESEARCH_CONTENT_TYPE_BLOCKED")
    if size > MAX_FETCH_BYTES:
        raise ValueError("RESEARCH_CONTENT_TOO_LARGE")
