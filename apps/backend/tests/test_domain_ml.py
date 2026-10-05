import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.session import get_db
from app.main import create_app
from app.ml.domain.dataset import DATASET_PATH, assert_no_leakage, load_dataset, split_by_company
from app.ml.domain.taxonomy import load_taxonomy
from app.ml.domain.text_builder import INPUT_BUILDER_VERSION, build_text, text_hash
from app.ml.domain.train import run_training, train_candidates
from app.models import (
    AnalysisJob,
    AuditLog,
    Company,
    CompanyProfile,
    Document,
    DocumentPage,
    DomainClassification,
    DomainClassificationEvidence,
    ExtractedField,
    MLDataset,
    MLMetric,
    MLModel,
    MLRun,
)
from app.models.enums import (
    DocumentStatus,
    FieldStatus,
    IdentityMatchStatus,
    PageExtractionMethod,
    ParserStatus,
    ProfileStatus,
)


def test_taxonomy_loads_and_has_valid_hierarchy() -> None:
    taxonomy = load_taxonomy()
    assert taxonomy.version == "domain_taxonomy_v1"
    assert taxonomy.counts()["sectors"] >= 16
    assert taxonomy.path_for("Transformers & Switchgear") == (
        "Industrials",
        "Electrical Equipment",
        "Power Equipment",
        "Transformers & Switchgear",
    )
    assert taxonomy.path_for("Refining & Marketing")[0] == "Energy"
    assert taxonomy.path_for("Enterprise Technology Services")[0] == "Information Technology"
    assert taxonomy.path_for("Formulations & APIs")[0] == "Healthcare"


def test_taxonomy_rejects_duplicate_and_invalid_parent(tmp_path: Path) -> None:
    from app.ml.domain.taxonomy import load_taxonomy

    path = tmp_path / "taxonomy.json"
    path.write_text(
        json.dumps({"version": "test", "paths": [["A", "B", "C", "D"], ["A", "B", "C", "D"]]})
    )
    with pytest.raises(ValueError, match="Duplicate"):
        load_taxonomy(path)
    path.write_text(
        json.dumps({"version": "test", "paths": [["A", "B", "C", "D"], ["X", "B", "C", "E"]]})
    )
    with pytest.raises(ValueError, match="multiple parents"):
        load_taxonomy(path)
    path.write_text(json.dumps({"paths": [["A", "B", "C", "D"]]}))
    with pytest.raises(ValueError, match="version"):
        load_taxonomy(path)


def test_dataset_validation_hash_and_split_reproducibility() -> None:
    taxonomy = load_taxonomy()
    rows, digest = load_dataset(DATASET_PATH, taxonomy)
    assert len(rows) == 32
    assert all(row.source == "SYNTHETIC" for row in rows)
    assert len(digest) == 64
    assert load_dataset(DATASET_PATH, taxonomy)[1] == digest
    splits = split_by_company(rows, 42)
    assert {key: len(value) for key, value in splits.items()} == {
        "train": 24,
        "validation": 4,
        "test": 4,
    }
    assert split_by_company(rows, 42) == splits
    assert_no_leakage(splits)
    bad = dict(splits)
    bad["test"] = splits["test"] + [splits["train"][0]]
    with pytest.raises(ValueError, match="leakage"):
        assert_no_leakage(bad)
    copied_document = dict(splits)
    copied_document["test"] = [
        splits["test"][0].model_copy(update={"document_key": splits["train"][0].document_key}),
        *splits["test"][1:],
    ]
    with pytest.raises(ValueError, match="document"):
        assert_no_leakage(copied_document)


def test_dataset_rejects_wrong_label_and_version(tmp_path: Path) -> None:
    row = json.loads(DATASET_PATH.read_text(encoding="utf-8").splitlines()[0])
    path = tmp_path / "bad.jsonl"
    row["sub_domain"] = "Not In Taxonomy"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="taxonomy"):
        load_dataset(path, load_taxonomy())
    row["sub_domain"] = "Transformers & Switchgear"
    row["dataset_version"] = "wrong"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        load_dataset(path, load_taxonomy())


