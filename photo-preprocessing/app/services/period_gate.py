from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import repositories as repo
from app.db.models import Survey
from app.services.queue_groups import parse_exif_dt


def exif_date(survey: Survey) -> date | None:
    meta = survey.metadata_ or {}
    dt = parse_exif_dt(meta.get("datetime_original"))
    return dt.date() if dt else None


def stale_message(photo: date, current: date) -> str:
    return (
        f"Снимок за {photo.isoformat()} относится к предыдущему периоду съёмки. "
        f"Актуальный день: {current.isoformat()}. Такие фото не принимаются."
    )


async def last_stored_period(session: AsyncSession, object_id: str) -> date | None:
    report = await repo.latest_report_capture_date(session, object_id)
    dates = [report] if report else []
    for survey in await repo.stored_surveys_for_object(session, object_id):
        day = exif_date(survey)
        if day:
            dates.append(day)
    return max(dates) if dates else None


async def period_cutoff(
    session: AsyncSession,
    object_id: str,
    batch_surveys: list[Survey] | None = None,
    exclude_id: int | None = None,
) -> date | None:
    candidates = []
    stored = await last_stored_period(session, object_id)
    if stored:
        candidates.append(stored)
    for survey in batch_surveys or []:
        if survey.id == exclude_id or survey.object_id != object_id or survey.status != "validated":
            continue
        day = exif_date(survey)
        if day:
            candidates.append(day)
    return max(candidates) if candidates else None


def stale_reason(photo: date | None, cutoff: date | None) -> str | None:
    if photo and cutoff and photo < cutoff:
        return stale_message(photo, cutoff)
    return None


async def reject_older_days_in_batch(
    session: AsyncSession,
    batch_id: str,
    object_id: str | None = None,
) -> int:
    """В одной загрузке оставляем только самый поздний день объекта. Более ранние — reject."""
    surveys = await repo.list_surveys(session, batch_id)
    groups: dict[str, list[Survey]] = {}
    for survey in surveys:
        if survey.status != "validated" or not survey.object_id:
            continue
        if object_id and survey.object_id != object_id:
            continue
        groups.setdefault(survey.object_id, []).append(survey)

    rejected = 0
    for oid, group in groups.items():
        cutoff = await period_cutoff(session, oid, group)
        if cutoff is None:
            continue
        for survey in group:
            reason = stale_reason(exif_date(survey), cutoff)
            if not reason:
                continue
            await repo.update_survey(
                session,
                survey.id,
                status="rejected",
                validation_errors=(survey.validation_errors or []) + [reason],
            )
            rejected += 1
    return rejected
