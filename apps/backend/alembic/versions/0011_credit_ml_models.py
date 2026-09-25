"""credit_ml_models

Revision ID: 0011_credit_ml_models
Revises: 0010_credit_ml_dataset
Create Date: 2026-09-24 18:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011_credit_ml_models"
down_revision: str | None = "0010_credit_ml_dataset"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_ml_metrics_value_range"), "ml_metrics", type_="check")
    op.create_check_constraint(
        op.f("ck_ml_metrics_value_nonnegative"), "ml_metrics", "metric_value >= 0"
    )
    op.add_column("ml_runs", sa.Column("training_mode", sa.String(length=50), nullable=True))
    op.add_column("ml_runs", sa.Column("feature_group", sa.String(length=100), nullable=True))
    op.add_column(
        "ml_runs", sa.Column("training_config_version", sa.String(length=100), nullable=True)
    )
    op.add_column("ml_models", sa.Column("training_mode", sa.String(length=50), nullable=True))
    op.add_column(
        "ml_models", sa.Column("model_readiness_status", sa.String(length=50), nullable=True)
    )
    op.add_column("ml_models", sa.Column("lifecycle_status", sa.String(length=50), nullable=True))
    op.add_column("ml_models", sa.Column("calibration_method", sa.String(length=50), nullable=True))
    op.add_column("ml_models", sa.Column("selected_threshold", sa.Float(), nullable=True))
    op.add_column("ml_models", sa.Column("feature_group", sa.String(length=100), nullable=True))
    op.add_column(
        "ml_models", sa.Column("selection_policy_version", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "ml_models",
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ml_models", "metadata_json")
    op.drop_column("ml_models", "selection_policy_version")
    op.drop_column("ml_models", "feature_group")
    op.drop_column("ml_models", "selected_threshold")
    op.drop_column("ml_models", "calibration_method")
    op.drop_column("ml_models", "lifecycle_status")
    op.drop_column("ml_models", "model_readiness_status")
    op.drop_column("ml_models", "training_mode")
    op.drop_column("ml_runs", "training_config_version")
    op.drop_column("ml_runs", "feature_group")
    op.drop_column("ml_runs", "training_mode")
    op.drop_constraint(op.f("ck_ml_metrics_value_nonnegative"), "ml_metrics", type_="check")
    op.create_check_constraint(
        op.f("ck_ml_metrics_value_range"),
        "ml_metrics",
        "metric_value >= 0 AND metric_value <= 1",
    )