def test_input_builder_excludes_irrelevant_fields_and_hashes_deterministically() -> None:
    values = {
        "business_description": ["  Transformer manufacturer  "],
        "product": ["Switchgear"],
        "website": ["www.example.com"],
        "country": ["India"],
    }
    text = build_text(values)
    assert "transformer manufacturer" in text
    assert "switchgear" in text
    assert "example.com" not in text and "india" not in text
    assert text_hash(text) == text_hash(build_text(values))
    assert INPUT_BUILDER_VERSION == "domain_input_builder_v1"


def test_both_model_candidates_train_and_metrics_are_measured() -> None:
    taxonomy = load_taxonomy()
    rows, _ = load_dataset(DATASET_PATH, taxonomy)
    selected, model, reports = train_candidates(split_by_company(rows), taxonomy)
    assert selected in {"tfidf_logistic_regression", "tfidf_calibrated_linear_svm"}
    assert set(reports) == {"tfidf_logistic_regression", "tfidf_calibrated_linear_svm"}
    assert "test" in reports[selected]
    assert 0 <= reports[selected]["test"]["full_path_accuracy"] <= 1
    assert len(model.predict_proba([rows[0].input_text()])[0]) == 4


@pytest.fixture(scope="module")
def trained_model(
    database_engine: Engine, test_url: str, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[tuple[Settings, dict[str, object]]]:
    root = tmp_path_factory.mktemp("domain_model")
    settings = Settings(
        _env_file=None,
        app_env="test",
        test_database_url=test_url,
        database_url=test_url,
        local_storage_path=root,
        ocr_enabled=False,
    )
    report = run_training(settings, version=f"domain_classifier_test_{uuid4().hex[:10]}")
    yield settings, report
    with Session(database_engine) as session, session.begin():
        model = session.scalar(
            select(MLModel).where(MLModel.model_version == report["model_version"])
        )
        runs = session.scalars(
            select(MLRun).where(MLRun.model_version == report["model_version"])
        ).all()
        run_ids = [run.id for run in runs]
        entity_ids = run_ids + ([model.id] if model is not None else [])
        if entity_ids:
            session.execute(delete(AuditLog).where(AuditLog.entity_id.in_(entity_ids)))
        if model is not None:
            session.delete(model)
            session.flush()
        if run_ids:
            session.execute(delete(MLMetric).where(MLMetric.run_id.in_(run_ids)))
            session.execute(delete(MLRun).where(MLRun.id.in_(run_ids)))
        dataset = session.scalar(select(MLDataset).where(MLDataset.version == "domain_dataset_v1"))
        if (
            dataset is not None
            and session.scalar(
                select(func.count()).select_from(MLRun).where(MLRun.dataset_id == dataset.id)
            )
            == 0
        ):
            session.delete(dataset)


def test_training_registry_metrics_and_artifact(
    trained_model: tuple[Settings, dict[str, object]], database_engine: Engine
) -> None:
    settings, report = trained_model
    path = settings.storage_root / report["artifact_uri"].removeprefix("local://")
    assert path.is_file()
    metadata = json.loads((path.parent / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["dataset_version"] == "domain_dataset_v1"
    assert metadata["taxonomy_version"] == "domain_taxonomy_v1"
    assert metadata["input_builder_version"] == INPUT_BUILDER_VERSION
    with Session(database_engine) as session:
        model = session.scalar(
            select(MLModel).where(MLModel.model_version == report["model_version"])
        )
        assert model is not None and model.is_active
        dataset = session.get(MLDataset, model.dataset_id)
        assert (
            dataset is not None
            and dataset.record_count == 32
            and dataset.sha256_hash == report["dataset_sha256"]
        )
        runs = session.scalars(
            select(MLRun).where(MLRun.model_version == report["model_version"])
        ).all()
        assert len(runs) == 2 and all(run.status.value == "COMPLETED" for run in runs)
        assert (
            session.scalar(
                select(func.count()).select_from(MLMetric).where(MLMetric.run_id == model.run_id)
            )
            > 0
        )


@dataclass
class Context:
    client: TestClient
    connection: Connection
    settings: Settings

    def profile(
        self, description: str, products: list[str], *, company: str = "Synthetic Company Ltd"
    ) -> str:
        with Session(self.connection, join_transaction_mode="create_savepoint") as session:
            company_row = Company(legal_name=company)
            session.add(company_row)
            session.flush()
            job = AnalysisJob(company_id=company_row.id)
            session.add(job)
            session.flush()
            doc = Document(
                company_id=company_row.id,
                analysis_job_id=job.id,
                original_filename="report.pdf",
                status=DocumentStatus.UPLOADED,
                parser_status=ParserStatus.PARSED,
                sha256_hash=uuid4().hex,
            )
            session.add(doc)
            session.flush()
            page = DocumentPage(
                document_id=doc.id,
                page_number=1,
                text_content=description + "\n" + ", ".join(products),
                extraction_method=PageExtractionMethod.NATIVE_TEXT,
                parser_version="pdf_parser_v1",
            )
            session.add(page)
            session.flush()
            profile = CompanyProfile(
                analysis_job_id=job.id,
                company_id=company_row.id,
                document_id=doc.id,
                legal_name=company,
                status=ProfileStatus.VERIFIED,
                identity_match_status=IdentityMatchStatus.MATCHED,
                extractor_version="company_profile_extractor_v1",
            )
            session.add(profile)
            session.flush()
            for field_name, value in [
                ("business_description", description),
                *(("product", item) for item in products),
            ]:
                session.add(
                    ExtractedField(
                        analysis_job_id=job.id,
                        document_id=doc.id,
                        document_page_id=page.id,
                        company_profile_id=profile.id,
                        field_group="BUSINESS_PROFILE",
                        field_name=field_name,
                        raw_value=value,
                        normalized_value=value,
                        page_number=1,
                        evidence_text=value,
                        confidence_score=0.9,
                        status=FieldStatus.VERIFIED,
                        extractor_version="company_profile_extractor_v1",
                    )
                )
            session.commit()
            return str(profile.id)

    def classify(self, profile_id: str):
        return self.client.post(f"/api/v1/company-profiles/{profile_id}/domain-classification")


@pytest.fixture
def context(
    database_engine: Engine, trained_model: tuple[Settings, dict[str, object]]
) -> Iterator[Context]:
    settings, _ = trained_model
    connection = database_engine.connect()
    outer = connection.begin()
    app = create_app(settings)

    def test_db() -> Iterator[Session]:
        with Session(connection, join_transaction_mode="create_savepoint") as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield Context(client, connection, settings)
    outer.rollback()
    connection.close()


@pytest.mark.parametrize(
    "description,products,expected",
    [
        (
            "Manufacturer of power transformers, distribution transformers and "
            "switchgear for electric grids.",
            ["Power Transformers", "Switchgear"],
            "Transformers & Switchgear",
        ),
        (
            "Operates petroleum refineries and markets diesel, gasoline and other refined fuels.",
            ["Diesel", "Gasoline"],
            "Refining & Marketing",
        ),
        (
            "Provides enterprise software development, cloud engineering and IT "
            "consulting services.",
            ["Enterprise Software", "Cloud Platforms"],
            "Enterprise Technology Services",
        ),
        (
            "Manufactures pharmaceutical formulations and active pharmaceutical "
            "ingredients for medicine.",
            ["Drug Formulations", "Active Pharmaceutical Ingredients"],
            "Formulations & APIs",
        ),
    ],
)
def test_classification_hierarchy_confidence_and_lineage(
    context: Context, description: str, products: list[str], expected: str
) -> None:
    profile_id = context.profile(description, products)
    response = context.classify(profile_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sub_domain"]["label"] == expected
    taxonomy = load_taxonomy()
    path = (
        body["sector"]["label"],
        body["industry"]["label"],
        body["domain"]["label"],
        body["sub_domain"]["label"],
    )
    assert taxonomy.contains(path)
    assert all(
        0 <= body[name]["confidence"] <= 1
        for name in ("sector", "industry", "domain", "sub_domain")
    )
    assert body["overall_confidence"] == min(
        body[name]["confidence"] for name in ("sector", "industry", "domain", "sub_domain")
    )
    assert body["taxonomy_version"] == "domain_taxonomy_v1"
    assert body["dataset_version"] == "domain_dataset_v1"
    assert body["input_builder_version"] == INPUT_BUILDER_VERSION
    assert len(body["input_text_hash"]) == 64
    evidence = context.client.get(
        f"/api/v1/domain-classifications/{body['classification_id']}/evidence"
    )
    assert evidence.status_code == 200 and len(evidence.json()) == 1 + len(products)
    assert all(item["document_page_id"] for item in evidence.json())
    assert (
        context.client.get(f"/api/v1/company-profiles/{profile_id}/domain-classification").json()
        == body
    )


def test_classification_requires_profile_and_business_evidence(context: Context) -> None:
    assert context.classify(str(uuid4())).status_code == 404
    profile_id = context.profile("No business evidence", [])
    with Session(context.connection, join_transaction_mode="create_savepoint") as session:
        for field in session.scalars(
            select(ExtractedField).where(ExtractedField.company_profile_id == UUID(profile_id))
        ):
            field.status = FieldStatus.NEEDS_REVIEW
        session.commit()
    response = context.classify(profile_id)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSUFFICIENT_BUSINESS_EVIDENCE"


def test_classification_idempotent_and_profile_isolated(context: Context) -> None:
    first_profile = context.profile(
        "Manufacturer of power transformers and switchgear for electricity networks.",
        ["Power Transformers", "Switchgear"],
    )
    other_profile = context.profile(
        "Operates petroleum refineries and markets refined fuel products.", ["Diesel"]
    )
    first = context.classify(first_profile).json()
    assert context.classify(first_profile).json() == first
    with Session(context.connection, join_transaction_mode="create_savepoint") as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(DomainClassification)
                .where(DomainClassification.company_profile_id == UUID(first_profile))
            )
            == 1
        )
        links = session.scalars(
            select(DomainClassificationEvidence).where(
                DomainClassificationEvidence.domain_classification_id
                == UUID(first["classification_id"])
            )
        ).all()
        other_ids = set(
            session.scalars(
                select(ExtractedField.id).where(
                    ExtractedField.company_profile_id == UUID(other_profile)
                )
            ).all()
        )
        assert all(link.extracted_field_id not in other_ids for link in links)


def test_changed_input_creates_new_prediction_and_old_one_is_stale(context: Context) -> None:
    profile_id = context.profile(
        "Manufacturer of power transformers and switchgear for grids.", ["Transformers"]
    )
    first = context.classify(profile_id).json()
    with Session(context.connection, join_transaction_mode="create_savepoint") as session:
        field = session.scalar(
            select(ExtractedField).where(
                ExtractedField.company_profile_id == UUID(profile_id),
                ExtractedField.field_name == "product",
            )
        )
        assert field is not None
        field.normalized_value = "Switchgear"
        session.commit()
    previous = context.client.get(
        f"/api/v1/company-profiles/{profile_id}/domain-classification"
    ).json()
    assert previous["stale"] is True
    second = context.classify(profile_id).json()
    assert second["classification_id"] != first["classification_id"]
    assert second["input_text_hash"] != first["input_text_hash"]


def test_missing_artifact_and_taxonomy_mismatch_fail_safely(context: Context) -> None:
    profile_id = context.profile(
        "Manufacturer of electrical transformers and switchgear.", ["Transformers"]
    )
    with Session(context.connection, join_transaction_mode="create_savepoint") as session:
        model = session.scalar(select(MLModel).where(MLModel.is_active.is_(True)))
        assert model is not None
        path = context.settings.storage_root / model.artifact_uri.removeprefix("local://")
        original_version = model.taxonomy_version
        model.taxonomy_version = "incompatible_taxonomy"
        session.commit()
    assert context.classify(profile_id).json()["error"]["code"] == "MODEL_TAXONOMY_MISMATCH"
    with Session(context.connection, join_transaction_mode="create_savepoint") as session:
        model = session.scalar(select(MLModel).where(MLModel.is_active.is_(True)))
        assert model is not None
        model.taxonomy_version = original_version
        session.commit()
    hidden = path.with_suffix(".hidden")
    path.rename(hidden)
    try:
        response = context.classify(profile_id)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "MODEL_ARTIFACT_UNAVAILABLE"
    finally:
        hidden.rename(path)


def test_low_information_is_not_verified(context: Context) -> None:
    profile_id = context.profile("The company is engaged in general corporate activities.", [])
    body = context.classify(profile_id).json()
    assert body["status"] != "VERIFIED"


def test_ambiguous_business_shows_alternative_and_review(context: Context) -> None:
    profile_id = context.profile(
        "Company operates petroleum refineries and provides enterprise software "
        "consulting services.",
        [],
    )
    body = context.classify(profile_id).json()
    assert body["status"] == "NEEDS_REVIEW"
    assert body["alternative_sub_domain"] is not None
    assert body["alternative_sub_domain"]["label"] != body["sub_domain"]["label"]


def test_unrelated_office_text_is_not_verified(context: Context) -> None:
    profile_id = context.profile(
        "Registered office address, board of directors and legal disclaimer details.", []
    )
    assert context.classify(profile_id).json()["status"] != "VERIFIED"


def test_failed_training_preserves_active_model(
    trained_model: tuple[Settings, dict[str, object]], database_engine: Engine
) -> None:
    settings, report = trained_model
    invalid_version = "../invalid_model_version"
    with pytest.raises(ValueError, match="Model version"):
        run_training(settings, version=invalid_version)
    with Session(database_engine) as session, session.begin():
        active = session.scalar(select(MLModel).where(MLModel.is_active.is_(True)))
        assert active is not None and active.model_version == report["model_version"]
        failed = session.scalars(select(MLRun).where(MLRun.model_version == invalid_version)).all()
        assert len(failed) == 2 and all(run.status.value == "FAILED" for run in failed)
        ids = [run.id for run in failed]
        session.execute(delete(AuditLog).where(AuditLog.entity_id.in_(ids)))
        session.execute(delete(MLRun).where(MLRun.id.in_(ids)))


def test_failed_registration_rolls_back_activation(
    trained_model: tuple[Settings, dict[str, object]],
    database_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ml.domain import train

    settings, report = trained_model
    version = f"domain_registration_failure_{uuid4().hex[:8]}"
    original_write = train.write_audit_log

    def fail_activation(*args: object, **kwargs: object):
        if kwargs.get("event_type") == "MODEL_ACTIVATED":
            raise RuntimeError("injected registration failure")
        return original_write(*args, **kwargs)

    monkeypatch.setattr(train, "write_audit_log", fail_activation)
    with pytest.raises(RuntimeError, match="registration failure"):
        run_training(settings, version=version)
    with Session(database_engine) as session, session.begin():
        active = session.scalar(select(MLModel).where(MLModel.is_active.is_(True)))
        assert active is not None and active.model_version == report["model_version"]
        assert session.scalar(select(MLModel).where(MLModel.model_version == version)) is None
        failed = session.scalars(select(MLRun).where(MLRun.model_version == version)).all()
        assert len(failed) == 2 and all(run.status.value == "FAILED" for run in failed)
        ids = [run.id for run in failed]
        session.execute(delete(AuditLog).where(AuditLog.entity_id.in_(ids)))
        session.execute(delete(MLMetric).where(MLMetric.run_id.in_(ids)))
        session.execute(delete(MLRun).where(MLRun.id.in_(ids)))


def test_classification_schema_and_status(context: Context, database_engine: Engine) -> None:
    names = set(inspect(database_engine).get_table_names())
    assert {
        "ml_datasets",
        "ml_runs",
        "ml_metrics",
        "ml_models",
        "domain_classifications",
        "domain_classification_evidence",
    } <= names
    status = context.client.get("/api/v1/status").json()
    assert status["development_stage"]["day"] == 28
    assert status["components"]["domain_ml_dataset"] == "ready"
    assert status["components"]["domain_model_training"] == "ready"
    assert status["components"]["domain_classification"] == "ready"
    assert status["components"]["financial_engine"] in {"ready", "unavailable"}
