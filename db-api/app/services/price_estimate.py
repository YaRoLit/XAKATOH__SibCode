from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AnalysisReport, ConstructionPlan, Object, PriceReport, PriceSearchTask, User


async def latest_completed_analysis(session: AsyncSession, object_id: str) -> AnalysisReport | None:
    res = await session.execute(
        select(AnalysisReport)
        .where(
            AnalysisReport.object_id == object_id,
            AnalysisReport.agent_status == "completed",
        )
        .order_by(AnalysisReport.captured_at.desc().nulls_last(), AnalysisReport.created_at.desc().nulls_last())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def active_task(session: AsyncSession, object_id: str) -> PriceSearchTask | None:
    res = await session.execute(
        select(PriceSearchTask)
        .where(
            PriceSearchTask.object_id == object_id,
            PriceSearchTask.status.in_(("pending", "processing")),
        )
        .order_by(PriceSearchTask.created_at.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def latest_task(session: AsyncSession, object_id: str) -> PriceSearchTask | None:
    res = await session.execute(
        select(PriceSearchTask)
        .where(PriceSearchTask.object_id == object_id)
        .order_by(PriceSearchTask.created_at.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


async def report_for_task(session: AsyncSession, task_id: int) -> PriceReport | None:
    res = await session.execute(select(PriceReport).where(PriceReport.task_id == task_id))
    return res.scalar_one_or_none()


def _analysis_block(report: AnalysisReport) -> dict:
    raw = report.report_json if isinstance(report.report_json, dict) else {}
    utilities = raw.get("utilities") if isinstance(raw.get("utilities"), dict) else None
    return {
        "analysis_report_id": report.id,
        "captured_at": report.captured_at.isoformat() if report.captured_at else None,
        "report_mode": report.report_mode,
        "detected_stage_id": raw.get("detected_stage_id"),
        "detected_stage": report.detected_stage,
        "stage_progress_percent": report.stage_progress_percent,
        "progress_percent": report.progress_percent,
        "image_quality": report.image_quality,
        "overall_confidence": report.overall_confidence,
        "attention_required": bool(report.attention_required),
        "attention_reason": report.attention_reason,
        "utilities": utilities,
        "looks_residential": raw.get("looks_residential"),
        "residential_comment": raw.get("residential_comment"),
    }


def build_spec(obj: Object, plan: ConstructionPlan | None, report: AnalysisReport) -> dict:
    return {
        "object": {
            "object_id": obj.id,
            "address": obj.address,
            "cadastral_number": obj.cadastral_number,
            "name": obj.name,
            "material": obj.material,
        },
        "plan": {
            "description": plan.description if plan and plan.description else None,
        },
        "analysis": _analysis_block(report),
        "search_request": {
            "goal": "Найти похожие объекты недвижимости для примерной оценки рыночного диапазона цены",
            "property_type": "ИЖС",
            "preferred_comparables": ["completed", "unfinished"],
            "min_comparables": 3,
            "max_comparables": 6,
            "currency": "RUB",
        },
    }


def serialize_task(task: PriceSearchTask) -> dict:
    return {
        "id": task.id,
        "object_id": task.object_id,
        "analysis_report_id": task.analysis_report_id,
        "status": task.status,
        "error_message": task.error_message,
        "created_at": task.created_at,
        "picked_at": task.picked_at,
        "completed_at": task.completed_at,
        "requested_by": task.requested_by,
        "source": task.source,
    }


def serialize_report(report: PriceReport) -> dict:
    return {
        "id": report.id,
        "task_id": report.task_id,
        "object_id": report.object_id,
        "value_min": report.value_min,
        "value_point": report.value_point,
        "value_max": report.value_max,
        "currency": report.currency,
        "justification": report.justification,
        "comparables": report.comparables_json,
        "confidence": report.confidence,
        "data_source": report.data_source,
        "is_mock": bool(report.is_mock),
        "prompt_version": report.prompt_version,
        "llm_model": report.llm_model,
        "created_at": report.created_at,
    }


async def estimate_state(session: AsyncSession, object_id: str) -> dict:
    analysis = await latest_completed_analysis(session, object_id)
    task = await latest_task(session, object_id)
    report = await report_for_task(session, task.id) if task else None
    return {
        "can_estimate": analysis is not None,
        "has_active_task": bool(task and task.status in {"pending", "processing"}),
        "task": serialize_task(task) if task else None,
        "report": serialize_report(report) if report else None,
    }


async def request_estimate(session: AsyncSession, obj: Object, user: User) -> dict:
    analysis = await latest_completed_analysis(session, obj.id)
    if analysis is None:
        raise ValueError("Сначала дождитесь отчёта агента по последней съёмке")

    existing = await active_task(session, obj.id)
    if existing:
        return await estimate_state(session, obj.id)

    plan = (
        await session.execute(select(ConstructionPlan).where(ConstructionPlan.object_id == obj.id))
    ).scalar_one_or_none()
    spec = build_spec(obj, plan, analysis)
    task = PriceSearchTask(
        object_id=obj.id,
        analysis_report_id=analysis.id,
        address_snapshot=obj.address or "",
        cadastral_number_snapshot=obj.cadastral_number,
        spec_json=spec,
        status="pending",
        requested_by=user.login or user.id,
        source="manager_dashboard",
    )
    session.add(task)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
    return await estimate_state(session, obj.id)
