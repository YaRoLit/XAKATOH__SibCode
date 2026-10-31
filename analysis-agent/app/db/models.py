from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class AgentBase(DeclarativeBase):
    pass


class ConstructionPlan(AgentBase):
    __tablename__ = "construction_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    building_type: Mapped[str | None] = mapped_column(String(128))
    object_purpose: Mapped[str | None] = mapped_column(String(128))
    floors_count: Mapped[int | None] = mapped_column(Integer)
    total_area: Mapped[float | None] = mapped_column(Float)
    planned_start: Mapped[datetime | None] = mapped_column(DateTime)
    planned_finish: Mapped[datetime | None] = mapped_column(DateTime)
    materials: Mapped[str | None] = mapped_column(Text)
    stages: Mapped[dict | list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class AnalysisReport(AgentBase):
    __tablename__ = "analysis_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    survey_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    object_id: Mapped[str] = mapped_column(String(64), index=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    report_mode: Mapped[str] = mapped_column(String(32))
    agent_status: Mapped[str] = mapped_column(String(32), index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    object_match: Mapped[str | None] = mapped_column(String(32))
    detected_stage_id: Mapped[int | None] = mapped_column(Integer)
    detected_stage: Mapped[str | None] = mapped_column(String(64))
    stage_progress_percent: Mapped[int | None] = mapped_column(Integer)
    progress_percent: Mapped[int | None] = mapped_column(Integer)
    compliance_status: Mapped[str | None] = mapped_column(String(32))
    deviation_days: Mapped[int | None] = mapped_column(Integer)
    deviation_severity: Mapped[str | None] = mapped_column(String(32))
    attention_required: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    attention_reason: Mapped[str | None] = mapped_column(Text)
    overall_confidence: Mapped[float | None] = mapped_column(Float)
    image_quality: Mapped[str | None] = mapped_column(String(32))
    looks_residential: Mapped[bool | None] = mapped_column(Boolean)
    prev_report_id: Mapped[int | None] = mapped_column(ForeignKey("analysis_reports.id"))
    progress_delta: Mapped[float | None] = mapped_column(Float)
    days_since_prev: Mapped[int | None] = mapped_column(Integer)
    progress_rate_per_week: Mapped[float | None] = mapped_column(Float)
    movement_status: Mapped[str | None] = mapped_column(String(64), index=True)
    report_json: Mapped[dict | None] = mapped_column(JSONB)
    report_html_key: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    llm_calls: Mapped[int | None] = mapped_column(Integer)
    crops_used: Mapped[int | None] = mapped_column(Integer)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    processing_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
