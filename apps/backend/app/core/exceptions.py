import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.runtime.observability import redact

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, str] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        event = None
        if "INTEGRITY" in exc.code:
            event = "ARTIFACT_INTEGRITY_FAILED"
        elif exc.code in {
            "FILE_TOO_LARGE",
            "INVALID_FILE_TYPE",
            "INVALID_MIME_TYPE",
            "INVALID_PDF_SIGNATURE",
            "EMPTY_FILE",
        }:
            event = "UPLOAD_REJECTED"
        elif exc.code == "DEPENDENCY_UNAVAILABLE":
            event = "DEPENDENCY_UNAVAILABLE"
        if event:
            from app.runtime.audit import record_failure

            principal = getattr(_request.state, "principal", None)
            await asyncio.to_thread(
                record_failure,
                _request.app.state.settings,
                event,
                getattr(_request.state, "request_id", "unknown"),
                principal.user_id if principal else None,
            )
        message = redact(
            "Request could not be completed"
            if _request.app.state.settings.controlled_environment
            else exc.message
        )
        error: dict[str, object] = {"code": exc.code, "message": message}
        if exc.details and not _request.app.state.settings.controlled_environment:
            error["details"] = redact(exc.details)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": error,
                "error_code": exc.code,
                "message": message,
                "request_id": getattr(_request.state, "request_id", None),
            },
            headers={"Retry-After": "60"} if exc.status_code == 429 else None,
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        message = "Request could not be completed"
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": "HTTP_ERROR",
                "message": message,
                "request_id": getattr(request.state, "request_id", None),
                "error": {"code": "HTTP_ERROR", "message": message},
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {"code": "validation_error", "message": "Invalid request"},
                "error_code": "VALIDATION_ERROR",
                "message": "Invalid request",
                "request_id": getattr(_request.state, "request_id", None),
            },
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled request error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {"code": "internal_error", "message": "Internal server error"},
                "error_code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "request_id": getattr(_request.state, "request_id", None),
            },
        )
