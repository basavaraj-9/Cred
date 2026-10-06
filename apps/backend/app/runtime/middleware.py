from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from uuid import uuid4

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import Settings
from app.runtime.observability import context, metrics
from app.runtime.provider_safety import runtime_settings

logger = logging.getLogger(__name__)


class RuntimeMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings):
        self.app, self.settings = app, settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        incoming = headers.get(b"x-request-id", b"").decode("ascii", "ignore")
        request_id = incoming if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", incoming) else str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        token = context.set({"request_id": request_id, "environment": self.settings.app_env.value})
        settings_token = runtime_settings.set(self.settings)
        start, status, started = time.monotonic(), 500, False
        response_blocked = False

        async def safe_send(message):
            nonlocal status, started, response_blocked
            if response_blocked:
                return
            if message["type"] == "http.response.start":
                response_headers = dict(message.get("headers", []))
                if (
                    response_headers.get(b"content-type", b"").startswith(b"application/json")
                    and b"content-disposition" not in response_headers
                    and int(response_headers.get(b"content-length", b"0"))
                    > self.settings.max_json_response_bytes
                ):
                    await fail(
                        "RESPONSE_TOO_LARGE", "Narrow the query or download an artifact", 413
                    )
                    response_blocked = True
                    return
                started = True
                status = message["status"]
                security_headers = [
                    (b"x-request-id", request_id.encode()),
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
                    (b"cache-control", b"no-store"),
                ]
                if self.settings.controlled_environment and self.settings.https_deployment:
                    security_headers.append(
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                    )
                message["headers"] = list(message.get("headers", [])) + security_headers
            await send(message)

        async def fail(code: str, message: str, status_code: int):
            if code == "UPLOAD_REJECTED":
                from app.runtime.audit import record_failure

                await asyncio.to_thread(record_failure, self.settings, code, request_id, None)
            await JSONResponse(
                {
                    "error_code": code,
                    "message": message,
                    "request_id": request_id,
                    "error": {"code": code, "message": message},
                },
                status_code=status_code,
            )(scope, receive, safe_send)

        try:
            body = bytearray()
            content_type = headers.get(b"content-type", b"").decode("ascii", "ignore").lower()
            limit = (
                self.settings.max_json_bytes
                if content_type.startswith("application/json")
                else self.settings.max_request_bytes
            )
            if content_type and not content_type.startswith(
                ("application/json", "multipart/form-data")
            ):
                await fail("VALIDATION_ERROR", "Unsupported content type", 415)
                return
            try:
                async with asyncio.timeout(self.settings.request_timeout_seconds):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        body.extend(message.get("body", b""))
                        if len(body) > limit:
                            await fail("UPLOAD_REJECTED", "Request size limit exceeded", 413)
                            return
                        if not message.get("more_body", False):
                            break
            except TimeoutError:
                await fail("REQUEST_TIMEOUT", "Request body timed out", 408)
                return
            if content_type.startswith("application/json") and body:
                try:
                    json.loads(body)
                except (ValueError, UnicodeError, RecursionError):
                    await fail("VALIDATION_ERROR", "Malformed JSON", 422)
                    return
            sent = False

            async def buffered_receive():
                nonlocal sent
                if body and not sent:
                    sent = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": b"", "more_body": False}
                return await receive()

            # Large operations have durable async endpoints; this caps request delivery.
            async with asyncio.timeout(self.settings.request_timeout_seconds):
                await self.app(scope, buffered_receive, safe_send)
        except TimeoutError:
            if not started:
                await fail("REQUEST_TIMEOUT", "Request timed out; use an asynchronous job", 504)
        except Exception:
            logger.exception("request_failed")
            if started:
                raise
            await fail("INTERNAL_ERROR", "Internal server error", 500)
        finally:
            duration = time.monotonic() - start
            metrics.add("http_requests_total", category="failure" if status >= 400 else "success")
            metrics.add("http_request_duration_seconds_sum", duration)
            route = scope.get("route")
            logger.info(
                "http_request",
                extra={
                    "runtime": {
                        "user_id": str(scope["state"]["principal"].user_id)
                        if "principal" in scope["state"]
                        else None,
                        "route": getattr(route, "path", "unmatched"),
                        "status": status,
                        "duration": duration,
                    }
                },
            )
            context.reset(token)
            runtime_settings.reset(settings_token)
