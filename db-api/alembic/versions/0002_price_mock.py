"""price mock tasks and reports

Revision ID: 0002_price_mock
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_price_mock"
down_revision = "0001_platform"


def upgrade() -> None:
    op.create_table(
        "price_search_tasks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("object_id", sa.String(64), sa.ForeignKey("objects.id"), nullable=False),
        sa.Column("analysis_report_id", sa.Integer(), sa.ForeignKey("analysis_reports.id"), nullable=False),
        sa.Column("address_snapshot", sa.Text(), nullable=False),
        sa.Column("cadastral_number_snapshot", sa.String(64), nullable=True),
        sa.Column("spec_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("picked_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("requested_by", sa.String(64), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="manager_dashboard"),
    )
    op.create_index("ix_price_tasks_status_created", "price_search_tasks", ["status", "created_at"])
    op.create_index("ix_price_tasks_object_created", "price_search_tasks", ["object_id", "created_at"])
    op.create_index("ix_price_tasks_analysis_report", "price_search_tasks", ["analysis_report_id"])
    op.execute(
        """
        CREATE UNIQUE INDEX uq_price_tasks_object_active
        ON price_search_tasks (object_id)
        WHERE status IN ('pending', 'processing')
        """
    )

    op.create_table(
        "price_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("price_search_tasks.id"), nullable=False, unique=True),
        sa.Column("object_id", sa.String(64), sa.ForeignKey("objects.id"), nullable=False),
        sa.Column("value_min", sa.BigInteger(), nullable=False),
        sa.Column("value_point", sa.BigInteger(), nullable=False),
        sa.Column("value_max", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="RUB"),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("comparables_json", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("data_source", sa.String(32), nullable=False, server_default="mock_llm_v1"),
        sa.Column("is_mock", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("prompt_version", sa.String(64), nullable=False),
        sa.Column("llm_model", sa.String(128), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("processing_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_price_reports_object_created", "price_reports", ["object_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_price_reports_object_created", table_name="price_reports")
    op.drop_table("price_reports")
    op.execute("DROP INDEX IF EXISTS uq_price_tasks_object_active")
    op.drop_index("ix_price_tasks_analysis_report", table_name="price_search_tasks")
    op.drop_index("ix_price_tasks_object_created", table_name="price_search_tasks")
    op.drop_index("ix_price_tasks_status_created", table_name="price_search_tasks")
    op.drop_table("price_search_tasks")
