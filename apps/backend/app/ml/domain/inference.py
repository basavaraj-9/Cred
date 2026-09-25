import hashlib
import logging
from pathlib import Path
from uuid import UUID

import joblib  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import AppError
from app.database.repositories.audit_log import write_audit_log
from app.ml.domain.taxonomy import Taxonomy, load_taxonomy
from app.ml.domain.text_builder import INPUT_BUILDER_VERSION, build_from_fields, text_hash
from app.models.company_profile import CompanyProfile
from app.models.domain_classification import DomainClassification, DomainClassificationEvidence
from app.models.enums import ClassificationStatus, ProfileStatus
from app.models.extracted_field import ExtractedField
from app.models.ml import MLDataset, MLModel
from app.schemas.domain_classification import (
    ClassificationEvidenceResponse,
    DomainClassificationResponse,
    LabelConfidence,
)

logger = logging.getLogger(__name__)
TASK_TYPE = "DOMAIN_CLASSIFICATION"


def _active_model(session: Session) -> MLModel:
    model = session.scalar(
        select(MLModel).where(MLModel.task_type == TASK_TYPE, MLModel.is_active.is_(True))
    )
    if model is None:
        raise AppError("DOMAIN_MODEL_UNAVAILABLE", "No active domain model is available", 503)
    return model


def _model_path(settings: Settings, uri: str) -> Path:
    prefix = "local://models/domain/"
    if not uri.startswith(prefix):
        raise AppError("MODEL_ARTIFACT_UNAVAILABLE", "Domain model artifact is unavailable", 503)
    relative = uri.removeprefix("local://")
    path = (settings.storage_root / relative).resolve()
    if not path.is_relative_to(settings.storage_root) or path.suffix != ".joblib":
        raise AppError("MODEL_ARTIFACT_UNAVAILABLE", "Domain model artifact is unavailable", 503)
    return path


def _load_model(settings: Settings, model: MLModel, taxonomy: Taxonomy):
    if (
        model.taxonomy_version != taxonomy.version
        or model.input_builder_version != INPUT_BUILDER_VERSION
    ):
        raise AppError(
            "MODEL_TAXONOMY_MISMATCH",
            "Model taxonomy or input builder version is incompatible",
            409,
        )
    path = _model_path(settings, model.artifact_uri)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != model.artifact_sha256:
        raise AppError("MODEL_ARTIFACT_UNAVAILABLE", "Domain model artifact is unavailable", 503)
    try:
        return joblib.load(path)
    except Exception as exc:
        logger.error("Could not load domain model: %s error=%s", model.id, type(exc).__name__)
        raise AppError(
            "MODEL_ARTIFACT_UNAVAILABLE", "Domain model artifact is unavailable", 503
        ) from None


def _response(row: DomainClassification, *, stale: bool = False) -> DomainClassificationResponse:
    return DomainClassificationResponse(
        classification_id=row.id,
        company_profile_id=row.company_profile_id,
        sector=LabelConfidence(label=row.sector, confidence=row.sector_confidence),
        industry=LabelConfidence(label=row.industry, confidence=row.industry_confidence),
        domain=LabelConfidence(label=row.domain, confidence=row.domain_confidence),
        sub_domain=LabelConfidence(label=row.sub_domain, confidence=row.sub_domain_confidence),
        overall_confidence=row.overall_confidence,
        status=row.status,
        alternative_sub_domain=LabelConfidence(
            label=row.alternative_sub_domain, confidence=row.alternative_confidence
        )
        if row.alternative_sub_domain is not None and row.alternative_confidence is not None
        else None,
        taxonomy_version=row.taxonomy_version,
        model_version=row.model_version,
        dataset_version=row.dataset_version,
        input_builder_version=row.input_builder_version,
        input_text_hash=row.input_text_hash,
        stale=stale,
    )


def _level_confidence(
    classes: list[str],
    probabilities: list[float],
    taxonomy: Taxonomy,
    path: tuple[str, str, str, str],
    level: int,
) -> float:
    return round(
        sum(
            probability
            for label, probability in zip(classes, probabilities)
            if taxonomy.path_for(label)[level] == path[level]
        ),
        4,
    )


