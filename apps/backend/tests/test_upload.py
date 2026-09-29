import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.session import get_db
from app.main import create_app
from app.models import AnalysisJob, AuditLog, Company, Document
from app.models.enums import AnalysisJobStatus, DocumentStatus
from app.services import ingestion
from app.services.storage.local import LocalStorage
from app.services.storage.service import get_storage

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


@dataclass
class UploadContext:
    client: TestClient
    connection: Connection
    storage: LocalStorage
    root: Path

    def upload(
        self,
        *,
        company: str = "Example Credit Ltd",
        filename: str = "annual.pdf",
        content: bytes = PDF,
        mime: str = "application/pdf",
    ):
        return self.client.post(
            "/api/v1/documents/upload",
            data={"company_legal_name": company},
            files={"file": (filename, content, mime)},
        )

    def counts(self) -> tuple[int, int, int, int]:
        with Session(self.connection, join_transaction_mode="create_savepoint") as session:
            return (
                session.scalar(select(func.count()).select_from(Company)) or 0,
                session.scalar(select(func.count()).select_from(AnalysisJob)) or 0,
                session.scalar(select(func.count()).select_from(Document)) or 0,
                session.scalar(select(func.count()).select_from(AuditLog)) or 0,
            )

    def files(self) -> list[Path]:
        upload_dir = self.root / "uploads"
        return list(upload_dir.glob("*.pdf")) if upload_dir.exists() else []


@pytest.fixture
def upload_context(
    database_engine: Engine, test_url: str, tmp_path: Path
) -> Iterator[UploadContext]:
    connection = database_engine.connect()
    outer = connection.begin()
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=test_url,
        local_storage_path=tmp_path,
        max_upload_size_mb=1,
        ocr_enabled=False,
    )
    app = create_app(settings)

    def test_db() -> Iterator[Session]:
        with Session(connection, join_transaction_mode="create_savepoint") as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield UploadContext(client, connection, LocalStorage(tmp_path), tmp_path)
    outer.rollback()
    connection.close()


def test_upload_valid_pdf_creates_company_job_document_and_audit(
    upload_context: UploadContext,
) -> None:
    response = upload_context.upload()
    assert response.status_code == 201
    payload = response.json()
    assert payload["document"]["status"] == "UPLOADED"
    assert payload["document"]["file_size_bytes"] == len(PDF)
    assert payload["document"]["sha256_hash"] == hashlib.sha256(PDF).hexdigest()
    assert upload_context.counts() == (1, 1, 1, 1)
    assert len(upload_context.files()) == 1
    with Session(upload_context.connection, join_transaction_mode="create_savepoint") as session:
        document = session.get(Document, UUID(payload["document"]["id"]))
        assert document is not None
        assert document.status == DocumentStatus.UPLOADED
        assert document.analysis_job_id == UUID(payload["analysis_id"])
        assert document.company_id == UUID(payload["company_id"])
        assert document.storage_uri == f"local://uploads/{document.id.hex}.pdf"
        assert document.stored_filename == f"{document.id.hex}.pdf"
        assert document.analysis_job.status == AnalysisJobStatus.PENDING
        assert document.company.legal_name == "Example Credit Ltd"
        assert document.analysis_job.audit_logs[0].event_type == "DOCUMENT_UPLOADED"


def test_sha256_is_deterministic(upload_context: UploadContext) -> None:
    first = upload_context.upload(company="First Company")
    second = upload_context.upload(company="Second Company")
    assert first.status_code == second.status_code == 201
    assert first.json()["document"]["sha256_hash"] == second.json()["document"]["sha256_hash"]


def test_duplicate_rejected_without_second_file_or_row(upload_context: UploadContext) -> None:
    first = upload_context.upload()
    assert first.status_code == 201
    second = upload_context.upload(company="example credit ltd")
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "DUPLICATE_DOCUMENT"
    assert (
        second.json()["error"]["details"]["existing_document_id"] == first.json()["document"]["id"]
    )
    assert upload_context.counts() == (1, 1, 1, 1)
    assert len(upload_context.files()) == 1


