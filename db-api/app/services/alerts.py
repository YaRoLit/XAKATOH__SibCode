from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.models import AiReport, AnalysisReport, ConstructionPlan, Object, ProblemAction, ProblemAlert, User


def html_url(key: str | None) -> str | None:
    if not key:
        return None
    return f"{settings.storage_public_base.rstrip('/')}/{key.lstrip('/')}"


async def list_problem_alerts(session: AsyncSession, status: str | None = None, object_id: str | None = None):
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


async def list_alerts(session: AsyncSession, status: str | None = None, object_id: str | None = None):
    items = []
    if status in (None, "new"):
        agent_stmt = select(AnalysisReport).where(AnalysisReport.attention_required.is_(True)).order_by(AnalysisReport.created_at.desc())
        if object_id:
            agent_stmt = agent_stmt.where(AnalysisReport.object_id == object_id)
        for report in (await session.execute(agent_stmt)).scalars():
            items.append(await serialize_analysis_alert(session, report))
    for alert in await list_problem_alerts(session, status=status, object_id=object_id):
        items.append(await serialize_alert(session, alert))
    items.sort(key=lambda row: row.get("created_at") or 0, reverse=True)
    return items


async def get_alert(session: AsyncSession, alert_id: str) -> ProblemAlert | None:
    res = await session.execute(
        select(ProblemAlert).options(selectinload(ProblemAlert.actions)).where(ProblemAlert.id == alert_id)
    )
    return res.scalar_one_or_none()


async def get_analysis_report(session: AsyncSession, report_id: int) -> AnalysisReport | None:
    return await session.get(AnalysisReport, report_id)


async def serialize_analysis_alert(session: AsyncSession, report: AnalysisReport) -> dict:
    obj = await session.get(Object, report.object_id)
    return {
        "id": f"ar_{report.id}",
        "object_id": report.object_id,
        "object_name": obj.name if obj else None,
        "report_id": str(report.id),
        "title": report.attention_reason or "Внимание агента",
        "summary": report.error_message or report.detected_stage,
        "severity": "red" if report.agent_status == "failed" else "yellow",
        "status": "new",
        "raw_item": {
            "source": "analysis-agent",
            "agent_status": report.agent_status,
            "movement_status": report.movement_status,
            "html_url": html_url(report.report_html_key),
            "progress_percent": report.progress_percent,
        },
        "created_at": report.created_at or report.captured_at,
        "actions": [],
        "readonly": True,
    }


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
    items = []
    if object_id and not checkpoint_id:
        agent_stmt = select(AnalysisReport).where(AnalysisReport.object_id == object_id).order_by(AnalysisReport.captured_at.desc())
        for report in (await session.execute(agent_stmt)).scalars():
            items.append(serialize_analysis_report(report))
    stmt = select(AiReport).order_by(AiReport.created_at.desc())
    if object_id:
        stmt = stmt.where(AiReport.object_id == object_id)
    if checkpoint_id:
        stmt = stmt.where(AiReport.checkpoint_id == checkpoint_id)
    for report in (await session.execute(stmt)).scalars():
        items.append(serialize_report(report))
    return items


def serialize_report(report: AiReport) -> dict:
    return {
        "id": report.id,
        "object_id": report.object_id,
        "source": "demo",
        "checkpoint_id": report.checkpoint_id,
        "agent_run_id": report.agent_run_id,
        "raw_json": report.raw_json,
        "created_at": report.created_at,
        "html_url": None,
        "agent_status": "completed",
    }


def serialize_analysis_report(report: AnalysisReport) -> dict:
    raw = dict(report.report_json or {})
    raw.setdefault("overall_readiness_pct", report.progress_percent)
    if report.attention_required:
        raw.setdefault("overall_status", "red")
        raw.setdefault("problems", [{"title": report.attention_reason, "description": report.error_message}])
    elif report.movement_status == "stalled":
        raw.setdefault("overall_status", "yellow")
    else:
        raw.setdefault("overall_status", "green")
    if report.detected_stage:
        raw.setdefault(
            "stages",
            [{"name": report.detected_stage, "readiness_pct": report.stage_progress_percent, "status": raw.get("overall_status")}],
        )
    raw["html_url"] = html_url(report.report_html_key)
    raw["movement_status"] = report.movement_status
    raw["progress_delta"] = report.progress_delta
    return {
        "id": f"an_{report.id}",
        "object_id": report.object_id,
        "source": "analysis",
        "checkpoint_id": None,
        "agent_run_id": None,
        "raw_json": raw,
        "created_at": report.captured_at or report.created_at,
        "html_url": html_url(report.report_html_key),
        "agent_status": report.agent_status,
    }


async def get_plan(session: AsyncSession, object_id: str) -> ConstructionPlan | None:
    res = await session.execute(select(ConstructionPlan).where(ConstructionPlan.object_id == object_id))
    return res.scalar_one_or_none()


async def upsert_plan(session: AsyncSession, object_id: str, description: str) -> ConstructionPlan:
    plan = await get_plan(session, object_id)
    if plan is None:
        plan = ConstructionPlan(object_id=object_id, description=description)
        session.add(plan)
    else:
        plan.description = description
    await session.commit()
    await session.refresh(plan)
    return plan


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
