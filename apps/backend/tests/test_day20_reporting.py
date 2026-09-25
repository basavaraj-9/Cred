from __future__ import annotations

# ruff: noqa: E501
import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.audit_log import AuditLog
from app.models.decision import CreditDecisionSupport
from app.models.reporting import ReportArtifact, ReportSnapshot, ReportSourceLink
from app.services.credit_review.service import CreditReviewService
from app.services.reporting.service import (
    DISCLAIMER,
    RENDERER_VERSION,
    TEMPLATES,
    CreditReportService,
    report_payload,
)
from tests.test_day19_credit_review import _context, _user


def _review(session: Session) -> tuple[CreditReviewService, object, object, object, object]:
    service, support, admin, reviewer, checker = _context(session)
    case = service.create_case(support.id, admin.id)
    service.assign(case.id, reviewer.id, admin.id)
    service.start(case.id, reviewer.id)
    return service, case, admin, reviewer, checker


def test_report_snapshot_pdf_hash_idempotency_lineage_and_finalization(
    db_session: Session, tmp_path: Path
) -> None:
    review, case, _, manager, _ = _review(db_session)
    reporting = CreditReportService(db_session, tmp_path)
    report = reporting.generate(case.id, manager.id, "CAM", "PDF")
    repeated = reporting.generate(case.id, manager.id, "CAM", "PDF")
    assert repeated.id == report.id and report.status == "GENERATED"
    snapshot = db_session.scalar(
        select(ReportSnapshot).where(ReportSnapshot.generated_report_id == report.id)
    )
    artifact = db_session.scalar(
        select(ReportArtifact).where(ReportArtifact.generated_report_id == report.id)
    )
    assert snapshot is not None and artifact is not None
    assert (
        snapshot.payload_hash
        == hashlib.sha256(
            json.dumps(snapshot.payload_json, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    path = tmp_path / artifact.storage_path
    assert (
        path.is_file()
        and path.stat().st_size == artifact.file_size_bytes
        and path.read_bytes().startswith(b"%PDF")
    )
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest() == artifact.sha256
        and len(artifact.sha256) == 64
    )
    assert snapshot.payload_json["decision_support"]["system_recommendation"]
    assert snapshot.payload_json["human_decision"] is None
    assert snapshot.payload_json["experimental_ml_context"]["decision_weight"] == 0
    assert "password" not in json.dumps(snapshot.payload_json).lower()
    links = list(
        db_session.scalars(
            select(ReportSourceLink).where(ReportSourceLink.generated_report_id == report.id)
        )
    )
    assert {x.source_type for x in links} >= {
        "credit_assessment",
        "five_cs_assessment",
        "decision_support",
        "credit_review_case",
    }
    analyst = _user(db_session, "CREDIT_ANALYST")
    with pytest.raises(AppError):
        reporting.finalize(report.id, analyst.id)
    reporting.finalize(report.id, manager.id, "Reviewed and approved for internal issue")
    assert report.status == "FINALIZED" and report.finalized_by_user_id == manager.id
    assert report_payload(db_session, report)["artifact"]["sha256"] == artifact.sha256
    review.comment(case.id, manager.id, "GENERAL", "New persisted review note for report v2")
    successor = reporting.generate(case.id, manager.id, "CAM", "PDF")
    assert successor.report_version == 2 and successor.id != report.id
    reporting.supersede(report.id, successor.id, manager.id, "Replaced by the newer fixed snapshot")
    assert report.status == "SUPERSEDED" and report.superseded_by_report_id == successor.id
    assert successor.supersedes_report_id == report.id


def test_cam_committee_evidence_and_json_exports_preserve_upstream(
    db_session: Session, tmp_path: Path
) -> None:
    review, case, _, manager, _ = _review(db_session)
    package = review.committee_package(case.id, manager.id)
    support = db_session.get(CreditDecisionSupport, case.decision_support_id)
    assert support is not None
    original = (support.input_hash, support.system_recommendation, support.human_decision)
    reporting = CreditReportService(db_session, tmp_path)
    cam = reporting.generate(case.id, manager.id, "CAM", "PDF")
    memo = reporting.generate(case.id, manager.id, "CREDIT_COMMITTEE_MEMO", "PDF", package.id)
    evidence = reporting.generate(case.id, manager.id, "DECISION_EVIDENCE_PACK", "PDF")
    structured = reporting.generate(case.id, manager.id, "STRUCTURED_JSON_EXPORT", "JSON")
    assert {cam.template_version, memo.template_version, evidence.template_version} == {
        TEMPLATES["CAM"],
        TEMPLATES["CREDIT_COMMITTEE_MEMO"],
        TEMPLATES["DECISION_EVIDENCE_PACK"],
    }
    assert all(x.renderer_version == RENDERER_VERSION for x in (cam, memo, evidence, structured))
    artifacts = list(
        db_session.scalars(
            select(ReportArtifact).where(
                ReportArtifact.generated_report_id.in_(
                    [cam.id, memo.id, evidence.id, structured.id]
                )
            )
        )
    )
    assert len(artifacts) == 4 and all(x.file_size_bytes > 100 for x in artifacts)
    json_artifact = next(x for x in artifacts if x.format == "JSON")
    exported = json.loads((tmp_path / json_artifact.storage_path).read_text(encoding="utf-8"))
    assert exported["disclaimer"] == DISCLAIMER and "DB credentials" not in json.dumps(exported)
    assert db_session.get(CreditDecisionSupport, support.id).input_hash == original[0]  # type: ignore[union-attr]
    assert (support.input_hash, support.system_recommendation, support.human_decision) == original


def test_report_authorized_download_integrity_and_path_traversal(
    db_session: Session, tmp_path: Path
) -> None:
    _, case, _, manager, _ = _review(db_session)
    reporting = CreditReportService(db_session, tmp_path)
    report = reporting.generate(case.id, manager.id, "DECISION_EVIDENCE_PACK", "PDF")
    _, artifact, path = reporting.authorized_artifact(report.id, manager.id)
    assert path.is_relative_to(tmp_path) and path.name == "decision-evidence-pack.pdf"
    artifact.storage_path = "../../outside.pdf"
    with pytest.raises(AppError):
        reporting.authorized_artifact(report.id, manager.id)


def test_report_missing_data_is_explicit_and_no_new_credit_judgment(
    db_session: Session, tmp_path: Path
) -> None:
    _, case, _, manager, _ = _review(db_session)
    report = CreditReportService(db_session, tmp_path).generate(case.id, manager.id, "CAM", "PDF")
    snapshot = db_session.scalar(
        select(ReportSnapshot).where(ReportSnapshot.generated_report_id == report.id)
    )
    assert snapshot is not None
    payload = snapshot.payload_json
    assert payload["human_decision"] is None
    assert payload["decision_support"]["human_decision"] is None
    assert "new_credit_score" not in payload and "pricing" not in payload
    assert payload["disclaimer"] == DISCLAIMER


def test_report_type_validation_and_committee_linkage(db_session: Session, tmp_path: Path) -> None:
    _, case, _, manager, _ = _review(db_session)
    service = CreditReportService(db_session, tmp_path)
    with pytest.raises(AppError, match="Unsupported"):
        service.generate(case.id, manager.id, "SANCTION", "PDF")
    with pytest.raises(AppError, match="committee package"):
        service.generate(case.id, manager.id, "CREDIT_COMMITTEE_MEMO", "PDF")


def test_artifact_failure_is_clean_and_audited(
    db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, case, _, manager, _ = _review(db_session)
    service = CreditReportService(db_session, tmp_path)

    def fail_renderer(*_: object) -> None:
        raise RuntimeError("synthetic renderer failure")

    monkeypatch.setattr(service, "_render_pdf", fail_renderer)
    report = service.generate(case.id, manager.id, "CAM", "PDF")
    assert report.status == "FAILED"
    assert (
        db_session.scalar(
            select(ReportArtifact).where(ReportArtifact.generated_report_id == report.id)
        )
        is None
    )
    assert not list(tmp_path.rglob("*.pdf"))
    events = set(
        db_session.scalars(
            select(AuditLog.event_type).where(
                AuditLog.entity_type == "generated_report", AuditLog.entity_id == report.id
            )
        )
    )
    assert events >= {"CREDIT_REPORT_GENERATION_STARTED", "CREDIT_REPORT_GENERATION_FAILED"}
