from pathlib import Path
from typing import cast

from fastapi import APIRouter, Request
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.core.constants import PLANNED_COMPONENTS
from app.database.health import check_database
from app.database.session import get_engine
from app.ml.domain.dataset import DATASET_PATH
from app.models.ml import MLModel
from app.schemas.system import ApplicationInfo, ComponentStatus, StatusResponse
from app.services.document_intelligence.ocr import ocr_state
from app.services.storage.service import check_storage

router = APIRouter(tags=["system"])


def _financial_schema_ready(database_url: str | None) -> bool:
    if not database_url:
        return False
    try:
        return {
            "financial_extraction_runs",
            "financial_statements",
            "financial_line_items",
            "financial_analysis_runs",
            "normalized_financial_values",
            "financial_validation_issues",
            "financial_ratios",
            "financial_ratio_inputs",
            "financial_trend_runs",
            "financial_trends",
            "financial_trend_inputs",
            "financial_anomalies",
            "financial_anomaly_inputs",
            "credit_assessments",
            "credit_assessment_inputs",
            "credit_subscores",
            "credit_rule_results",
            "credit_ml_observations",
            "credit_outcomes",
            "credit_ml_feature_snapshots",
            "credit_ml_feature_sources",
            "credit_ml_examples",
            "credit_ml_dataset_reports",
            "credit_ml_evaluation_runs",
            "credit_ml_evaluation_windows",
            "credit_ml_window_model_results",
            "credit_ml_drift_results",
            "credit_rule_ml_comparisons",
            "credit_fusion_experiments",
            "credit_fusion_contributions",
            "credit_fusion_reasons",
            "credit_fusion_inputs",
            "five_cs_assessments",
            "five_cs_sections",
            "five_cs_evidence",
            "five_cs_review_items",
            "research_runs",
            "research_queries",
            "research_sources",
            "research_evidence",
            "research_findings",
            "research_finding_sources",
            "five_cs_refresh_runs",
            "five_cs_research_evidence_links",
            "credit_recommendation_preparations",
            "credit_recommendation_factors",
            "credit_recommendation_review_items",
            "credit_decision_support",
            "credit_decision_gates",
            "credit_policy_exceptions",
            "credit_decision_review_items",
            "credit_limit_preparations",
            "credit_limit_methods",
            "credit_review_cases",
            "credit_review_assignments",
            "credit_review_comments",
            "credit_review_evidence_acknowledgements",
            "credit_review_checklist_actions",
            "credit_information_requests",
            "credit_policy_exception_actions",
            "credit_human_decisions",
            "credit_decision_overrides",
            "credit_committee_packages",
            "credit_committee_package_sections",
            "generated_reports",
            "report_snapshots",
            "report_artifacts",
            "report_source_links",
            "report_finalization_actions",
            "rag_index_runs",
            "rag_chunks",
            "rag_embeddings",
            "analyst_chat_sessions",
            "analyst_chat_messages",
            "rag_query_runs",
            "rag_retrieval_results",
            "rag_answers",
            "rag_answer_citations",
            "rag_answer_feedback",
            "listed_companies",
            "stock_listings",
            "peer_groups",
            "peer_group_members",
            "market_data_runs",
            "stock_prices",
            "market_data_errors",
            "stock_fundamental_runs",
            "stock_fundamentals",
            "stock_valuation_runs",
            "stock_valuations",
            "stock_valuation_inputs",
            "sector_metric_runs",
            "sector_metrics",
            "stock_feature_runs",
            "stock_features",
            "stock_feature_inputs",
        }.issubset(inspect(get_engine(database_url)).get_table_names())
    except Exception:
        return False


def _domain_model_ready(database_url: str | None, storage_root: Path) -> bool:
    if not database_url:
        return False
    try:
        with Session(get_engine(database_url)) as session:
            model = session.scalar(
                select(MLModel).where(
                    MLModel.task_type == "DOMAIN_CLASSIFICATION", MLModel.is_active.is_(True)
                )
            )
            if model is None or not model.artifact_uri.startswith("local://models/domain/"):
                return False
            path = (storage_root / model.artifact_uri.removeprefix("local://")).resolve()
            return path.is_relative_to(storage_root) and path.is_file()
    except Exception:
        return False


