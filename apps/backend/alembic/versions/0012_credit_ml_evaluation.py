"""credit_ml_evaluation

Revision ID: 0012_credit_ml_evaluation
Revises: 0011_credit_ml_models
Create Date: 2026-09-24 21:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0012_credit_ml_evaluation"
down_revision: str | None = "0011_credit_ml_models"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "credit_ml_evaluation_runs",
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_version", sa.String(100), nullable=False),
        sa.Column("walk_forward_policy_version", sa.String(100), nullable=False),
        sa.Column("model_selection_policy_version", sa.String(100), nullable=False),
        sa.Column("fusion_readiness_policy_version", sa.String(100), nullable=False),
        sa.Column("drift_policy_version", sa.String(100), nullable=False),
        sa.Column("diagnostic_band_version", sa.String(100), nullable=False),
        sa.Column("mode", sa.String(50), nullable=False),
        sa.Column("window_mode", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("valid_window_count", sa.Integer(), nullable=False),
        sa.Column("skipped_window_count", sa.Integer(), nullable=False),
        sa.Column("summary_json", postgresql.JSONB(), nullable=False),
        sa.Column("fusion_readiness", sa.String(50), nullable=False),
        sa.Column("fusion_allowed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "valid_window_count >= 0",
            name=op.f("ck_credit_ml_evaluation_runs_valid_window_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "skipped_window_count >= 0",
            name=op.f("ck_credit_ml_evaluation_runs_skipped_window_count_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["ml_datasets.id"],
            name=op.f("fk_credit_ml_evaluation_runs_dataset_id_ml_datasets"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_ml_evaluation_runs")),
        sa.UniqueConstraint("input_hash", name="uq_credit_ml_evaluation_runs_input_hash"),
    )
    op.create_index(
        "ix_credit_ml_evaluation_runs_dataset_id", "credit_ml_evaluation_runs", ["dataset_id"]
    )
    op.create_index("ix_credit_ml_evaluation_runs_status", "credit_ml_evaluation_runs", ["status"])
    op.create_table(
        "credit_ml_evaluation_windows",
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=False),
        sa.Column("window_number", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(50), nullable=False),
        sa.Column("train_start", sa.Date(), nullable=True),
        sa.Column("train_end", sa.Date(), nullable=True),
        sa.Column("evaluation_start", sa.Date(), nullable=True),
        sa.Column("evaluation_end", sa.Date(), nullable=True),
        sa.Column("train_count", sa.Integer(), nullable=False),
        sa.Column("evaluation_count", sa.Integer(), nullable=False),
        sa.Column("train_positive", sa.Integer(), nullable=False),
        sa.Column("train_negative", sa.Integer(), nullable=False),
        sa.Column("evaluation_positive", sa.Integer(), nullable=False),
        sa.Column("evaluation_negative", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("skip_reason", sa.String(100), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "train_count >= 0 AND evaluation_count >= 0",
            name=op.f("ck_credit_ml_evaluation_windows_window_counts_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"],
            ["credit_ml_evaluation_runs.id"],
            name=op.f(
                "fk_credit_ml_evaluation_windows_evaluation_run_id_credit_ml_evaluation_runs"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_ml_evaluation_windows")),
        sa.UniqueConstraint(
            "evaluation_run_id", "window_number", name="uq_credit_ml_window_number"
        ),
    )
    op.create_index(
        "ix_credit_ml_windows_run_id", "credit_ml_evaluation_windows", ["evaluation_run_id"]
    )
    op.create_table(
        "credit_ml_window_model_results",
        sa.Column("evaluation_window_id", sa.Uuid(), nullable=False),
        sa.Column("model_family", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("calibration_method", sa.String(50), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("metric_summary_json", postgresql.JSONB(), nullable=False),
        sa.Column("artifact_uri", sa.String(2048), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["evaluation_window_id"],
            ["credit_ml_evaluation_windows.id"],
            name=op.f(
                "fk_credit_ml_window_model_results_evaluation_window_id_credit_ml_evaluation_windows"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_ml_window_model_results")),
        sa.UniqueConstraint(
            "evaluation_window_id", "model_family", name="uq_credit_ml_window_model_family"
        ),
    )
    op.create_index(
        "ix_credit_ml_window_results_window_id",
        "credit_ml_window_model_results",
        ["evaluation_window_id"],
    )
    op.create_table(
        "credit_ml_drift_results",
        sa.Column("evaluation_window_id", sa.Uuid(), nullable=False),
        sa.Column("feature_name", sa.String(120), nullable=True),
        sa.Column("drift_type", sa.String(50), nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("threshold_version", sa.String(100), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["evaluation_window_id"],
            ["credit_ml_evaluation_windows.id"],
            name=op.f(
                "fk_credit_ml_drift_results_evaluation_window_id_credit_ml_evaluation_windows"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_ml_drift_results")),
    )
    op.create_index(
        "ix_credit_ml_drift_window_id", "credit_ml_drift_results", ["evaluation_window_id"]
    )
    op.create_table(
        "credit_rule_ml_comparisons",
        sa.Column("evaluation_run_id", sa.Uuid(), nullable=False),
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.Column("credit_assessment_id", sa.Uuid(), nullable=True),
        sa.Column("ml_model_family", sa.String(100), nullable=False),
        sa.Column("ml_probability", sa.Float(), nullable=False),
        sa.Column("ml_predicted_class", sa.Integer(), nullable=False),
        sa.Column("rule_score", sa.Float(), nullable=True),
        sa.Column("rule_risk_index", sa.Float(), nullable=True),
        sa.Column("rule_risk_band", sa.String(50), nullable=True),
        sa.Column("ml_diagnostic_band", sa.String(50), nullable=False),
        sa.Column("agreement_status", sa.String(50), nullable=False),
        sa.Column("probability_gap", sa.Float(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "ml_probability >= 0 AND ml_probability <= 1",
            name=op.f("ck_credit_rule_ml_comparisons_ml_probability_range"),
        ),
        sa.CheckConstraint(
            "rule_risk_index IS NULL OR (rule_risk_index >= 0 AND rule_risk_index <= 1)",
            name=op.f("ck_credit_rule_ml_comparisons_rule_risk_index_range"),
        ),
        sa.ForeignKeyConstraint(
            ["credit_assessment_id"],
            ["credit_assessments.id"],
            name=op.f("fk_credit_rule_ml_comparisons_credit_assessment_id_credit_assessments"),
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"],
            ["credit_ml_evaluation_runs.id"],
            name=op.f("fk_credit_rule_ml_comparisons_evaluation_run_id_credit_ml_evaluation_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["credit_ml_observations.id"],
            name=op.f("fk_credit_rule_ml_comparisons_observation_id_credit_ml_observations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_rule_ml_comparisons")),
    )
    op.create_index(
        "ix_credit_rule_ml_comparisons_run_id", "credit_rule_ml_comparisons", ["evaluation_run_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_credit_rule_ml_comparisons_run_id", table_name="credit_rule_ml_comparisons")
    op.drop_table("credit_rule_ml_comparisons")
    op.drop_index("ix_credit_ml_drift_window_id", table_name="credit_ml_drift_results")
    op.drop_table("credit_ml_drift_results")
    op.drop_index(
        "ix_credit_ml_window_results_window_id", table_name="credit_ml_window_model_results"
    )
    op.drop_table("credit_ml_window_model_results")
    op.drop_index("ix_credit_ml_windows_run_id", table_name="credit_ml_evaluation_windows")
    op.drop_table("credit_ml_evaluation_windows")
    op.drop_index("ix_credit_ml_evaluation_runs_status", table_name="credit_ml_evaluation_runs")
    op.drop_index("ix_credit_ml_evaluation_runs_dataset_id", table_name="credit_ml_evaluation_runs")
    op.drop_table("credit_ml_evaluation_runs")
