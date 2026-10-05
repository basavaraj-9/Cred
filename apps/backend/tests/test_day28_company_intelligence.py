import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pymupdf
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.company import Company
from app.models.credit import CreditAssessment
from app.models.reporting import GeneratedReport, ReportArtifact, ReportSnapshot, ReportSourceLink
from app.models.stock import ListedCompany
from app.models.stock_intelligence import (
    StockIntelligenceComponent,
    StockIntelligenceComponentInput,
)
from app.services.reporting.company_intelligence import CompanyIntelligenceReportService
from app.services.reporting.service import report_payload
from app.services.stock_analytics.service import FeatureService, ValuationService
from app.services.stock_intelligence.service import StockIntelligenceService
from app.services.stock_monitoring.service import StockMonitoringService
from app.services.stock_validation.service import StockIntelligenceValidationService
from tests.test_day20_reporting import _review
from tests.test_day23_stock_analytics import _context
from tests.test_day25_stock_intelligence import _day25_context


def _rebuild_current_credit(session: Session, company: Company):
    from app.models.company_profile import CompanyProfile
    from app.services.credit_decision.service import CreditDecisionSupportService
    from app.services.credit_recommendation.service import CreditRecommendationService
    from app.services.external_research.service import ExternalResearchService
    from app.services.five_cs.refresh import FiveCsResearchRefreshService
    from app.services.five_cs.service import FiveCsAssessmentService

    profile = session.scalar(select(CompanyProfile).where(CompanyProfile.company_id == company.id))
    base = FiveCsAssessmentService(session).analyze(profile.document_id)[0]
    research = ExternalResearchService(session).research_company(
        company.id, ["COMPANY", "LEGAL", "RATINGS", "INDUSTRY", "SECTOR"]
    )
    refreshed = FiveCsResearchRefreshService(session).refresh(base["assessment_id"], research.id)
    recommendation = CreditRecommendationService(session).prepare(
        profile.document_id,
        five_cs_assessment_id=refreshed["refreshed_assessment_id"],
        research_run_id=research.id,
    )
    CreditDecisionSupportService(session).prepare(
        profile.document_id, recommendation_preparation_id=recommendation["preparation_id"]
    )
    return refreshed["refreshed_assessment_id"], research.id


