import shutil
import subprocess
from typing import Protocol

from fastapi import Request

from app.core.config import Settings


class OCRProvider(Protocol):
    def available(self) -> bool: ...

    def extract_text(self, image_png: bytes) -> str: ...


class OCRFailure(Exception):
    pass


class TesseractOCR:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def available(self) -> bool:
        return self.settings.ocr_enabled and shutil.which("tesseract") is not None

    def extract_text(self, image_png: bytes) -> str:
        executable = shutil.which("tesseract")
        if not self.settings.ocr_enabled or executable is None:
            raise OCRFailure("OCR provider is unavailable")
        try:
            result = subprocess.run(
                [executable, "stdin", "stdout", "-l", self.settings.ocr_language],
                input=image_png,
                capture_output=True,
                timeout=self.settings.ocr_timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise OCRFailure("OCR execution failed") from exc
        if result.returncode != 0:
            raise OCRFailure("OCR provider returned an error")
        return result.stdout.decode("utf-8", errors="replace")


def get_ocr_provider(request: Request) -> OCRProvider:
    return TesseractOCR(request.app.state.settings)


def ocr_state(settings: Settings) -> str:
    if not settings.ocr_enabled:
        return "disabled"
    return "available" if TesseractOCR(settings).available() else "unavailable"