@router.get("/status", response_model=StatusResponse)
def status(request: Request) -> StatusResponse:
    settings = request.app.state.settings
    database = check_database(settings.database_url)
    storage = check_storage(request)
    ingestion_ready = database == "connected" and storage == "ready"
    schema_ready = database == "connected" and _financial_schema_ready(settings.database_url)
    financial_ready = ingestion_ready and schema_ready
    components: dict[str, ComponentStatus] = {
        "api": "ready",
        "database": database,
        "file_upload": "ready" if ingestion_ready else "unavailable",
        "local_storage": cast(ComponentStatus, storage),
        "duplicate_detection": "ready" if ingestion_ready else "unavailable",
        "pdf_parsing": "ready" if ingestion_ready else "unavailable",
        "page_level_extraction": "ready" if ingestion_ready else "unavailable",
        "company_identity_extraction": "ready" if ingestion_ready else "unavailable",
        "business_profile_extraction": "ready" if ingestion_ready else "unavailable",
        "evidence_mapping": "ready" if ingestion_ready else "unavailable",
        "ocr_fallback": "ready" if ocr_state(settings) == "available" else "unavailable",
        **dict.fromkeys(PLANNED_COMPONENTS, "not_implemented"),
    }
    components["document_intelligence"] = "foundation_ready" if ingestion_ready else "unavailable"
    components["domain_ml_dataset"] = "ready" if DATASET_PATH.is_file() else "unavailable"
    components["domain_model_training"] = (
        "ready" if database == "connected" and DATASET_PATH.is_file() else "unavailable"
    )
    components["domain_classification"] = (
        "ready"
        if ingestion_ready and _domain_model_ready(settings.database_url, settings.storage_root)
        else "unavailable"
    )
    components["financial_statement_schema"] = "ready" if schema_ready else "unavailable"
    components["financial_extraction"] = "ready" if financial_ready else "unavailable"
    components["financial_engine"] = "ready" if financial_ready else "unavailable"
    components["financial_normalization"] = "ready" if financial_ready else "unavailable"
    components["financial_validation"] = "ready" if financial_ready else "unavailable"
    components["financial_ratios"] = "ready" if financial_ready else "unavailable"
    components["financial_trends"] = "ready" if financial_ready else "unavailable"
    components["financial_anomalies"] = "ready" if financial_ready else "unavailable"
    components["credit_engine"] = "ready" if financial_ready else "unavailable"
    components["rule_based_credit_risk"] = "ready" if financial_ready else "unavailable"
    components["credit_ml"] = "pipeline_validated" if financial_ready else "unavailable"
    components["five_cs"] = "ready" if financial_ready else "unavailable"
    components["five_cs_evidence_engine"] = "ready" if financial_ready else "unavailable"
    components["external_research_engine"] = "ready" if schema_ready else "unavailable"
    components["company_research"] = "ready" if schema_ready else "unavailable"
    components["legal_research"] = "ready" if schema_ready else "unavailable"
    components["rating_research"] = "ready" if schema_ready else "unavailable"
    components["promoter_research"] = "ready" if schema_ready else "unavailable"
    components["industry_sector_research"] = "ready" if schema_ready else "unavailable"
    components["external_to_five_cs_candidate_mapping"] = "ready" if schema_ready else "unavailable"
    components["automatic_five_cs_refresh"] = "not_implemented"
    components["research_enriched_five_cs"] = "ready" if schema_ready else "unavailable"
    components["credit_recommendation_preparation"] = "ready" if schema_ready else "unavailable"
    components["credit_decision_support"] = "ready" if schema_ready else "unavailable"
    components["credit_policy_gates"] = "ready" if schema_ready else "unavailable"
    components["credit_policy_exceptions"] = "ready" if schema_ready else "unavailable"
    components["proposed_limit_preparation"] = "ready" if schema_ready else "unavailable"
    components["final_human_decision"] = "not_recorded"
    components["automated_approval_rejection"] = "disabled"
    components["pricing"] = "not_implemented"
    components["human_review_workflow"] = "ready" if schema_ready else "unavailable"
    components["reviewer_assignment"] = "ready" if schema_ready else "unavailable"
    components["evidence_acknowledgement"] = "ready" if schema_ready else "unavailable"
    components["information_requests"] = "ready" if schema_ready else "unavailable"
    components["policy_exception_workflow"] = "ready" if schema_ready else "unavailable"
    components["human_decision_recording"] = "ready" if schema_ready else "unavailable"
    components["credit_committee_package"] = "ready" if schema_ready else "unavailable"
    components["facility_booking"] = "not_implemented"
    components["disbursement"] = "not_implemented"
    components["cam_pdf"] = "ready" if schema_ready else "unavailable"
    components["cam_generation"] = "ready" if schema_ready else "unavailable"
    components["committee_memo"] = "ready" if schema_ready else "unavailable"
    components["decision_evidence_pack"] = "ready" if schema_ready else "unavailable"
    components["pdf_export"] = "ready" if schema_ready else "unavailable"
    components["json_export"] = "ready" if schema_ready else "unavailable"
    components["finalized_report_versioning"] = "ready" if schema_ready else "unavailable"
    components["character_external_research"] = "ready" if schema_ready else "unavailable"
    components["collateral_valuation"] = "not_implemented"
    components["industry_research"] = "ready" if schema_ready else "unavailable"
    components["credit_decision_engine"] = "not_implemented"
    components["credit_ml_observation_layer"] = "ready" if financial_ready else "unavailable"
    components["credit_outcome_labels"] = "ready" if financial_ready else "unavailable"
    components["credit_ml_feature_snapshots"] = "ready" if financial_ready else "unavailable"
    components["credit_ml_dataset_builder"] = "ready" if financial_ready else "unavailable"
    components["credit_ml_training"] = "ready" if financial_ready else "unavailable"
    components["credit_ml_logistic_regression"] = "ready"
    components["credit_ml_random_forest"] = "ready"
    components["credit_ml_xgboost"] = "ready"
    components["credit_ml_calibration"] = "ready"
    components["credit_ml_evaluation"] = "ready"
    components["credit_ml_walk_forward_evaluation"] = "ready"
    components["credit_ml_model_stability"] = "ready"
    components["credit_ml_feature_drift"] = "ready"
    components["credit_ml_calibration_drift"] = "ready"
    components["credit_ml_rule_comparison"] = "ready"
    components["credit_ml_fusion_preparation"] = "ready"
    components["credit_fusion_architecture"] = "ready"
    components["experimental_credit_fusion"] = "experimental"
    components["production_credit_fusion"] = "unavailable"
    components["credit_ml_model_registry"] = "ready" if schema_ready else "unavailable"
    components["production_credit_ml"] = "unavailable"
    components["credit_ml_rule_fusion"] = "ready"
    components["credit_ml_prediction"] = "ready"
    components["rag_index"] = "ready" if schema_ready else "unavailable"
    components["hybrid_retrieval"] = "ready" if schema_ready else "unavailable"
    components["company_intelligence_qa"] = "ready" if schema_ready else "unavailable"
    components["credit_analyst_assistant"] = "ready" if schema_ready else "unavailable"
    components["citation_validation"] = "ready" if schema_ready else "unavailable"
    components["prompt_injection_defense"] = "ready" if schema_ready else "unavailable"
    components["production_ml_decisioning"] = "disabled"
    components["autonomous_lending_decision"] = "disabled"
    components["indian_listed_universe"] = "ready" if schema_ready else "unavailable"
    components["nse_bse_mapping"] = "ready" if schema_ready else "unavailable"
    components["peer_discovery"] = "ready" if schema_ready else "unavailable"
    components["peer_similarity_explainability"] = "ready" if schema_ready else "unavailable"
    components["market_data_foundation"] = "ready" if schema_ready else "unavailable"
    components["stock_fundamentals"] = "ready" if schema_ready else "unavailable"
    components["valuation"] = "ready" if schema_ready else "unavailable"
    components["peer_relative_metrics"] = "ready" if schema_ready else "unavailable"
    components["sector_metrics"] = "ready" if schema_ready else "unavailable"
    components["historical_feature_store"] = "ready" if schema_ready else "unavailable"
    components["stock_ml"] = "not_implemented"
    components["stock_intelligence_score"] = "not_implemented"
    components["buy_sell_hold"] = "disabled"
    components["target_price"] = "disabled"
    return StatusResponse(
        application=ApplicationInfo(
            name=settings.app_name,
            version=settings.app_version,
            environment=settings.app_env,
        ),
        components=components,
        development_stage={
            "day": 23,
            "name": "Stock Fundamentals + Valuation + Historical Feature Store",
        },
        core_models={
            "user": "ready",
            "company": "ready",
            "analysis_job": "ready",
            "document_metadata": "ready",
            "audit_log": "ready",
            "company_profile": "ready",
            "extracted_field": "ready",
            "ml_dataset": "ready",
            "ml_run": "ready",
            "ml_metric": "ready",
            "ml_model": "ready",
            "domain_classification": "ready",
            "financial_extraction_run": "ready",
            "financial_statement": "ready",
            "financial_line_item": "ready",
            "financial_analysis_run": "ready",
            "normalized_financial_value": "ready",
            "financial_validation_issue": "ready",
            "financial_ratio": "ready",
            "financial_ratio_input": "ready",
            "financial_trend_run": "ready",
            "financial_trend": "ready",
            "financial_trend_input": "ready",
            "financial_anomaly": "ready",
            "financial_anomaly_input": "ready",
            "credit_assessment": "ready",
            "credit_assessment_input": "ready",
            "credit_subscore": "ready",
            "credit_rule_result": "ready",
            "credit_ml_observation": "ready",
            "credit_outcome": "ready",
            "credit_ml_feature_snapshot": "ready",
            "credit_ml_feature_source": "ready",
            "credit_ml_example": "ready",
            "credit_ml_dataset_report": "ready",
            "credit_ml_evaluation_run": "ready",
            "credit_ml_evaluation_window": "ready",
            "credit_ml_window_model_result": "ready",
            "credit_ml_drift_result": "ready",
            "credit_rule_ml_comparison": "ready",
            "credit_fusion_experiment": "ready",
            "credit_fusion_contribution": "ready",
            "credit_fusion_reason": "ready",
            "credit_fusion_input": "ready",
            "five_cs_assessment": "ready",
            "five_cs_section": "ready",
            "five_cs_evidence": "ready",
            "five_cs_review_item": "ready",
            "research_run": "ready",
            "research_query": "ready",
            "research_source": "ready",
            "research_evidence": "ready",
            "research_finding": "ready",
            "research_finding_source": "ready",
            "five_cs_refresh_run": "ready",
            "five_cs_research_evidence_link": "ready",
            "credit_recommendation_preparation": "ready",
            "credit_recommendation_factor": "ready",
            "credit_recommendation_review_item": "ready",
            "credit_decision_support": "ready",
            "credit_decision_gate": "ready",
            "credit_policy_exception": "ready",
            "credit_decision_review_item": "ready",
            "credit_limit_preparation": "ready",
            "credit_limit_method": "ready",
            "credit_review_case": "ready",
            "credit_review_comment": "ready",
            "credit_information_request": "ready",
            "credit_human_decision": "ready",
            "credit_committee_package": "ready",
            "generated_report": "ready",
            "report_snapshot": "ready",
            "report_artifact": "ready",
            "report_source_link": "ready",
            "report_finalization_action": "ready",
            "rag_index_run": "ready",
            "rag_chunk": "ready",
            "rag_embedding": "ready",
            "analyst_chat_session": "ready",
            "analyst_chat_message": "ready",
            "rag_query_run": "ready",
            "rag_retrieval_result": "ready",
            "rag_answer": "ready",
            "rag_answer_citation": "ready",
            "rag_answer_feedback": "ready",
            "listed_company": "ready",
            "stock_listing": "ready",
            "peer_group": "ready",
            "peer_group_member": "ready",
            "market_data_run": "ready",
            "stock_price": "ready",
            "market_data_error": "ready",
            "stock_fundamental_run": "ready",
            "stock_fundamental": "ready",
            "stock_valuation_run": "ready",
            "stock_valuation": "ready",
            "stock_valuation_input": "ready",
            "sector_metric_run": "ready",
            "sector_metric": "ready",
            "stock_feature_run": "ready",
            "stock_feature": "ready",
            "stock_feature_input": "ready",
        },
    )
