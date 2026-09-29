from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.session import get_db
from app.main import create_app
from app.models import (
    AnalysisJob,
    AuditLog,
    Company,
    CompanyProfile,
    Document,
    DocumentPage,
    ExtractedField,
)
from app.models.enums import DocumentStatus, PageExtractionMethod, ParserStatus
from app.services.company_profile.extractor import (
    compare_identity,
    extract_candidates,
    normalize_legal_name,
)

REPORT = """ABC Electrical Limited — Annual Report 2025-26
ABOUT US
ABC Electrical Limited is a manufacturer of transformers and switchgear for power systems.
Products: Transformers, Switchgear
Services: EPC Services, Maintenance Services
Operating Segments: Power Equipment, Industrial Solutions
Headquarters: Bengaluru, Karnataka
Country: India
Website: www.example.com"""


@dataclass
class Context:
    client: TestClient
    connection: Connection

    def document(
        self, *texts: str, uploaded: str = "ABC Electrical Ltd", parsed: bool = True
    ) -> str:
        with Session(self.connection, join_transaction_mode="create_savepoint") as session:
            company = Company(legal_name=uploaded)
            session.add(company)
            session.flush()
            job = AnalysisJob(company_id=company.id)
            session.add(job)
            session.flush()
            document = Document(
                company_id=company.id,
                analysis_job_id=job.id,
                original_filename="report.pdf",
                status=DocumentStatus.UPLOADED,
                parser_status=ParserStatus.PARSED if parsed else ParserStatus.NOT_STARTED,
                sha256_hash=uuid4().hex,
            )
            session.add(document)
            session.flush()
            for number, text in enumerate(texts, 1):
                session.add(
                    DocumentPage(
                        document_id=document.id,
                        page_number=number,
                        text_content=text,
                        extraction_method=PageExtractionMethod.NATIVE_TEXT,
                        parser_version="pdf_parser_v1",
                    )
                )
            session.commit()
            return str(document.id)

    def extract(self, document_id: str):
        return self.client.post(f"/api/v1/documents/{document_id}/company-profile/extract")

    def rows(self, document_id: str) -> list[ExtractedField]:
        with Session(self.connection, join_transaction_mode="create_savepoint") as session:
            return list(
                session.scalars(
                    select(ExtractedField).where(ExtractedField.document_id == UUID(document_id))
                ).all()
            )


@pytest.fixture
def context(database_engine: Engine, test_url: str) -> Iterator[Context]:
    connection = database_engine.connect()
    outer = connection.begin()
    app = create_app(
        Settings(_env_file=None, app_env="test", database_url=test_url, ocr_enabled=False)
    )

    def test_db() -> Iterator[Session]:
        with Session(connection, join_transaction_mode="create_savepoint") as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield Context(client, connection)
    outer.rollback()
    connection.close()


def test_profile_requires_parsed_document_and_unknown_document(context: Context) -> None:
    document_id = context.document(REPORT, parsed=False)
    response = context.extract(document_id)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DOCUMENT_NOT_PARSED"
    assert context.extract(str(uuid4())).status_code == 404


def test_full_profile_has_evidence_provenance_and_status(context: Context) -> None:
    document_id = context.document(REPORT)
    response = context.extract(document_id)
    assert response.status_code == 200, response.text
    profile = response.json()
    assert profile["status"] == "VERIFIED"
    assert profile["identity_match_status"] == "MATCHED"
    assert profile["extractor_version"] == "company_profile_extractor_v1"
    legal = profile["fields"]["legal_name"][0]
    assert legal["value"] == "ABC Electrical Limited"
    assert legal["status"] == "VERIFIED"
    assert legal["page_number"] == 1
    assert 0.85 <= legal["confidence"] <= 1
    assert profile["fields"]["reporting_period"][0]["value"] == "FY2026"
    assert "manufacturer of transformers" in profile["fields"]["business_description"][0]["value"]
    assert {x["value"] for x in profile["fields"]["product"]} == {"Transformers", "Switchgear"}
    assert {x["value"] for x in profile["fields"]["service"]} == {
        "EPC Services",
        "Maintenance Services",
    }
    assert len(profile["fields"]["operating_segment"]) == 2
    assert profile["fields"]["headquarters"][0]["value"] == "Bengaluru, Karnataka"
    assert profile["fields"]["country"][0]["value"] == "India"
    assert profile["fields"]["website"][0]["value"] == "www.example.com"
    rows = context.rows(document_id)
    assert all(row.document_page_id and row.page_number == 1 and row.evidence_text for row in rows)
    assert all(0 <= row.confidence_score <= 1 for row in rows)
    assert all(len(row.evidence_text) <= 800 for row in rows)
    assert all(row.extractor_version == "company_profile_extractor_v1" for row in rows)


