"""platform schema: objects extras, users, checkpoints, ai reports

Revision ID: 0001_platform
"""
import bcrypt
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_platform"
down_revision = None


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.add_column("objects", sa.Column("name", sa.String(255), nullable=True))
    op.add_column("objects", sa.Column("material", sa.String(64), nullable=True))
    op.add_column("objects", sa.Column("credit_issued_at", sa.Date(), nullable=True))
    op.add_column("objects", sa.Column("planned_completion_at", sa.Date(), nullable=True))
    op.add_column("objects", sa.Column("is_demo", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("objects", sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True))
    op.add_column("objects", sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True))
    op.execute("UPDATE objects SET name = 'Объект ' || id WHERE name IS NULL")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_objects_address_trgm ON objects USING gin (address gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_objects_cadastral_trgm ON objects USING gin (cadastral_number gin_trgm_ops)"
    )

    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("login", sa.String(64), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("is_demo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_users_login", "users", ["login"])

    users = sa.table(
        "users",
        sa.column("id", sa.String),
        sa.column("login", sa.String),
        sa.column("password_hash", sa.String),
        sa.column("role", sa.String),
        sa.column("display_name", sa.String),
        sa.column("is_demo", sa.Boolean),
    )
    op.bulk_insert(
        users,
        [
            {
                "id": "user_manager",
                "login": "manager",
                "password_hash": _hash("manager"),
                "role": "manager",
                "display_name": "Анна Кредитова",
                "is_demo": True,
            },
            {
                "id": "user_operator",
                "login": "operator",
                "password_hash": _hash("operator"),
                "role": "operator",
                "display_name": "Игорь Пилотов",
                "is_demo": True,
            },
        ],
    )

    op.create_table(
        "checkpoints",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("object_id", sa.String(64), sa.ForeignKey("objects.id"), nullable=False),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=False),
        sa.Column("expected_readiness", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_checkpoints_object", "checkpoints", ["object_id"])
    op.create_index("ix_checkpoints_date", "checkpoints", ["planned_date"])

    op.create_table(
        "checkpoint_date_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("checkpoint_id", sa.String(64), sa.ForeignKey("checkpoints.id"), nullable=False),
        sa.Column("actor_id", sa.String(64), sa.ForeignKey("users.id")),
        sa.Column("old_date", sa.Date(), nullable=False),
        sa.Column("new_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_cp_history_cp", "checkpoint_date_history", ["checkpoint_id"])

    op.create_table(
        "ai_reports",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("object_id", sa.String(64), sa.ForeignKey("objects.id"), nullable=False),
        sa.Column("checkpoint_id", sa.String(64), sa.ForeignKey("checkpoints.id")),
        sa.Column("agent_run_id", sa.String(64)),
        sa.Column("raw_json", postgresql.JSONB(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_ai_reports_object", "ai_reports", ["object_id"])
    op.create_index("ix_ai_reports_run", "ai_reports", ["agent_run_id"])

    op.create_table(
        "problem_alerts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("object_id", sa.String(64), sa.ForeignKey("objects.id"), nullable=False),
        sa.Column("report_id", sa.String(64), sa.ForeignKey("ai_reports.id")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("severity", sa.String(32)),
        sa.Column("status", sa.String(32), server_default="new", nullable=False),
        sa.Column("raw_item", postgresql.JSONB()),
        sa.Column("is_demo", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_alerts_object", "problem_alerts", ["object_id"])
    op.create_index("ix_alerts_status", "problem_alerts", ["status"])

    op.create_table(
        "problem_actions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("alert_id", sa.String(64), sa.ForeignKey("problem_alerts.id"), nullable=False),
        sa.Column("actor_id", sa.String(64), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_actions_alert", "problem_actions", ["alert_id"])


def downgrade() -> None:
    op.drop_table("problem_actions")
    op.drop_table("problem_alerts")
    op.drop_table("ai_reports")
    op.drop_table("checkpoint_date_history")
    op.drop_table("checkpoints")
    op.drop_table("users")
    op.drop_index("ix_objects_cadastral_trgm", table_name="objects")
    op.drop_index("ix_objects_address_trgm", table_name="objects")
    op.drop_column("objects", "updated_at")
    op.drop_column("objects", "created_at")
    op.drop_column("objects", "is_demo")
    op.drop_column("objects", "planned_completion_at")
    op.drop_column("objects", "credit_issued_at")
    op.drop_column("objects", "material")
    op.drop_column("objects", "name")