def _classify_profile(
    session: Session, settings: Settings, profile_id: UUID
) -> DomainClassificationResponse:
    with session.begin():
        profile = session.get(CompanyProfile, profile_id, with_for_update=True)
        if profile is None:
            raise AppError("PROFILE_NOT_FOUND", "Company profile not found", 404)
        fields = list(
            session.scalars(
                select(ExtractedField).where(ExtractedField.company_profile_id == profile_id)
            ).all()
        )
        input_text, used = build_from_fields(fields)
        if not input_text or not used:
            raise AppError(
                "INSUFFICIENT_BUSINESS_EVIDENCE", "Verified business evidence is required", 409
            )
        input_digest = text_hash(input_text)
        active = _active_model(session)
        taxonomy = load_taxonomy()
        if (
            active.taxonomy_version != taxonomy.version
            or active.input_builder_version != INPUT_BUILDER_VERSION
        ):
            raise AppError(
                "MODEL_TAXONOMY_MISMATCH",
                "Model taxonomy or input builder version is incompatible",
                409,
            )
        existing = session.scalar(
            select(DomainClassification).where(
                DomainClassification.company_profile_id == profile_id,
                DomainClassification.model_id == active.id,
                DomainClassification.input_text_hash == input_digest,
                DomainClassification.input_builder_version == INPUT_BUILDER_VERSION,
            )
        )
        if existing is not None:
            return _response(existing)
        model = _load_model(settings, active, taxonomy)
        write_audit_log(
            session,
            entity_type="company_profile",
            entity_id=profile_id,
            action="DOMAIN_CLASSIFICATION_STARTED",
            event_type="DOMAIN_CLASSIFICATION_STARTED",
            company_id=profile.company_id,
            analysis_job_id=profile.analysis_job_id,
            metadata_json={
                "model_version": active.model_version,
                "taxonomy_version": taxonomy.version,
            },
        )
        probabilities = [float(value) for value in model.predict_proba([input_text])[0]]
        classes = [str(value) for value in model.classes_]
        if any(not any(path[3] == label for path in taxonomy.paths) for label in classes):
            raise AppError(
                "MODEL_TAXONOMY_MISMATCH", "Model predicts a label outside the taxonomy", 409
            )
        ranking = sorted(zip(classes, probabilities), key=lambda item: item[1], reverse=True)
        label, top_probability = ranking[0]
        try:
            path = taxonomy.path_for(label)
        except ValueError:
            raise AppError(
                "MODEL_TAXONOMY_MISMATCH", "Model predicts a label outside the taxonomy", 409
            ) from None
        level_scores = [
            _level_confidence(classes, probabilities, taxonomy, path, level) for level in range(4)
        ]
        overall = min(level_scores)
        second = ranking[1] if len(ranking) > 1 else None
        ambiguous = second is not None and second[1] >= 0.25 and top_probability - second[1] < 0.20
        if (
            overall >= settings.domain_verified_threshold
            and not ambiguous
            and profile.status == ProfileStatus.VERIFIED
        ):
            status = ClassificationStatus.VERIFIED
        elif (
            overall >= settings.domain_review_threshold
            or ambiguous
            or profile.status != ProfileStatus.VERIFIED
        ):
            status = ClassificationStatus.NEEDS_REVIEW
        else:
            status = ClassificationStatus.UNAVAILABLE
        dataset = session.get(MLDataset, active.dataset_id)
        assert dataset is not None
        row = DomainClassification(
            analysis_job_id=profile.analysis_job_id,
            company_id=profile.company_id,
            document_id=profile.document_id,
            company_profile_id=profile.id,
            model_id=active.id,
            sector=path[0],
            industry=path[1],
            domain=path[2],
            sub_domain=path[3],
            sector_confidence=level_scores[0],
            industry_confidence=level_scores[1],
            domain_confidence=level_scores[2],
            sub_domain_confidence=level_scores[3],
            overall_confidence=overall,
            status=status,
            alternative_sub_domain=second[0] if ambiguous and second is not None else None,
            alternative_confidence=round(second[1], 4)
            if ambiguous and second is not None
            else None,
            taxonomy_version=taxonomy.version,
            model_version=active.model_version,
            dataset_version=dataset.version,
            input_builder_version=INPUT_BUILDER_VERSION,
            input_text_hash=input_digest,
        )
        session.add(row)
        session.flush()
        for field in used:
            session.add(
                DomainClassificationEvidence(
                    domain_classification_id=row.id,
                    extracted_field_id=field.id,
                    document_page_id=field.document_page_id,
                    evidence_role=field.field_name.upper(),
                )
            )
        event = (
            "DOMAIN_CLASSIFICATION_COMPLETED"
            if status == ClassificationStatus.VERIFIED
            else "DOMAIN_CLASSIFICATION_REVIEW_REQUIRED"
        )
        write_audit_log(
            session,
            entity_type="domain_classification",
            entity_id=row.id,
            action=event,
            event_type=event,
            company_id=profile.company_id,
            analysis_job_id=profile.analysis_job_id,
            metadata_json={
                "model_version": active.model_version,
                "dataset_version": dataset.version,
                "taxonomy_version": taxonomy.version,
                "overall_confidence": overall,
                "status": status.value,
            },
        )
        logger.info(
            "Domain classification completed: profile=%s status=%s confidence=%.4f evidence=%s",
            profile_id,
            status,
            overall,
            len(used),
        )
        return _response(row)


