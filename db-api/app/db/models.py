from datetime import date, datetime

from sqlalchemy import JSON, BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    login: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32))
    display_name: Mapped[str] = mapped_column(String(128))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Object(Base):
    __tablename__ = "objects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cadastral_number: Mapped[str] = mapped_column(String(64), unique=True)
    address: Mapped[str] = mapped_column(Text)
    plot_corners: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="active")
    name: Mapped[str | None] = mapped_column(String(255))
    material: Mapped[str | None] = mapped_column(String(64))
    credit_issued_at: Mapped[date | None] = mapped_column(Date)
    planned_completion_at: Mapped[date | None] = mapped_column(Date)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    checkpoints: Mapped[list["Checkpoint"]] = relationship(back_populates="object_", order_by="Checkpoint.planned_date")


class Checkpoint(Base):
    __tablename__ = "checkpoints"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    object_id: Mapped[str] = mapped_column(ForeignKey("objects.id"), index=True)
    title: Mapped[str] = mapped_column(String(128))
    planned_date: Mapped[date] = mapped_column(Date, index=True)
    expected_readiness: Mapped[int] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    object_: Mapped[Object] = relationship(back_populates="checkpoints")
    date_history: Mapped[list["CheckpointDateHistory"]] = relationship(back_populates="checkpoint")


class CheckpointDateHistory(Base):
    __tablename__ = "checkpoint_date_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    checkpoint_id: Mapped[str] = mapped_column(ForeignKey("checkpoints.id"), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    old_date: Mapped[date] = mapped_column(Date)
    new_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    checkpoint: Mapped[Checkpoint] = relationship(back_populates="date_history")


class ConstructionPlan(Base):
    __tablename__ = "construction_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_id: Mapped[str] = mapped_column(ForeignKey("objects.id"), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())


class AnalysisReport(Base):
    __tablename__ = "analysis_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    survey_id: Mapped[int | None] = mapped_column(Integer, index=True)
    primary_survey_id: Mapped[int | None] = mapped_column(Integer, index=True)
    survey_ids: Mapped[list | None] = mapped_column(JSONB)
    batch_id: Mapped[str | None] = mapped_column(String(64), index=True)
    capture_date: Mapped[date | None] = mapped_column(Date)
    object_id: Mapped[str] = mapped_column(ForeignKey("objects.id"), index=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime)
    report_mode: Mapped[str | None] = mapped_column(String(32))
    agent_status: Mapped[str | None] = mapped_column(String(32), index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    object_match: Mapped[str | None] = mapped_column(String(32))
    detected_stage: Mapped[str | None] = mapped_column(String(64))
    stage_progress_percent: Mapped[int | None] = mapped_column(Integer)
    progress_percent: Mapped[int | None] = mapped_column(Integer)
    attention_required: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    attention_reason: Mapped[str | None] = mapped_column(Text)
    overall_confidence: Mapped[float | None] = mapped_column(Float)
    image_quality: Mapped[str | None] = mapped_column(String(32))
    movement_status: Mapped[str | None] = mapped_column(String(64))
    progress_delta: Mapped[float | None] = mapped_column(Float)
    days_since_prev: Mapped[int | None] = mapped_column(Integer)
    report_json: Mapped[dict | None] = mapped_column(JSONB)
    report_html_key: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())


class AiReport(Base):
    __tablename__ = "ai_reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    object_id: Mapped[str] = mapped_column(ForeignKey("objects.id"), index=True)
    checkpoint_id: Mapped[str | None] = mapped_column(ForeignKey("checkpoints.id"))
    agent_run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    raw_json: Mapped[dict] = mapped_column(JSONB)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ProblemAlert(Base):
    __tablename__ = "problem_alerts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    object_id: Mapped[str] = mapped_column(ForeignKey("objects.id"), index=True)
    report_id: Mapped[str | None] = mapped_column(ForeignKey("ai_reports.id"))
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    raw_item: Mapped[dict | None] = mapped_column(JSONB)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    actions: Mapped[list["ProblemAction"]] = relationship(back_populates="alert", order_by="ProblemAction.created_at")


class ProblemAction(Base):
    __tablename__ = "problem_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[str] = mapped_column(ForeignKey("problem_alerts.id"), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(64))
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    alert: Mapped[ProblemAlert] = relationship(back_populates="actions")


class PriceSearchTask(Base):
    __tablename__ = "price_search_tasks"
    __table_args__ = (
        Index("ix_price_tasks_status_created", "status", "created_at"),
        Index("ix_price_tasks_object_created", "object_id", "created_at"),
        Index(
            "uq_price_tasks_object_active",
            "object_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'processing')"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_id: Mapped[str] = mapped_column(ForeignKey("objects.id"), index=True)
    analysis_report_id: Mapped[int] = mapped_column(ForeignKey("analysis_reports.id"), index=True)
    address_snapshot: Mapped[str] = mapped_column(Text)
    cadastral_number_snapshot: Mapped[str | None] = mapped_column(String(64))
    spec_json: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    picked_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    requested_by: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(32), default="manager_dashboard")


class PriceReport(Base):
    __tablename__ = "price_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("price_search_tasks.id"), unique=True)
    object_id: Mapped[str] = mapped_column(ForeignKey("objects.id"), index=True)
    value_min: Mapped[int] = mapped_column(BigInteger)
    value_point: Mapped[int] = mapped_column(BigInteger)
    value_max: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(8), default="RUB")
    justification: Mapped[str] = mapped_column(Text)
    comparables_json: Mapped[list] = mapped_column(JSONB)
    confidence: Mapped[float | None] = mapped_column(Float)
    data_source: Mapped[str] = mapped_column(String(32), default="mock_llm_v1")
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True)
    prompt_version: Mapped[str] = mapped_column(String(64))
    llm_model: Mapped[str | None] = mapped_column(String(128))
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    processing_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Survey(Base):
    """Таблица первого сервиса, только чтение для статусов съёмки и кабинета оператора."""

    __tablename__ = "surveys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), index=True)
    validation_errors: Mapped[list | None] = mapped_column(JSONB)
    object_id: Mapped[str | None] = mapped_column(String(64), index=True)
    coverage: Mapped[float | None] = mapped_column(Float)
    s3_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    operator_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
