from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import AiReport, Object, ProblemAction, ProblemAlert, User


async def list_alerts(session: AsyncSession, status: str | None = None, object_id: str | None = None):
    stmt = (
        select(ProblemAlert)
        .options(selectinload(ProblemAlert.actions))
        .order_by(ProblemAlert.created_at.desc())
    )
    if status:
        stmt = stmt.where(ProblemAlert.status == status)
    if object_id:
        stmt = stmt.where(ProblemAlert.object_id == object_id)
    return list((await session.execute(stmt)).scalars())


async def get_alert(session: AsyncSession, alert_id: str) -> ProblemAlert | None:
    res = await session.execute(
        select(ProblemAlert).options(selectinload(ProblemAlert.actions)).where(ProblemAlert.id == alert_id)
    )
    return res.scalar_one_or_none()


async def add_action(
    session: AsyncSession,
    alert: ProblemAlert,
    actor_id: str,
    *,
    status: str | None,
    comment: str | None,
) -> ProblemAlert:
    if not status and not comment:
        raise ValueError("Нужен новый статус или комментарий")
    if status:
        alert.status = status
    session.add(
        ProblemAction(
            alert_id=alert.id,
            actor_id=actor_id,
            action="status_change" if status else "comment",
            comment=comment,
        )
    )
    await session.commit()
    return await get_alert(session, alert.id)


async def serialize_alert(session: AsyncSession, alert: ProblemAlert) -> dict:
    obj = await session.get(Object, alert.object_id)
    actor_ids = {a.actor_id for a in alert.actions if a.actor_id}
    actors = {}
    if actor_ids:
        rows = (await session.execute(select(User).where(User.id.in_(actor_ids)))).scalars()
        actors = {u.id: u.display_name for u in rows}
    return {
        "id": alert.id,
        "object_id": alert.object_id,
        "object_name": obj.name if obj else None,
        "report_id": alert.report_id,
        "title": alert.title,
        "summary": alert.summary,
        "severity": alert.severity,
        "status": alert.status,
        "raw_item": alert.raw_item,
        "created_at": alert.created_at,
        "actions": [
            {
                "id": a.id,
                "action": a.action,
                "comment": a.comment,
                "actor_id": a.actor_id,
                "actor_name": actors.get(a.actor_id),
                "created_at": a.created_at,
            }
            for a in alert.actions
        ],
    }


async def list_reports(session: AsyncSession, object_id: str | None = None, checkpoint_id: str | None = None):
    stmt = select(AiReport).order_by(AiReport.created_at.desc())
    if object_id:
        stmt = stmt.where(AiReport.object_id == object_id)
    if checkpoint_id:
        stmt = stmt.where(AiReport.checkpoint_id == checkpoint_id)
    return list((await session.execute(stmt)).scalars())


def serialize_report(report: AiReport) -> dict:
    return {
        "id": report.id,
        "object_id": report.object_id,
        "checkpoint_id": report.checkpoint_id,
        "agent_run_id": report.agent_run_id,
        "raw_json": report.raw_json,
        "created_at": report.created_at,
    }


async def create_report_from_agent(
    session: AsyncSession,
    *,
    object_id: str,
    checkpoint_id: str | None,
    agent_run_id: str | None,
    raw_json: dict,
) -> AiReport:
    """Контракт записи для третьего сервиса (агента). FastAPI менеджера сам агента не вызывает."""
    report = AiReport(
        id=f"rep_{uuid4().hex[:16]}",
        object_id=object_id,
        checkpoint_id=checkpoint_id,
        agent_run_id=agent_run_id,
        raw_json=raw_json,
        is_demo=False,
    )
    session.add(report)
    problems = raw_json.get("problems") if isinstance(raw_json, dict) else None
    if isinstance(problems, list):
        for item in problems:
            session.add(
                ProblemAlert(
                    id=f"al_{uuid4().hex[:16]}",
                    object_id=object_id,
                    report_id=report.id,
                    title=str(item.get("title") or item.get("code") or "Проблема AI"),
                    summary=item.get("description") or item.get("summary"),
                    severity=item.get("severity") or item.get("status"),
                    status="new",
                    raw_item=item,
                    is_demo=False,
                )
            )
    await session.commit()
    await session.refresh(report)
    return report
