from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Object(Base):
    __tablename__ = "objects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cadastral_number: Mapped[str] = mapped_column(String(64), unique=True)
    address: Mapped[str] = mapped_column(Text)
    plot_corners: Mapped[list] = mapped_column(JSON)  # [{"lat":..,"lon":..} x4]
    status: Mapped[str] = mapped_column(String(32), default="active")


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    operator_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="uploading")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    surveys: Mapped[list["Survey"]] = relationship(back_populates="batch")


class Survey(Base):
    __tablename__ = "surveys"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON)
    validation_errors: Mapped[list] = mapped_column(JSON, default=list)
    object_id: Mapped[str | None] = mapped_column(ForeignKey("objects.id"))
    coverage: Mapped[float | None] = mapped_column(Float)
    duplicate_of: Mapped[int | None] = mapped_column(ForeignKey("surveys.id"))
    temp_path: Mapped[str | None] = mapped_column(Text)
    preview_path: Mapped[str | None] = mapped_column(Text)
    s3_key: Mapped[str | None] = mapped_column(Text)
    preview_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    batch: Mapped[Batch] = relationship(back_populates="surveys")
    object_: Mapped[Object | None] = relationship(lazy="selectin")


class ProcessingQueue(Base):
    __tablename__ = "processing_queue"
    __table_args__ = (UniqueConstraint("batch_id", "object_id", name="uq_queue_batch_object"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    survey_id: Mapped[int | None] = mapped_column(Integer)
    survey_ids: Mapped[list] = mapped_column(JSONB, default=list)
    primary_survey_id: Mapped[int | None] = mapped_column(Integer)
    batch_id: Mapped[str | None] = mapped_column(String(64), index=True)
    object_id: Mapped[str] = mapped_column(ForeignKey("objects.id"), index=True)
    capture_date: Mapped[date | None] = mapped_column(Date)
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    picked_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)