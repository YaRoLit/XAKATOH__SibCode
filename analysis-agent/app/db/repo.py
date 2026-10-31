from datetime import date, datetime

from sqlalchemy import bindparam, select, text
from sqlalchemy.orm import Session

from app.db.models import AnalysisReport, ConstructionPlan


def claim_next_job(session: Session) -> dict | None:
    row = session.execute(
        text(
            """
            UPDATE processing_queue
            SET status = 'processing', picked_at = now()
            WHERE id = (
                SELECT q.id FROM processing_queue q
                JOIN batches b ON b.id = q.batch_id
                WHERE q.status = 'pending'
                  AND b.status IN ('ready', 'confirmed')
                ORDER BY CASE WHEN q.priority = 'high' THEN 0 ELSE 1 END, q.created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id, survey_id, survey_ids, primary_survey_id, batch_id, object_id,
                      capture_date, priority, status, created_at, picked_at
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
            SELECT s.id, s.object_id, s.s3_key, s.filename, s.created_at, s.batch_id,
                   s.metadata AS metadata,
                   o.address, o.cadastral_number, o.status AS object_status
            FROM surveys s
            LEFT JOIN objects o ON o.id = s.object_id
            WHERE s.id = :id
            """
        ),
        {"id": survey_id},
    ).mappings().first()
    return dict(row) if row else None


def load_surveys(session: Session, survey_ids: list[int]) -> list[dict]:
    if not survey_ids:
        return []
    rows = session.execute(
        text(
            """
            SELECT s.id, s.object_id, s.s3_key, s.filename, s.created_at, s.batch_id,
                   s.metadata AS metadata,
                   o.address, o.cadastral_number, o.status AS object_status
            FROM surveys s
            LEFT JOIN objects o ON o.id = s.object_id
            WHERE s.id IN :ids
            """
        ).bindparams(bindparam("ids", expanding=True)),
        {"ids": tuple(survey_ids)},
    ).mappings().all()
    by_id = {row["id"]: dict(row) for row in rows}
    return [by_id[sid] for sid in survey_ids if sid in by_id]


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


def newer_completed_exists(session: Session, object_id: str, captured_at: datetime | date) -> AnalysisReport | None:
    if isinstance(captured_at, datetime):
        captured_date = captured_at.date()
    else:
        captured_date = captured_at
    stmt = (
        select(AnalysisReport)
        .where(
            AnalysisReport.object_id == object_id,
            AnalysisReport.agent_status == "completed",
        )
        .order_by(AnalysisReport.captured_at.desc().nulls_last())
    )
    for report in session.scalars(stmt):
        report_date = report.capture_date or (report.captured_at.date() if report.captured_at else None)
        if report_date and report_date > captured_date:
            return report
    return None


def upsert_report(session: Session, values: dict) -> AnalysisReport:
    batch_id = values.get("batch_id")
    object_id = values.get("object_id")
    report = None
    if batch_id and object_id:
        report = session.scalar(
            select(AnalysisReport).where(
                AnalysisReport.batch_id == batch_id,
                AnalysisReport.object_id == object_id,
            )
        )
    if report is None and values.get("primary_survey_id"):
        report = session.scalar(
            select(AnalysisReport).where(AnalysisReport.primary_survey_id == values["primary_survey_id"])
        )
    if report is None and values.get("survey_id"):
        report = session.scalar(select(AnalysisReport).where(AnalysisReport.survey_id == values["survey_id"]))
    if report is None:
        report = AnalysisReport(**values)
        session.add(report)
    else:
        for key, value in values.items():
            setattr(report, key, value)
    session.commit()
    session.refresh(report)
    return report