def test_profile_get_and_evidence_endpoints(context: Context) -> None:
    document_id = context.document(REPORT)
    assert context.client.get(f"/api/v1/documents/{document_id}/company-profile").status_code == 404
    profile = context.extract(document_id).json()
    retrieved = context.client.get(f"/api/v1/documents/{document_id}/company-profile")
    assert retrieved.status_code == 200 and retrieved.json() == profile
    evidence = context.client.get(f"/api/v1/company-profiles/{profile['profile_id']}/evidence")
    assert evidence.status_code == 200
    assert len(evidence.json()) == len(context.rows(document_id))
    assert evidence.json()[0]["document_page_id"]
    assert context.client.get(f"/api/v1/company-profiles/{uuid4()}/evidence").status_code == 404


def test_idempotency_and_audit(context: Context) -> None:
    document_id = context.document(REPORT)
    first = context.extract(document_id).json()
    row_count = len(context.rows(document_id))
    second = context.extract(document_id).json()
    assert first == second
    assert len(context.rows(document_id)) == row_count
    with Session(context.connection, join_transaction_mode="create_savepoint") as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(CompanyProfile)
                .where(CompanyProfile.document_id == UUID(document_id))
            )
            == 1
        )
        events = list(
            session.scalars(
                select(AuditLog.event_type).where(AuditLog.entity_id == UUID(first["profile_id"]))
            ).all()
        )
    assert events.count("COMPANY_PROFILE_EXTRACTED") == 1


def test_missing_optional_fields_remain_unavailable(context: Context) -> None:
    document_id = context.document(
        "ABC Electrical Limited — Annual Report 2025-26\nABOUT US\n"
        "ABC Electrical Limited is a manufacturer of transformers for power systems."
    )
    profile = context.extract(document_id).json()
    assert profile["status"] == "VERIFIED"
    assert profile["fields"]["website"] == []
    assert profile["fields"]["headquarters"] == []
    assert profile["fields"]["country"] == []
    with Session(context.connection, join_transaction_mode="create_savepoint") as session:
        row = session.scalar(
            select(CompanyProfile).where(CompanyProfile.document_id == UUID(document_id))
        )
        assert row is not None and row.website is None and row.country is None


def test_subsidiary_auditor_bank_and_customer_not_primary(context: Context) -> None:
    extra = """Independent Auditor: XYZ & Associates LLP
ABC Electrical Limited has subsidiaries:
ABC Renewables Private Limited
ABC Switchgear Private Limited
Customer: Reliance Industries Limited
Bank: State Bank of India"""
    document_id = context.document(REPORT, extra)
    profile = context.extract(document_id).json()
    assert profile["status"] == "VERIFIED"
    assert {x["value"] for x in profile["fields"]["legal_name"]} == {"ABC Electrical Limited"}