def _record_failure(session: Session, profile_id: UUID, error_code: str) -> None:
    try:
        with session.begin():
            profile = session.get(CompanyProfile, profile_id)
            if profile is not None:
                write_audit_log(
                    session,
                    entity_type="company_profile",
                    entity_id=profile_id,
                    action="DOMAIN_CLASSIFICATION_FAILED",
                    event_type="DOMAIN_CLASSIFICATION_FAILED",
                    company_id=profile.company_id,
                    analysis_job_id=profile.analysis_job_id,
                    metadata_json={"error_code": error_code},
                )
    except Exception:
        logger.error("Could not record domain classification failure: %s", profile_id)


def classify_profile(
    session: Session, settings: Settings, profile_id: UUID
) -> DomainClassificationResponse:
    try:
        return _classify_profile(session, settings, profile_id)
    except AppError as exc:
        session.rollback()
        if exc.code not in {"PROFILE_NOT_FOUND", "INSUFFICIENT_BUSINESS_EVIDENCE"}:
            _record_failure(session, profile_id, exc.code)
        raise
    except Exception as exc:
        session.rollback()
        logger.error("Domain classification failed: %s error=%s", profile_id, type(exc).__name__)
        _record_failure(session, profile_id, "DOMAIN_CLASSIFICATION_FAILED")
        raise AppError(
            "DOMAIN_CLASSIFICATION_FAILED", "Domain classification failed", 500
        ) from None


def get_classification(session: Session, profile_id: UUID) -> DomainClassificationResponse:
    with session.begin():
        profile = session.get(CompanyProfile, profile_id)
        if profile is None:
            raise AppError("PROFILE_NOT_FOUND", "Company profile not found", 404)
        row = session.scalar(
            select(DomainClassification)
            .where(DomainClassification.company_profile_id == profile_id)
            .order_by(DomainClassification.created_at.desc())
        )
        if row is None:
            raise AppError("CLASSIFICATION_NOT_FOUND", "Domain classification not found", 404)
        fields = list(
            session.scalars(
                select(ExtractedField).where(ExtractedField.company_profile_id == profile_id)
            ).all()
        )
        current_text, _ = build_from_fields(fields)
        return _response(row, stale=text_hash(current_text) != row.input_text_hash)


def get_evidence(session: Session, classification_id: UUID) -> list[ClassificationEvidenceResponse]:
    with session.begin():
        if session.get(DomainClassification, classification_id) is None:
            raise AppError("CLASSIFICATION_NOT_FOUND", "Domain classification not found", 404)
        links = list(
            session.scalars(
                select(DomainClassificationEvidence).where(
                    DomainClassificationEvidence.domain_classification_id == classification_id
                )
            ).all()
        )
        result = []
        for link in links:
            field = session.get(ExtractedField, link.extracted_field_id)
            assert field is not None
            result.append(
                ClassificationEvidenceResponse(
                    extracted_field_id=field.id,
                    document_page_id=field.document_page_id,
                    document_id=field.document_id,
                    page_number=field.page_number,
                    field_name=field.field_name,
                    evidence_role=link.evidence_role,
                    evidence_text=field.evidence_text,
                    confidence_score=field.confidence_score,
                )
            )
        return result
