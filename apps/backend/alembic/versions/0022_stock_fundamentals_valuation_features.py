"""stock_fundamentals_valuation_features

Revision ID: 0022_stock_fundamentals_valuation_features
Revises: 0021_stock_universe_peer_market_data
Create Date: 2026-09-27 19:08:22.133605
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0022_stock_fundamentals_valuation_features"
down_revision: str | None = "0021_stock_universe_peer_market_data"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Keep Alembic's version column large enough for long revision identifiers.
    op.alter_column(
        "alembic_version",
        "version_num",
        type_=sa.String(length=64),
    )

    # -------------------------------------------------------------------------
    # Sector metric runs
    # -------------------------------------------------------------------------
    op.create_table(
        "sector_metric_runs",
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("group_type", sa.String(length=20), nullable=False),
        sa.Column("sector", sa.String(length=100), nullable=False),
        sa.Column("industry", sa.String(length=100), nullable=True),
        sa.Column("domain", sa.String(length=100), nullable=True),
        sa.Column("policy_version", sa.String(length=100), nullable=False),
        sa.Column("universe_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_sector_metric_runs"),
        ),
    )

    # -------------------------------------------------------------------------
    # Sector metrics
    # -------------------------------------------------------------------------
    op.create_table(
        "sector_metrics",
        sa.Column("sector_metric_run_id", sa.Uuid(), nullable=False),
        sa.Column("listed_company_id", sa.Uuid(), nullable=False),
        sa.Column("metric_code", sa.String(length=60), nullable=False),
        sa.Column(
            "raw_value",
            sa.Numeric(precision=24, scale=8),
            nullable=True,
        ),
        sa.Column(
            "percentile",
            sa.Numeric(precision=7, scale=6),
            nullable=True,
        ),
        sa.Column(
            "z_score",
            sa.Numeric(precision=16, scale=8),
            nullable=True,
        ),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("eligible_company_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["listed_company_id"],
            ["listed_companies.id"],
            name=op.f("fk_sector_metrics_listed_company_id_listed_companies"),
        ),
        sa.ForeignKeyConstraint(
            ["sector_metric_run_id"],
            ["sector_metric_runs.id"],
            name=op.f("fk_sector_metrics_sector_metric_run_id_sector_metric_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_sector_metrics"),
        ),
        sa.UniqueConstraint(
            "sector_metric_run_id",
            "listed_company_id",
            "metric_code",
            name="uq_sector_metric_member",
        ),
    )

    op.create_index(
        op.f("ix_sector_metrics_sector_metric_run_id"),
        "sector_metrics",
        ["sector_metric_run_id"],
        unique=False,
    )

    # -------------------------------------------------------------------------
    # Stock fundamental runs
    # -------------------------------------------------------------------------
    op.create_table(
        "stock_fundamental_runs",
        sa.Column("listed_company_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("provider_version", sa.String(length=100), nullable=False),
        sa.Column("period_type", sa.String(length=20), nullable=False),
        sa.Column("statement_scope", sa.String(length=20), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("reporting_period", sa.String(length=50), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("availability_date", sa.Date(), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
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
            "status IN ('PENDING','PROCESSING','COMPLETED','PARTIAL','FAILED','NEEDS_REVIEW')",
            name=op.f("ck_stock_fundamental_runs_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["listed_company_id"],
            ["listed_companies.id"],
            name=op.f("fk_stock_fundamental_runs_listed_company_id_listed_companies"),
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_stock_fundamental_runs"),
        ),
        sa.UniqueConstraint(
            "listed_company_id",
            "provider",
            "provider_version",
            "statement_scope",
            "period_end",
            "input_hash",
            name="uq_stock_fundamental_run_input",
        ),
    )

    op.create_index(
        op.f("ix_stock_fundamental_runs_listed_company_id"),
        "stock_fundamental_runs",
        ["listed_company_id"],
        unique=False,
    )

    # -------------------------------------------------------------------------
    # Stock feature runs
    # -------------------------------------------------------------------------
    op.create_table(
        "stock_feature_runs",
        sa.Column("listed_company_id", sa.Uuid(), nullable=False),
        sa.Column("stock_listing_id", sa.Uuid(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("feature_set_version", sa.String(length=100), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["listed_company_id"],
            ["listed_companies.id"],
            name=op.f("fk_stock_feature_runs_listed_company_id_listed_companies"),
        ),
        sa.ForeignKeyConstraint(
            ["stock_listing_id"],
            ["stock_listings.id"],
            name=op.f("fk_stock_feature_runs_stock_listing_id_stock_listings"),
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_stock_feature_runs"),
        ),
        sa.UniqueConstraint(
            "stock_listing_id",
            "as_of_date",
            "feature_set_version",
            "input_hash",
            name="uq_stock_feature_input",
        ),
    )

    op.create_index(
        op.f("ix_stock_feature_runs_stock_listing_id"),
        "stock_feature_runs",
        ["stock_listing_id"],
        unique=False,
    )

    # -------------------------------------------------------------------------
    # Stock fundamentals
    # -------------------------------------------------------------------------
    op.create_table(
        "stock_fundamentals",
        sa.Column("fundamental_run_id", sa.Uuid(), nullable=False),
        sa.Column("listed_company_id", sa.Uuid(), nullable=False),
        sa.Column("metric_code", sa.String(length=60), nullable=False),
        sa.Column("metric_name", sa.String(length=120), nullable=False),
        sa.Column(
            "value",
            sa.Numeric(precision=24, scale=6),
            nullable=False,
        ),
        sa.Column(
            "raw_value",
            sa.Numeric(precision=24, scale=6),
            nullable=False,
        ),
        sa.Column("raw_unit", sa.String(length=30), nullable=False),
        sa.Column("unit", sa.String(length=30), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("availability_date", sa.Date(), nullable=True),
        sa.Column("statement_scope", sa.String(length=20), nullable=False),
        sa.Column("provenance_type", sa.String(length=30), nullable=False),
        sa.Column("source_provider", sa.String(length=100), nullable=False),
        sa.Column("source_reference", sa.String(length=500), nullable=True),
        sa.Column(
            "normalization_version",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "confidence_score",
            sa.Numeric(precision=7, scale=6),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["fundamental_run_id"],
            ["stock_fundamental_runs.id"],
            name=op.f("fk_stock_fundamentals_fundamental_run_id_stock_fundamental_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["listed_company_id"],
            ["listed_companies.id"],
            name=op.f("fk_stock_fundamentals_listed_company_id_listed_companies"),
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_stock_fundamentals"),
        ),
        sa.UniqueConstraint(
            "fundamental_run_id",
            "metric_code",
            name="uq_stock_fundamental_metric",
        ),
    )

    op.create_index(
        op.f("ix_stock_fundamentals_fundamental_run_id"),
        "stock_fundamentals",
        ["fundamental_run_id"],
        unique=False,
    )

    # -------------------------------------------------------------------------
    # Stock features
    # -------------------------------------------------------------------------
    op.create_table(
        "stock_features",
        sa.Column("feature_run_id", sa.Uuid(), nullable=False),
        sa.Column("feature_name", sa.String(length=80), nullable=False),
        sa.Column("feature_group", sa.String(length=30), nullable=False),
        sa.Column(
            "value",
            sa.Numeric(precision=24, scale=8),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN "
            "('AVAILABLE','UNAVAILABLE','INSUFFICIENT_INPUTS',"
            "'INVALID_DENOMINATOR','NOT_MEANINGFUL','NEEDS_REVIEW',"
            "'INSUFFICIENT_HISTORY','INSUFFICIENT_GROUP_SIZE',"
            "'INVALID_INPUT')",
            name=op.f("ck_stock_features_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["feature_run_id"],
            ["stock_feature_runs.id"],
            name=op.f("fk_stock_features_feature_run_id_stock_feature_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_stock_features"),
        ),
        sa.UniqueConstraint(
            "feature_run_id",
            "feature_name",
            name="uq_stock_feature_name",
        ),
    )

    op.create_index(
        op.f("ix_stock_features_feature_run_id"),
        "stock_features",
        ["feature_run_id"],
        unique=False,
    )

    # -------------------------------------------------------------------------
    # Stock valuation runs
    # -------------------------------------------------------------------------
    op.create_table(
        "stock_valuation_runs",
        sa.Column("listed_company_id", sa.Uuid(), nullable=False),
        sa.Column("stock_listing_id", sa.Uuid(), nullable=False),
        sa.Column("valuation_date", sa.Date(), nullable=False),
        sa.Column("fundamental_run_id", sa.Uuid(), nullable=True),
        sa.Column("price_record_id", sa.Uuid(), nullable=True),
        sa.Column("policy_version", sa.String(length=100), nullable=False),
        sa.Column("engine_version", sa.String(length=100), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["fundamental_run_id"],
            ["stock_fundamental_runs.id"],
            name=op.f("fk_stock_valuation_runs_fundamental_run_id_stock_fundamental_runs"),
        ),
        sa.ForeignKeyConstraint(
            ["listed_company_id"],
            ["listed_companies.id"],
            name=op.f("fk_stock_valuation_runs_listed_company_id_listed_companies"),
        ),
        sa.ForeignKeyConstraint(
            ["price_record_id"],
            ["stock_prices.id"],
            name=op.f("fk_stock_valuation_runs_price_record_id_stock_prices"),
        ),
        sa.ForeignKeyConstraint(
            ["stock_listing_id"],
            ["stock_listings.id"],
            name=op.f("fk_stock_valuation_runs_stock_listing_id_stock_listings"),
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_stock_valuation_runs"),
        ),
        sa.UniqueConstraint(
            "stock_listing_id",
            "valuation_date",
            "policy_version",
            "input_hash",
            name="uq_stock_valuation_input",
        ),
    )

    op.create_index(
        op.f("ix_stock_valuation_runs_stock_listing_id"),
        "stock_valuation_runs",
        ["stock_listing_id"],
        unique=False,
    )

    # -------------------------------------------------------------------------
    # Stock feature inputs
    # -------------------------------------------------------------------------
    op.create_table(
        "stock_feature_inputs",
        sa.Column("stock_feature_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_reference_id", sa.Uuid(), nullable=False),
        sa.Column("input_name", sa.String(length=80), nullable=False),
        sa.Column(
            "input_value",
            sa.Numeric(precision=24, scale=8),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["stock_feature_id"],
            ["stock_features.id"],
            name=op.f("fk_stock_feature_inputs_stock_feature_id_stock_features"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_stock_feature_inputs"),
        ),
    )

    op.create_index(
        op.f("ix_stock_feature_inputs_stock_feature_id"),
        "stock_feature_inputs",
        ["stock_feature_id"],
        unique=False,
    )

    # -------------------------------------------------------------------------
    # Stock valuations
    # -------------------------------------------------------------------------
    op.create_table(
        "stock_valuations",
        sa.Column("valuation_run_id", sa.Uuid(), nullable=False),
        sa.Column("metric_code", sa.String(length=60), nullable=False),
        sa.Column(
            "value",
            sa.Numeric(precision=24, scale=8),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("formula_version", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN "
            "('AVAILABLE','UNAVAILABLE','INSUFFICIENT_INPUTS',"
            "'INVALID_DENOMINATOR','NOT_MEANINGFUL','NEEDS_REVIEW',"
            "'INSUFFICIENT_HISTORY','INSUFFICIENT_GROUP_SIZE',"
            "'INVALID_INPUT')",
            name=op.f("ck_stock_valuations_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["valuation_run_id"],
            ["stock_valuation_runs.id"],
            name=op.f("fk_stock_valuations_valuation_run_id_stock_valuation_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_stock_valuations"),
        ),
        sa.UniqueConstraint(
            "valuation_run_id",
            "metric_code",
            name="uq_stock_valuation_metric",
        ),
    )

    op.create_index(
        op.f("ix_stock_valuations_valuation_run_id"),
        "stock_valuations",
        ["valuation_run_id"],
        unique=False,
    )

    # -------------------------------------------------------------------------
    # Stock valuation inputs
    # -------------------------------------------------------------------------
    op.create_table(
        "stock_valuation_inputs",
        sa.Column("stock_valuation_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_reference_id", sa.Uuid(), nullable=False),
        sa.Column("input_name", sa.String(length=80), nullable=False),
        sa.Column(
            "input_value",
            sa.Numeric(precision=24, scale=8),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["stock_valuation_id"],
            ["stock_valuations.id"],
            name=op.f("fk_stock_valuation_inputs_stock_valuation_id_stock_valuations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_stock_valuation_inputs"),
        ),
    )

    op.create_index(
        op.f("ix_stock_valuation_inputs_stock_valuation_id"),
        "stock_valuation_inputs",
        ["stock_valuation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_stock_valuation_inputs_stock_valuation_id"),
        table_name="stock_valuation_inputs",
    )
    op.drop_table("stock_valuation_inputs")

    op.drop_index(
        op.f("ix_stock_valuations_valuation_run_id"),
        table_name="stock_valuations",
    )
    op.drop_table("stock_valuations")

    op.drop_index(
        op.f("ix_stock_feature_inputs_stock_feature_id"),
        table_name="stock_feature_inputs",
    )
    op.drop_table("stock_feature_inputs")

    op.drop_index(
        op.f("ix_stock_valuation_runs_stock_listing_id"),
        table_name="stock_valuation_runs",
    )
    op.drop_table("stock_valuation_runs")

    op.drop_index(
        op.f("ix_stock_features_feature_run_id"),
        table_name="stock_features",
    )
    op.drop_table("stock_features")

    op.drop_index(
        op.f("ix_stock_fundamentals_fundamental_run_id"),
        table_name="stock_fundamentals",
    )
    op.drop_table("stock_fundamentals")

    op.drop_index(
        op.f("ix_stock_feature_runs_stock_listing_id"),
        table_name="stock_feature_runs",
    )
    op.drop_table("stock_feature_runs")

    op.drop_index(
        op.f("ix_stock_fundamental_runs_listed_company_id"),
        table_name="stock_fundamental_runs",
    )
    op.drop_table("stock_fundamental_runs")

    op.drop_index(
        op.f("ix_sector_metrics_sector_metric_run_id"),
        table_name="sector_metrics",
    )
    op.drop_table("sector_metrics")

    op.drop_table("sector_metric_runs")