def test_identity_mismatch_requires_review_and_audit(context: Context) -> None:
    document_id = context.document(REPORT, uploaded="XYZ Power Limited")
    profile = context.extract(document_id).json()
    assert profile["identity_match_status"] == "MISMATCH"
    assert profile["status"] == "NEEDS_REVIEW"
    assert profile["fields"]["legal_name"][0]["status"] == "NEEDS_REVIEW"
    with Session(context.connection, join_transaction_mode="create_savepoint") as session:
        row = session.scalar(
            select(CompanyProfile).where(CompanyProfile.document_id == UUID(document_id))
        )
        assert row is not None and row.legal_name is None
        company = session.get(Company, row.company_id)
        assert company is not None and company.legal_name == "XYZ Power Limited"
        events = list(
            session.scalars(select(AuditLog.event_type).where(AuditLog.entity_id == row.id)).all()
        )
    assert "COMPANY_IDENTITY_MISMATCH" in events


def test_conflicting_strong_names_are_both_preserved(context: Context) -> None:
    second = "ABC Electrical Industries Limited — Annual Report 2025-26"
    document_id = context.document(REPORT, second)
    profile = context.extract(document_id).json()
    assert profile["status"] == "CONFLICTING"
    assert {x["status"] for x in profile["fields"]["legal_name"]} == {"CONFLICTING"}
    assert {x["page_number"] for x in profile["fields"]["legal_name"]} == {1, 2}
    with Session(context.connection, join_transaction_mode="create_savepoint") as session:
        row = session.scalar(
            select(CompanyProfile).where(CompanyProfile.document_id == UUID(document_id))
        )
        assert row is not None and row.legal_name is None


def test_partial_document_inherits_review(context: Context) -> None:
    document_id = context.document(REPORT)
    with Session(context.connection, join_transaction_mode="create_savepoint") as session:
        doc = session.get(Document, UUID(document_id))
        assert doc is not None
        doc.parser_status = ParserStatus.PARTIAL
        session.commit()
    assert context.extract(document_id).json()["status"] == "NEEDS_REVIEW"


def test_low_confidence_business_field_needs_review(context: Context) -> None:
    text = (
        "ABC Electrical Limited — Annual Report 2025-26\n"
        "ABC Electrical Limited is a manufacturer of transformers for power systems."
    )
    document_id = context.document(text)
    profile = context.extract(document_id).json()
    assert profile["status"] == "PARTIAL"
    assert profile["fields"]["business_description"][0]["status"] == "NEEDS_REVIEW"


@pytest.mark.parametrize(
    "uploaded,extracted,expected",
    [
        ("ABC Electrical Ltd", "ABC Electrical Limited", "MATCHED"),
        ("ABC Electrical Limited", "ABC Electrical Limited", "MATCHED"),
        ("XYZ Power Limited", "ABC Electrical Limited", "MISMATCH"),
    ],
)
def test_identity_matching_and_normalization(uploaded: str, extracted: str, expected: str) -> None:
    assert compare_identity(uploaded, extracted).value == expected
    assert normalize_legal_name("ABC ELECTRICAL LIMITED") == "ABC Electrical Limited"


def test_rule_extraction_is_document_only() -> None:
    page = DocumentPage(page_number=1, text_content="No company identity or country is stated.")
    assert extract_candidates([page], "Uploaded Company Limited") == []


