from fastapi import APIRouter, Request

from app.core.constants import SERVICE_NAME
from app.database.health import check_database
from app.schemas.system import HealthResponse
from app.services.document_intelligence.ocr import ocr_state
from app.services.storage.service import check_storage

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    database = check_database(settings.database_url)
    storage = check_storage(request)
    return HealthResponse(
        status="healthy" if database == "connected" and storage == "ready" else "degraded",
        service=SERVICE_NAME,
        version=settings.app_version,
        environment=settings.app_env,
        dependencies={"database": database, "storage": storage, "ocr": ocr_state(settings)},
    )