@pytest.mark.parametrize(
    ("filename", "content", "mime", "code"),
    [
        ("empty.pdf", b"", "application/pdf", "EMPTY_FILE"),
        ("report.exe", PDF, "application/pdf", "INVALID_FILE_TYPE"),
        ("annual_report.pdf.exe", PDF, "application/pdf", "INVALID_FILE_TYPE"),
        ("fake.pdf", b"MZ executable", "application/pdf", "INVALID_PDF_SIGNATURE"),
        ("report.pdf", PDF, "application/octet-stream", "INVALID_MIME_TYPE"),
    ],
)
def test_invalid_upload_rejected_without_state(
    upload_context: UploadContext, filename: str, content: bytes, mime: str, code: str
) -> None:
    response = upload_context.upload(filename=filename, content=content, mime=mime)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == code
    assert upload_context.counts() == (0, 0, 0, 0)
    assert upload_context.files() == []


def test_file_over_size_limit_rejected(upload_context: UploadContext) -> None:
    response = upload_context.upload(content=b"%PDF-" + b"x" * (1024 * 1024))
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert upload_context.counts() == (0, 0, 0, 0)
    assert upload_context.files() == []


@pytest.mark.parametrize(
    "filename", ["../../secret.pdf", "..\\..\\windows\\file.pdf", "company/../../report.pdf"]
)
def test_path_traversal_filename_is_sanitized(upload_context: UploadContext, filename: str) -> None:
    response = upload_context.upload(filename=filename)
    assert response.status_code == 201
    assert "/" not in response.json()["document"]["original_filename"]
    assert "\\" not in response.json()["document"]["original_filename"]
    assert len(upload_context.files()) == 1
    assert upload_context.files()[0].parent == upload_context.root / "uploads"


def test_document_metadata_and_analysis_listing(upload_context: UploadContext) -> None:
    result = upload_context.upload().json()
    document_id = result["document"]["id"]
    analysis_id = result["analysis_id"]
    metadata = upload_context.client.get(f"/api/v1/documents/{document_id}")
    assert metadata.status_code == 200
    assert metadata.json()["analysis_job_id"] == analysis_id
    assert metadata.json()["sha256_hash"] == hashlib.sha256(PDF).hexdigest()
    assert "storage_uri" not in metadata.json()
    listing = upload_context.client.get(f"/api/v1/analysis/{analysis_id}/documents")
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [document_id]


def test_unknown_document_returns_404(upload_context: UploadContext) -> None:
    response = upload_context.client.get(f"/api/v1/documents/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


def test_storage_failure_rolls_back_database(
    upload_context: UploadContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_save(_source, _name: str) -> str:
        raise OSError("injected storage failure")

    monkeypatch.setattr(upload_context.storage, "save_file", fail_save)
    upload_context.client.app.dependency_overrides[get_storage] = lambda: upload_context.storage
    response = upload_context.upload()
    assert response.status_code == 500
    assert upload_context.counts() == (0, 0, 0, 0)
    assert upload_context.files() == []


def test_database_failure_after_storage_cleans_up_file(
    upload_context: UploadContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_audit(*_args, **_kwargs):
        raise IntegrityError("INSERT audit_logs", {}, Exception("injected database failure"))

    monkeypatch.setattr(ingestion, "write_audit_log", fail_audit)
    response = upload_context.upload()
    assert response.status_code == 500
    assert upload_context.counts() == (0, 0, 0, 0)
    assert upload_context.files() == []


def test_commit_failure_after_storage_cleans_up_file(upload_context: UploadContext) -> None:
    def fail_before_commit(_session: Session) -> None:
        raise IntegrityError("COMMIT", {}, Exception("injected commit failure"))

    event.listen(Session, "before_commit", fail_before_commit)
    try:
        response = upload_context.upload()
    finally:
        event.remove(Session, "before_commit", fail_before_commit)
    assert response.status_code == 500
    assert upload_context.counts() == (0, 0, 0, 0)
    assert upload_context.files() == []


def test_status_reports_day_3_and_health_reports_storage(upload_context: UploadContext) -> None:
    status = upload_context.client.get("/api/v1/status")
    health = upload_context.client.get("/api/v1/health")
    assert status.status_code == health.status_code == 200
    assert status.json()["components"]["file_upload"] == "ready"
    assert status.json()["components"]["local_storage"] == "ready"
    assert status.json()["components"]["duplicate_detection"] == "ready"
    assert status.json()["components"]["document_intelligence"] == "foundation_ready"
    assert status.json()["development_stage"]["day"] == 24
    assert health.json()["dependencies"] == {
        "database": "connected",
        "storage": "ready",
        "ocr": "disabled",
    }


def test_local_storage_rejects_malicious_keys(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    with pytest.raises(Exception):
        storage.exists("local://uploads/../../secret.pdf")
    with pytest.raises(Exception):
        storage.delete_file("file:///etc/passwd")