def test_validation_monitoring_snapshot_and_future_exclusion(
    db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Construct consistent identity before any research/credit services execute.
    from tests.test_five_cs import _context as credit_context

    monkeypatch.setattr(
        "tests.test_day18_credit_decision._context",
        lambda session: credit_context(session, company_name="Grid Switchgear India Limited"),
    )
    admin, listings, dates, _, _, _, _ = _day25_context(db_session)
    company = db_session.scalar(select(Company))
    # Resolve the fixture's listing by legal identity, never by database row order.
    listing = next(
        item
        for item in listings
        if db_session.get(ListedCompany, item.listed_company_id).legal_name == company.legal_name
    )
    listings.remove(listing)
    listings.insert(0, listing)
    listed = db_session.get(ListedCompany, listing.listed_company_id)
    current_five, current_research = _rebuild_current_credit(db_session, company)
    from app.services.stock_analytics.service import FundamentalService

    FundamentalService(db_session).sync(admin.id, [listed.id])
    ValuationService(db_session).build(listings[0].id, dates[-2], admin.id)
    validation = StockIntelligenceValidationService(db_session).build_validation(
        dates[0], dates[-2], admin.id
    )
    monitoring = StockMonitoringService(db_session).build_monitoring_run(
        dates[0], dates[2], dates[3], dates[-2], admin.id
    )
    service = CompanyIntelligenceReportService(db_session, tmp_path)
    report = service.generate(company.id, admin.id)
    snapshot = db_session.scalar(
        select(ReportSnapshot).where(ReportSnapshot.generated_report_id == report.id)
    )
    payload = snapshot.payload_json
    assert payload["sections"]["validation"]["data"]["run"]["id"] == str(validation.id)
    assert payload["sections"]["monitoring"]["data"]["run"]["id"] == str(monitoring.id)
    assert payload["sections"]["monitoring"]["data"]["automatic_action"] == "NONE"
    assert payload["sections"]["stock"]["data"]["fundamentals"]
    assert payload["sections"]["stock"]["data"]["valuations"]
    assert payload["sections"]["credit"]["data"]["assessment"]
    assert payload["sections"]["stock"]["data"]["score"]
    profile = payload["sections"]["company_profile"]["data"]["profile"]
    assert profile["legal_name"] == company.legal_name == "Grid Switchgear India Limited"
    assert profile["identity_match_status"] == "MATCHED"
    assert payload["sections"]["credit"]["data"]["five_cs"]["id"] == str(current_five)
    assert payload["sections"]["credit"]["data"]["research"]["id"] == str(current_research)
    assert "CONDITIONS_DOMAIN_UNVERIFIED" not in json.dumps(payload)
    assert "DOMAIN_CLASSIFICATION_REVIEW_REQUIRED" not in json.dumps(payload)
    assert "Day 15 Test Ltd" not in json.dumps(payload)
    # Preserve a deterministic smoke export for manual review; source records
    # remain isolated in this test transaction.
    import shutil

    output = Path(__file__).resolve().parents[3] / "output" / "day28-smoke"
    output.mkdir(parents=True, exist_ok=True)
    for artifact in db_session.scalars(
        select(ReportArtifact).where(ReportArtifact.generated_report_id == report.id)
    ):
        shutil.copyfile(
            tmp_path / artifact.storage_path,
            output / f"company-intelligence-360.{artifact.format.lower()}",
        )
        if artifact.format == "PDF":
            with pymupdf.open(tmp_path / artifact.storage_path) as pdf:
                rendered = "".join(page.get_text() for page in pdf)
            assert "Grid Switchgear India Limited" in rendered
            assert "Day 15 Test Ltd" not in rendered
            assert "CONDITIONS_DOMAIN_UNVERIFIED" not in rendered
            assert "DOMAIN_CLASSIFICATION_REVIEW_REQUIRED" not in rendered
            assert "development_fixture_provider" not in rendered
            assert "development_fixture_fundamentals_provider" not in rendered
            assert "Development market data provider" in rendered
            assert "Development fundamentals provider" in rendered
        assert "development_fixture_provider" in json.dumps(payload)

    before = snapshot.payload_hash
    monitoring.created_at = datetime.now(UTC) + timedelta(days=2)
    db_session.flush()
    later, links, _ = service.build_snapshot(company.id, None, datetime.now(UTC).date(), True, True)
    assert later["sections"]["monitoring"]["status"] == "UNAVAILABLE"
    assert str(monitoring.id) not in later["manifest"]["source_ids"]
    assert snapshot.payload_hash == before
    excluded, excluded_links, _ = service.build_snapshot(
        company.id, None, datetime.now(UTC).date(), False, False
    )
    assert excluded["sections"]["stock"]["status"] == "NOT_APPLICABLE"
    assert excluded["sections"]["credit"]["status"] == "NOT_APPLICABLE"
    assert not any(
        source_type.startswith(("STOCK_", "CREDIT_")) for source_type, _, _, _ in excluded_links
    )


def test_export_failure_rolls_back_all_report_metadata(
    db_session: Session, tmp_path: Path, monkeypatch
):
    _, case, admin, _, _ = _review(db_session)
    service = CompanyIntelligenceReportService(db_session, tmp_path)

    def fail(*args):
        raise RuntimeError("Renderer failed")

    monkeypatch.setattr(service, "_render_pdf", fail)
    with pytest.raises(RuntimeError, match="Renderer failed"):
        service.generate(case.company_id, admin.id)
    assert (
        db_session.scalar(
            select(GeneratedReport).where(GeneratedReport.company_id == case.company_id)
        )
        is None
    )
    assert list(tmp_path.rglob("*.json")) == []
    assert list(tmp_path.rglob("*.pdf")) == []
    service.policy["max_records_per_collection"] = 1
    with pytest.raises(AppError, match="source limit exceeded"):
        service.build_snapshot(case.company_id, None, datetime.now(UTC).date(), True, True)


def test_api_snapshot_evidence_exports_and_permissions(db_session: Session, tmp_path: Path):
    from app.api.v1.company_intelligence_reports import _artifact, evidence, get_report, snapshot
    from app.core.config import Settings
    from tests.test_day19_credit_review import _user

    _, case, admin, _, _ = _review(db_session)
    settings = Settings(_env_file=None, local_storage_path=tmp_path)
    service = CompanyIntelligenceReportService(db_session, tmp_path)
    report = service.generate(case.company_id, admin.id)
    assert get_report(report.id, admin.id, db_session, settings)["id"] == report.id
    assert snapshot(report.id, admin.id, db_session, settings)["payload_hash"]
    assert evidence(report.id, admin.id, db_session, settings)
    assert (
        _artifact(report.id, "JSON", admin.id, db_session, settings).media_type
        == "application/json"
    )
    analyst = _user(db_session, "CREDIT_ANALYST")
    with pytest.raises(AppError):
        service.finalize(report.id, analyst.id, None)
    analyst.is_active = False
    with pytest.raises(AppError):
        get_report(report.id, analyst.id, db_session, settings)


def test_missing_credit_and_listed_score_are_explicit(db_session: Session, tmp_path: Path):
    from tests.test_day22_stock import _stock_context

    case, admin, _, _ = _stock_context(db_session)
    listed = db_session.scalar(select(ListedCompany))
    company = Company(legal_name=listed.legal_name)
    db_session.add(company)
    db_session.flush()
    service = CompanyIntelligenceReportService(db_session, tmp_path)
    payload, _, _ = service.build_snapshot(company.id, None, datetime.now(UTC).date(), True, True)
    assert payload["sections"]["stock"]["status"] == "PARTIAL"
    assert payload["sections"]["stock"]["data"]["score"] is None
    assert payload["sections"]["credit"]["status"] == "UNAVAILABLE"
    assert payload["executive_summary"]["credit_view"] is None
    assert payload["executive_summary"]["equity_research_view"] is None


def test_nonlisted_report_snapshot_and_artifacts(db_session: Session, tmp_path: Path) -> None:
    _, case, admin, _, _ = _review(db_session)
    service = CompanyIntelligenceReportService(db_session, tmp_path)
    report = service.generate(case.company_id, admin.id, as_of=datetime.now(UTC).date())
    snapshot = db_session.scalar(
        select(ReportSnapshot).where(ReportSnapshot.generated_report_id == report.id)
    )
    assert snapshot is not None
    assert snapshot.payload_json["sections"]["stock"]["status"] == "NOT_APPLICABLE"
    assert service.generate(case.company_id, admin.id).id == report.id
    artifacts = list(
        db_session.scalars(
            select(ReportArtifact).where(ReportArtifact.generated_report_id == report.id)
        )
    )
    assert {item.format for item in artifacts} == {"JSON", "PDF"}
    assert len(report_payload(db_session, report)["artifacts"]) == 2


def test_listed_report_preserves_scores_lineage_and_pdf(db_session: Session, tmp_path: Path):
    admin, listings = _context(db_session)
    listing = listings[0]
    company = db_session.scalar(select(Company))
    listed = db_session.get(ListedCompany, listing.listed_company_id)
    company.legal_name = listed.legal_name
    day = date(2026, 9, 25)
    ValuationService(db_session).build(listing.id, day, admin.id)
    FeatureService(db_session).build(listing.id, day, admin.id)
    score = StockIntelligenceService(db_session).build_score(listing.id, day, admin.id)
    original = (score.score, score.input_hash)
    service = CompanyIntelligenceReportService(db_session, tmp_path)
    report = service.generate(company.id, admin.id)
    snapshot = db_session.scalar(
        select(ReportSnapshot).where(ReportSnapshot.generated_report_id == report.id)
    )
    payload = snapshot.payload_json
    assert payload["sections"]["stock"]["data"]["score"]["id"] == str(score.id)
    assert len(payload["sections"]["stock"]["data"]["components"]) == 11
    expected_inputs = set(
        db_session.scalars(
            select(StockIntelligenceComponentInput.id)
            .join(StockIntelligenceComponent)
            .where(StockIntelligenceComponent.run_id == score.id)
        )
    )
    assert {item["id"] for item in payload["sections"]["stock"]["data"]["component_inputs"]} == {
        str(source_id) for source_id in expected_inputs
    }
    assert payload["no_master_score"] is True
    assert (score.score, score.input_hash) == original
    types = set(
        db_session.scalars(
            select(ReportSourceLink.source_type).where(
                ReportSourceLink.generated_report_id == report.id
            )
        )
    )
    assert {
        "CREDIT_SCORE",
        "NORMALIZED_FINANCIAL",
        "STOCK_INTELLIGENCE_SCORE",
        "STOCK_VALUATION",
        "STOCK_FEATURE",
    } <= types
    for artifact in db_session.scalars(
        select(ReportArtifact).where(ReportArtifact.generated_report_id == report.id)
    ):
        path = tmp_path / artifact.storage_path
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact.sha256
        if artifact.format == "PDF":
            with pymupdf.open(path) as pdf:
                text = "".join(page.get_text() for page in pdf)
                assert "Company Intelligence Report" in text
                assert "Evidence Appendix" in text
                assert "Credit" in text and "Stock" in text
        else:
            assert json.loads(path.read_text("utf-8")) == payload
    assert (
        snapshot.payload_hash
        == hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


def test_snapshot_immutability_new_version_and_supersession(db_session: Session, tmp_path: Path):
    _, case, admin, _, _ = _review(db_session)
    service = CompanyIntelligenceReportService(db_session, tmp_path)
    report = service.generate(case.company_id, admin.id)
    snapshot = db_session.scalar(
        select(ReportSnapshot).where(ReportSnapshot.generated_report_id == report.id)
    )
    before = json.dumps(snapshot.payload_json, sort_keys=True)
    service.finalize(report.id, admin.id, "Reviewed")
    credit = db_session.scalar(
        select(CreditAssessment).where(CreditAssessment.company_id == case.company_id)
    )
    credit.overall_score = Decimal("40")
    newer = service.generate(case.company_id, admin.id)
    assert newer.id != report.id and newer.report_version == report.report_version + 1
    service.supersede(report.id, newer.id, admin.id, "Updated source evidence")
    assert report.status == "SUPERSEDED"
    assert json.dumps(snapshot.payload_json, sort_keys=True) == before


def test_historical_report_excludes_future_credit_and_documents(
    db_session: Session, tmp_path: Path
):
    _, case, admin, _, _ = _review(db_session)
    service = CompanyIntelligenceReportService(db_session, tmp_path)
    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    payload, links, _ = service.build_snapshot(case.company_id, None, yesterday, True, True)
    assert payload["sections"]["credit"]["status"] == "UNAVAILABLE"
    assert payload["sections"]["documents"]["status"] == "UNAVAILABLE"
    assert not any(item[0] in {"CREDIT_SCORE", "HUMAN_DECISION"} for item in links)
    with pytest.raises(AppError, match="after report as-of"):
        service.build_snapshot(case.company_id, case.analysis_job_id, yesterday, True, True)


def test_http_report_lifecycle_and_artifact_integrity(db_session: Session, tmp_path: Path):
    from fastapi.testclient import TestClient

    from app.core.config import Settings, get_settings
    from app.database.session import get_db
    from app.main import create_app

    _, case, admin, _, _ = _review(db_session)
    connection = db_session.connection()
    settings = Settings(_env_file=None, app_env="test", local_storage_path=tmp_path)
    app = create_app(settings)

    def isolated_session():
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session

    app.dependency_overrides[get_db] = isolated_session
    app.dependency_overrides[get_settings] = lambda: settings
    root = "/api/v1/company-intelligence-reports"
    actor = {"actor_user_id": str(admin.id)}
    body = {**actor, "company_id": str(case.company_id)}
    with TestClient(app) as client:
        response = client.post(root, json=body)
        assert response.status_code == 200, response.text
        report = response.json()
        report_id = report["id"]
        assert client.post(root, json=body).json()["id"] == report_id
        assert (
            client.get(root, params={**actor, "company": str(case.company_id)}).json()[0]["id"]
            == report_id
        )
        for suffix in ("", "/snapshot", "/evidence", "/artifacts/pdf", "/artifacts/json"):
            response = client.get(root + "/" + report_id + suffix, params=actor)
            assert response.status_code == 200, response.text
        assert (
            client.post(
                root + "/" + report_id + "/finalize", json={**actor, "rationale": "Reviewed"}
            ).json()["status"]
            == "FINALIZED"
        )
        body["include_stock"] = False
        successor = client.post(root, json=body).json()
        response = client.post(
            root + "/" + report_id + "/supersede",
            json={**actor, "successor_report_id": successor["id"], "rationale": "Scope changed"},
        )
        assert response.status_code == 200 and response.json()["status"] == "SUPERSEDED"
        artifact = db_session.scalar(
            select(ReportArtifact).where(
                ReportArtifact.generated_report_id == report_id, ReportArtifact.format == "JSON"
            )
        )
        (tmp_path / artifact.storage_path).write_text("tampered", encoding="utf-8")
        assert (
            client.get(root + "/" + report_id + "/artifacts/json", params=actor).status_code == 409
        )


@pytest.mark.parametrize("future", [False, True])
def test_human_decision_separate_and_never_inferred(
    db_session: Session, tmp_path: Path, future: bool
):
    from app.models.review import CreditHumanDecision

    _, case, admin, _, _ = _review(db_session)
    service = CompanyIntelligenceReportService(db_session, tmp_path)
    today = datetime.now(UTC).date()
    before, _, _ = service.build_snapshot(case.company_id, None, today, True, True)
    assert before["sections"]["credit"]["data"]["human_decision"] is None
    timestamp = datetime.now(UTC) + timedelta(days=1 if future else 0)
    human = CreditHumanDecision(
        review_case_id=case.id,
        decision_support_id=case.decision_support_id,
        decided_by_user_id=admin.id,
        decision="DECLINED",
        decision_rationale="Explicit fixture decision",
        decision_authority_role=admin.reviewer_role,
        decision_timestamp=timestamp,
        policy_version="test",
        decision_version=1,
        is_current=True,
        created_at=timestamp,
    )
    db_session.add(human)
    db_session.flush()
    after, links, _ = service.build_snapshot(case.company_id, None, today, True, True)
    section = after["sections"]["credit"]["data"]
    assert (
        section["decision_support"]["system_recommendation"]
        == before["sections"]["credit"]["data"]["decision_support"]["system_recommendation"]
    )
    if future:
        assert section["human_decision"] is None
        assert human.id not in {item[1] for item in links}
    else:
        assert section["human_decision"]["decision"] == "DECLINED"
        assert any(conflict["type"] == "SYSTEM_HUMAN_DECISION" for conflict in after["conflicts"])


def test_schema_rejects_invalid_section_and_master_score(db_session: Session, tmp_path: Path):
    from jsonschema import ValidationError, validate

    _, case, _, _, _ = _review(db_session)
    service = CompanyIntelligenceReportService(db_session, tmp_path)
    payload, _, _ = service.build_snapshot(
        case.company_id, None, datetime.now(UTC).date(), True, True
    )
    payload["no_master_score"] = False
    with pytest.raises(ValidationError):
        validate(payload, service.schema)
    payload["no_master_score"] = True
    payload["sections"]["credit"]["status"] = "APPROVED"
    with pytest.raises(ValidationError):
        validate(payload, service.schema)


def test_report_document_page_lineage(db_session: Session, tmp_path: Path):
    from app.models.document_page import DocumentPage
    from app.models.enums import PageExtractionMethod

    _, case, admin, _, _ = _review(db_session)
    page = DocumentPage(
        document_id=case.document_id,
        page_number=987,
        extraction_method=PageExtractionMethod.NATIVE_TEXT,
        text_content="Verified source snippet",
        character_count=23,
        word_count=3,
        text_quality_score=1,
        parser_version="fixture",
    )
    db_session.add(page)
    db_session.flush()
    report = CompanyIntelligenceReportService(db_session, tmp_path).generate(
        case.company_id, admin.id
    )
    link = db_session.scalar(
        select(ReportSourceLink).where(
            ReportSourceLink.generated_report_id == report.id,
            ReportSourceLink.source_reference_id == page.id,
        )
    )
    assert link.source_type == "DOCUMENT_PAGE"
    assert link.source_metadata_json["document_id"] == str(case.document_id)
    assert link.source_metadata_json["page_number"] == 987
    assert link.source_metadata_json["snippet"] == "Verified source snippet"


def test_future_prices_fundamentals_and_scores_excluded(db_session: Session, tmp_path: Path):
    from app.models.stock import StockPrice
    from app.models.stock_analytics import StockFundamental, StockFundamentalRun
    from app.services.stock.service import MarketDataService

    admin, listings = _context(db_session)
    listing = listings[0]
    company = db_session.scalar(select(Company))
    company.legal_name = db_session.get(ListedCompany, listing.listed_company_id).legal_name
    today = datetime.now(UTC).date()
    future = today + timedelta(days=365)
    MarketDataService(db_session).sync(
        admin.id, future, future + timedelta(days=7), symbols=[listing.symbol]
    )
    score = StockIntelligenceService(db_session).build_score(listing.id, today, admin.id)
    score.as_of_date = future
    for run in db_session.scalars(
        select(StockFundamentalRun).where(
            StockFundamentalRun.listed_company_id == listing.listed_company_id
        )
    ):
        run.availability_date = future
    for item in db_session.scalars(
        select(StockFundamental).where(
            StockFundamental.listed_company_id == listing.listed_company_id
        )
    ):
        item.availability_date = future
    db_session.flush()
    payload, links, _ = CompanyIntelligenceReportService(db_session, tmp_path).build_snapshot(
        company.id, None, today, True, True
    )
    stock = payload["sections"]["stock"]["data"]
    assert stock["score"] is None and stock["fundamentals"] == []
    assert stock["market_data"]["price"]["trade_date"] <= today.isoformat()
    assert "last_price_date" not in stock["listing"]
    assert "end_date" not in stock["market_data"]["run"]
    future_ids = set(db_session.scalars(select(StockPrice.id).where(StockPrice.trade_date > today)))
    assert not future_ids.intersection({item[1] for item in links})
    assert score.id not in {item[1] for item in links}


@pytest.mark.parametrize(
    "extracted, expected",
    [
        ("Grid Switchgear India Ltd.", "MATCHED"),
        ("  GRID  SWITCHGEAR INDIA LIMITED ", "MATCHED"),
        ("Day 15 Test Ltd", "MISMATCH"),
        ("", "UNAVAILABLE"),
    ],
)
def test_report_identity_is_recomputed_without_renaming(
    db_session: Session, tmp_path: Path, extracted: str, expected: str
):
    from app.models.company_profile import CompanyProfile
    from app.models.enums import IdentityMatchStatus

    _, case, admin, _, _ = _review(db_session)
    company = db_session.get(Company, case.company_id)
    company.legal_name = "Grid Switchgear India Limited"
    profile = db_session.scalar(
        select(CompanyProfile).where(CompanyProfile.company_id == company.id)
    )
    profile.legal_name = extracted
    profile.identity_match_status = IdentityMatchStatus.MATCHED
    db_session.flush()
    payload, _, _ = CompanyIntelligenceReportService(db_session, tmp_path).build_snapshot(
        company.id, None, datetime.now(UTC).date(), True, False
    )
    current = payload["sections"]["company_profile"]["data"]["profile"]
    assert current["identity_match_status"] == expected
    assert current["recorded_identity_match_status"] == "MATCHED"
    assert current["legal_name"] == extracted
    assert company.legal_name == "Grid Switchgear India Limited"
    assert (
        profile.identity_match_status == IdentityMatchStatus.MATCHED
    )  # historical source untouched
    assert any(item["type"] == "COMPANY_NAME" for item in payload["conflicts"]) == (
        expected != "MATCHED"
    )
    if expected != "MATCHED":
        assert payload["sections"]["company_profile"]["status"] == "NEEDS_REVIEW"
        assert current["status"] in {"CONFLICTING", "NEEDS_REVIEW"}


def test_current_domain_supersedes_old_five_cs_without_deleting_lineage(
    db_session: Session, tmp_path: Path
):
    from app.models.five_cs import FiveCsAssessment, FiveCsEvidence, FiveCsSection
    from app.models.research import ResearchRun
    from tests.test_day22_stock import _stock_context

    case, admin, _, _ = _stock_context(db_session)
    company = db_session.get(Company, case.company_id)
    old_evidence = list(
        db_session.scalars(
            select(FiveCsEvidence).where(
                FiveCsEvidence.observation_code == "CONDITIONS_DOMAIN_UNVERIFIED"
            )
        )
    )
    assert old_evidence
    old_values = [(item.id, item.description, item.five_cs_section_id) for item in old_evidence]
    service = CompanyIntelligenceReportService(db_session, tmp_path)
    stale, _, _ = service.build_snapshot(company.id, None, datetime.now(UTC).date(), True, False)
    assert stale["sections"]["credit"]["data"]["five_cs"] is None
    assert any(item["type"] == "STALE_FIVE_CS_LINEAGE" for item in stale["conflicts"])
    fresh_five, fresh_research = _rebuild_current_credit(db_session, company)
    # Deliberately make obsolete runs newer; lineage must still win.
    for old in db_session.scalars(
        select(FiveCsAssessment).where(FiveCsAssessment.domain_classification_id.is_(None))
    ):
        old.created_at = datetime.now(UTC)
    for old in db_session.scalars(
        select(ResearchRun).where(ResearchRun.domain_classification_id.is_(None))
    ):
        old.created_at = datetime.now(UTC)
        old.refresh_number += 100
    db_session.flush()
    report = service.generate(company.id, admin.id)
    stored = db_session.scalar(
        select(ReportSnapshot).where(ReportSnapshot.generated_report_id == report.id)
    )
    payload = stored.payload_json
    data = payload["sections"]["credit"]["data"]
    assert data["five_cs"]["id"] == str(fresh_five)
    assert data["research"]["id"] == str(fresh_research)
    assert data["recommendation"]["five_cs_assessment_id"] == str(fresh_five)
    assert "CONDITIONS_DOMAIN_UNVERIFIED" not in json.dumps(payload)
    assert "DOMAIN_CLASSIFICATION_REVIEW_REQUIRED" not in json.dumps(payload)
    assert [
        (item.id, item.description, item.five_cs_section_id) for item in old_evidence
    ] == old_values
    assert all(db_session.get(FiveCsEvidence, item[0]) for item in old_values)
    historical_ids = {str(item.id) for item in old_evidence}
    assert not historical_ids.intersection({item["id"] for item in data["five_cs_evidence"]})
    assert data["excluded_historical_sources"]
    original_snapshot = json.dumps(payload, sort_keys=True)
    from app.models.five_cs import FiveCsReviewItem

    future_review = FiveCsReviewItem(
        five_cs_assessment_id=fresh_five,
        section="CONDITIONS",
        reason_code="DOMAIN_CLASSIFICATION_REVIEW_REQUIRED",
        message="Future review record",
        priority="HIGH",
        status="OPEN",
        created_at=datetime.now(UTC) + timedelta(days=1),
        updated_at=datetime.now(UTC) + timedelta(days=1),
    )
    db_session.add(future_review)
    db_session.flush()
    historical, _, _ = service.build_snapshot(
        company.id, None, datetime.now(UTC).date(), True, False
    )
    assert historical["sections"]["credit"]["data"]["five_cs"]["id"] == str(fresh_five)
    assert not any(item["type"] == "DOMAIN_EVIDENCE_CONFLICT" for item in historical["conflicts"])
    # An imported contradiction linked to the current domain is detected, not hidden.
    current_section = db_session.scalar(
        select(FiveCsSection).where(
            FiveCsSection.five_cs_assessment_id == fresh_five, FiveCsSection.section == "CONDITIONS"
        )
    )
    evidence = db_session.scalar(
        select(FiveCsEvidence).where(FiveCsEvidence.five_cs_section_id == current_section.id)
    )
    original_code = evidence.observation_code
    evidence.observation_code = "CONDITIONS_DOMAIN_UNVERIFIED"
    db_session.flush()
    conflict, _, _ = service.build_snapshot(company.id, None, datetime.now(UTC).date(), True, False)
    assert any(item["type"] == "DOMAIN_EVIDENCE_CONFLICT" for item in conflict["conflicts"])
    assert conflict["sections"]["credit"]["data"]["five_cs"] is None
    assert json.dumps(stored.payload_json, sort_keys=True) == original_snapshot
    evidence.observation_code = original_code
    future_review.created_at = datetime.now(UTC)
    future_review.updated_at = datetime.now(UTC)
    db_session.flush()
    current, _, _ = service.build_snapshot(company.id, None, datetime.now(UTC).date(), True, False)
    assert any(item["type"] == "DOMAIN_EVIDENCE_CONFLICT" for item in current["conflicts"])
