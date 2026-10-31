from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import AnalysisReport, ConstructionPlan


def claim_next_job(session: Session) -> dict | None:
    row = session.execute(
        text(
            """
            UPDATE processing_queue
            SET status = 'processing', picked_at = now()
            WHERE id = (
                SELECT id FROM processing_queue
                WHERE status = 'pending'
                ORDER BY CASE WHEN priority = 'high' THEN 0 ELSE 1 END, created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id, survey_id, object_id, priority, status, created_at, picked_at
            """
        )
    ).mappings().first()
    session.commit()
    return dict(row) if row else None


def finish_queue(session: Session, queue_id: int, status: str) -> None:
    session.execute(
        text(
            """
            UPDATE processing_queue
            SET status = :status, completed_at = now()
            WHERE id = :id
            """
        ),
        {"status": status, "id": queue_id},
    )
    session.commit()


def load_survey(session: Session, survey_id: int) -> dict | None:
    row = session.execute(
        text(
            """
            SELECT s.id, s.object_id, s.s3_key, s.filename, s.created_at,
                   o.address, o.cadastral_number, o.status AS object_status
            FROM surveys s
            LEFT JOIN objects o ON o.id = s.object_id
            WHERE s.id = :id
            """
        ),
        {"id": survey_id},
    ).mappings().first()
    return dict(row) if row else None


def load_plan(session: Session, object_id: str) -> ConstructionPlan | None:
    return session.scalar(select(ConstructionPlan).where(ConstructionPlan.object_id == object_id))


def latest_completed_before(session: Session, object_id: str, captured_at: datetime) -> AnalysisReport | None:
    stmt = (
        select(AnalysisReport)
        .where(
            AnalysisReport.object_id == object_id,
            AnalysisReport.agent_status == "completed",
            AnalysisReport.progress_percent.is_not(None),
            AnalysisReport.captured_at.is_not(None),
            AnalysisReport.captured_at < captured_at,
        )
        .order_by(AnalysisReport.captured_at.desc())
        .limit(1)
    )
    return session.scalar(stmt)


def newer_completed_exists(session: Session, object_id: str, captured_at: datetime) -> AnalysisReport | None:
    stmt = (
        select(AnalysisReport)
        .where(
            AnalysisReport.object_id == object_id,
            AnalysisReport.agent_status == "completed",
            AnalysisReport.captured_at.is_not(None),
            AnalysisReport.captured_at > captured_at,
        )
        .order_by(AnalysisReport.captured_at.desc())
        .limit(1)
    )
    return session.scalar(stmt)


def upsert_report(session: Session, values: dict) -> AnalysisReport:
    survey_id = values["survey_id"]
    report = session.scalar(select(AnalysisReport).where(AnalysisReport.survey_id == survey_id))
    if report is None:
        report = AnalysisReport(**values)
        session.add(report)
    else:
        for key, value in values.items():
            setattr(report, key, value)
    session.commit()
    session.refresh(report)
    return report
