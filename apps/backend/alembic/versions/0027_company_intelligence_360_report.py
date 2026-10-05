"""company intelligence 360 report

Revision ID: 0027_company_intelligence_360_report
Revises: 0026_stock_monitoring_governance
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0027_company_intelligence_360_report"
down_revision: str | None = "0026_stock_monitoring_governance"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("generated_reports", sa.Column("policy_version", sa.String(100)))
    op.add_column("generated_reports", sa.Column("schema_version", sa.String(100)))
    op.add_column("generated_reports", sa.Column("readiness_status", sa.String(30)))
    op.add_column("generated_reports", sa.Column("analytical_as_of_date", sa.Date()))
    op.add_column("generated_reports", sa.Column("include_credit", sa.Boolean()))
    op.add_column("generated_reports", sa.Column("include_stock", sa.Boolean()))
    op.add_column("generated_reports", sa.Column("completeness_ratio", sa.Numeric(7, 6)))
    op.add_column("generated_reports", sa.Column("evidence_coverage", sa.Numeric(7, 6)))

    for column in ("document_id", "analysis_job_id", "review_case_id", "decision_support_id"):
        op.alter_column("generated_reports", column, existing_type=sa.UUID(), nullable=True)

    op.drop_constraint(
        op.f("ck_generated_reports_report_type_valid"), "generated_reports", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_generated_reports_report_type_valid"),
        "generated_reports",
        "report_type IN ('CAM','CREDIT_COMMITTEE_MEMO','DECISION_EVIDENCE_PACK',"
        "'STRUCTURED_JSON_EXPORT','COMPANY_INTELLIGENCE_360')",
    )
    op.drop_constraint(
        op.f("ck_generated_reports_status_valid"), "generated_reports", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_generated_reports_status_valid"),
        "generated_reports",
        "status IN ('DRAFT','GENERATED','READY','NEEDS_REVIEW','FINALIZED','SUPERSEDED','FAILED')",
    )
    op.create_check_constraint(
        op.f("ck_generated_reports_readiness_valid"),
        "generated_reports",
        "readiness_status IS NULL OR readiness_status IN "
        "('COMPLETE','PARTIAL','INSUFFICIENT_DATA','NEEDS_REVIEW')",
    )
    op.create_check_constraint(
        op.f("ck_generated_reports_completeness_range"),
        "generated_reports",
        "completeness_ratio IS NULL OR completeness_ratio BETWEEN 0 AND 1",
    )
    op.create_check_constraint(
        op.f("ck_generated_reports_evidence_coverage_range"),
        "generated_reports",
        "evidence_coverage IS NULL OR evidence_coverage BETWEEN 0 AND 1",
    )
    op.create_index(
        "ix_generated_reports_as_of",
        "generated_reports",
        ["analytical_as_of_date", "report_type"],
    )
    op.create_index(
        "ix_generated_reports_company_type",
        "generated_reports",
        ["company_id", "report_type", "generated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_generated_reports_company_type", table_name="generated_reports")
    op.drop_index("ix_generated_reports_as_of", table_name="generated_reports")
    op.drop_constraint(
        op.f("ck_generated_reports_evidence_coverage_range"), "generated_reports", type_="check"
    )
    op.drop_constraint(
        op.f("ck_generated_reports_completeness_range"), "generated_reports", type_="check"
    )
    op.drop_constraint(
        op.f("ck_generated_reports_readiness_valid"), "generated_reports", type_="check"
    )
    op.drop_constraint(
        op.f("ck_generated_reports_status_valid"), "generated_reports", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_generated_reports_status_valid"),
        "generated_reports",
        "status IN ('DRAFT','GENERATED','FINALIZED','SUPERSEDED','FAILED')",
    )
    op.drop_constraint(
        op.f("ck_generated_reports_report_type_valid"), "generated_reports", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_generated_reports_report_type_valid"),
        "generated_reports",
        "report_type IN ('CAM','CREDIT_COMMITTEE_MEMO','DECISION_EVIDENCE_PACK',"
        "'STRUCTURED_JSON_EXPORT')",
    )

    for column in ("decision_support_id", "review_case_id", "analysis_job_id", "document_id"):
        op.alter_column("generated_reports", column, existing_type=sa.UUID(), nullable=False)

    op.drop_column("generated_reports", "evidence_coverage")
    op.drop_column("generated_reports", "completeness_ratio")
    op.drop_column("generated_reports", "include_stock")
    op.drop_column("generated_reports", "include_credit")
    op.drop_column("generated_reports", "analytical_as_of_date")
    op.drop_column("generated_reports", "readiness_status")
    op.drop_column("generated_reports", "schema_version")
    op.drop_column("generated_reports", "policy_version")