def test_status_reports_day_5(context: Context) -> None:
    response = context.client.get("/api/v1/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["development_stage"]["day"] == 24
    assert payload["components"]["company_identity_extraction"] == "ready"
    assert payload["components"]["business_profile_extraction"] == "ready"
    assert payload["components"]["evidence_mapping"] == "ready"
    assert payload["components"]["domain_classification"] in {"ready", "unavailable"}


def test_single_weak_legal_occurrence_is_not_verified(context: Context) -> None:
    document_id = context.document(
        "ABC Electrical Limited is engaged in manufacturing equipment for power systems."
    )
    profile = context.extract(document_id).json()
    assert profile["status"] == "NEEDS_REVIEW"
    assert profile["fields"]["legal_name"][0]["status"] == "NEEDS_REVIEW"
    with Session(context.connection, join_transaction_mode="create_savepoint") as session:
        row = session.scalar(
            select(CompanyProfile).where(CompanyProfile.document_id == UUID(document_id))
        )
        assert row is not None and row.legal_name is None


def test_extraction_preserves_source_pages(context: Context) -> None:
    document_id = context.document(REPORT)
    with Session(context.connection, join_transaction_mode="create_savepoint") as session:
        before = [
            (row.id, row.text_content, row.parser_version)
            for row in session.scalars(
                select(DocumentPage).where(DocumentPage.document_id == UUID(document_id))
            )
        ]
    assert context.extract(document_id).status_code == 200
    with Session(context.connection, join_transaction_mode="create_savepoint") as session:
        after = [
            (row.id, row.text_content, row.parser_version)
            for row in session.scalars(
                select(DocumentPage).where(DocumentPage.document_id == UUID(document_id))
            )
        ]
    assert before == after


def test_profile_and_field_foreign_keys(context: Context) -> None:
    document_id = context.document(REPORT)
    profile_id = UUID(context.extract(document_id).json()["profile_id"])
    with Session(context.connection, join_transaction_mode="create_savepoint") as session:
        profile = session.get(CompanyProfile, profile_id)
        assert profile is not None
        document = session.get(Document, UUID(document_id))
        assert document is not None
        assert profile.document_id == document.id
        assert profile.company_id == document.company_id
        assert profile.analysis_job_id == document.analysis_job_id
        for field in session.scalars(
            select(ExtractedField).where(ExtractedField.company_profile_id == profile_id)
        ):
            page = session.get(DocumentPage, field.document_page_id)
            assert page is not None
            assert field.document_id == page.document_id == document.id
            assert field.page_number == page.page_number


def test_oil_and_software_reports_do_not_classify_domain(context: Context) -> None:
    fixtures = [
        "Delta Refining Limited — Annual Report 2025-26\nABOUT US\n"
        "Delta Refining Limited is engaged in refining petroleum products.\n"
        "Products: Diesel, Aviation fuel\nOperating Segments: Refining, Petrochemicals",
        "Nimbus Software Limited — Annual Report 2025-26\nABOUT US\n"
        "Nimbus Software Limited provides enterprise software services to global clients.\n"
        "Services: Software development, Cloud migration",
    ]
    for uploaded, text in zip(("Delta Refining Ltd", "Nimbus Software Ltd"), fixtures):
        profile = context.extract(context.document(text, uploaded=uploaded)).json()
        assert profile["status"] == "VERIFIED"
        assert "domain" not in profile["fields"]
        assert "sector" not in profile["fields"]


def test_persistence_failure_rolls_back_profile_and_fields(
    context: Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.company_profile import service

    document_id = context.document(REPORT)
    real_write = service.write_audit_log
    calls = 0

    def fail_second_audit(*args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected persistence failure")
        return real_write(*args, **kwargs)

    monkeypatch.setattr(service, "write_audit_log", fail_second_audit)
    failure = context.extract(document_id)
    assert failure.status_code == 500
    assert failure.json()["error"]["code"] == "PROFILE_EXTRACTION_FAILED"
    with Session(context.connection, join_transaction_mode="create_savepoint") as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(CompanyProfile)
                .where(CompanyProfile.document_id == UUID(document_id))
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(ExtractedField)
                .where(ExtractedField.document_id == UUID(document_id))
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.entity_id == UUID(document_id),
                    AuditLog.event_type == "COMPANY_PROFILE_EXTRACTION_FAILED",
                )
            )
            == 1
        )


def test_profile_schema_indexes_and_unique_constraint(database_engine: Engine) -> None:
    inspector = inspect(database_engine)
    assert {"company_profiles", "extracted_fields"} <= set(inspector.get_table_names())
    uniques = {item["name"] for item in inspector.get_unique_constraints("company_profiles")}
    assert "uq_company_profiles_document_version" in uniques
    profile_indexes = {item["name"] for item in inspector.get_indexes("company_profiles")}
    field_indexes = {item["name"] for item in inspector.get_indexes("extracted_fields")}
    assert {"ix_company_profiles_document_id", "ix_company_profiles_company_id"} <= profile_indexes
    assert {"ix_extracted_fields_document_page_id", "ix_extracted_fields_status"} <= field_indexes
