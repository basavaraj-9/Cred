from fastapi import APIRouter

from app.api.v1 import (
    company_profiles,
    credit_decision,
    credit_fusion,
    credit_ml_datasets,
    credit_ml_evaluations,
    credit_ml_models,
    credit_recommendation,
    credit_review,
    credit_risk,
    documents,
    domain_classification,
    financial_analysis,
    financial_statements,
    financial_trends,
    five_cs,
    health,
    research,
    status,
)

router = APIRouter()
router.include_router(health.router)
router.include_router(status.router)
router.include_router(documents.router)
router.include_router(company_profiles.router)
router.include_router(domain_classification.router)
router.include_router(financial_statements.router)
router.include_router(financial_analysis.router)
router.include_router(financial_trends.router)
router.include_router(credit_risk.router)
router.include_router(credit_ml_datasets.router)
router.include_router(credit_ml_models.router)
router.include_router(credit_ml_evaluations.router)
router.include_router(credit_fusion.router)
router.include_router(credit_decision.router)
router.include_router(credit_recommendation.router)
router.include_router(credit_review.router)
router.include_router(five_cs.router)
router.include_router(research.router)
