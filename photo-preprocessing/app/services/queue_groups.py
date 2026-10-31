from datetime import date, datetime
from math import cos, hypot, radians

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db import repositories as repo
from app.db.models import Object, Survey

log = get_logger(__name__)


def parse_exif_dt(raw) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def capture_dt(survey: Survey) -> datetime | None:
    meta = survey.metadata_ or {}
    return parse_exif_dt(meta.get("datetime_original")) or survey.created_at


def capture_date(survey: Survey) -> date | None:
    dt = capture_dt(survey)
    return dt.date() if dt else None


def _centroid(corners: list[dict]) -> tuple[float, float] | None:
    if not corners:
        return None
    lat = sum(float(p["lat"]) for p in corners) / len(corners)
    lon = sum(float(p["lon"]) for p in corners) / len(corners)
    return lat, lon


def _distance_m(lat: float, lon: float, lat0: float, lon0: float) -> float:
    x = (lon - lon0) * 111_000.0 * cos(radians(lat0))
    y = (lat - lat0) * 111_000.0
    return hypot(x, y)


def pick_primary(surveys: list[Survey], obj: Object | None) -> int:
    if not surveys:
        raise ValueError("empty survey group")
    centroid = _centroid((obj.plot_corners if obj else None) or [])
    if centroid is None:
        return surveys[0].id
    lat0, lon0 = centroid
    best_id = surveys[0].id
    best_d = None
    for survey in surveys:
        coords = (survey.metadata_ or {}).get("coordinates") or {}
        if "lat" not in coords or "lon" not in coords:
            continue
        dist = _distance_m(float(coords["lat"]), float(coords["lon"]), lat0, lon0)
        if best_d is None or dist < best_d:
            best_d = dist
            best_id = survey.id
    return best_id


def latest_date_group(surveys: list[Survey]) -> tuple[date | None, list[Survey]]:
    by_date: dict[date | None, list[Survey]] = {}
    for survey in surveys:
        by_date.setdefault(capture_date(survey), []).append(survey)
    known = [d for d in by_date if d is not None]
    if not known:
        return None, surveys
    chosen = max(known)
    return chosen, by_date[chosen]


async def enqueue_object_group(session: AsyncSession, batch_id: str, object_id: str, surveys: list[Survey]) -> dict:
    validated = [s for s in surveys if s.status == "validated" and s.s3_key and s.object_id == object_id]
    if not validated:
        return {"status": "skip", "reason": "no_validated"}

    capture, group = latest_date_group(validated)
    last = await repo.latest_report_capture_date(session, object_id)
    if capture and last and capture < last:
        log.info(
            "queue: skip stale group batch=%s object=%s capture=%s last_report=%s",
            batch_id, object_id, capture, last,
        )
        return {"status": "skipped_stale", "capture_date": str(capture), "last_report": str(last)}

    obj = next((s.object_ for s in group if s.object_), None)
    if obj is None:
        objects = {o.id: o for o in await repo.active_objects(session)}
        obj = objects.get(object_id)
    primary = pick_primary(group, obj)
    row = await repo.upsert_queue_group(
        session,
        batch_id=batch_id,
        object_id=object_id,
        survey_ids=[s.id for s in group],
        primary_survey_id=primary,
        capture_date=capture,
    )
    log.debug(
        "queue: group batch=%s object=%s n=%s primary=%s date=%s",
        batch_id, object_id, len(group), primary, capture,
    )
    return {
        "status": "ok",
        "queue_id": row.id if row else None,
        "survey_ids": [s.id for s in group],
        "primary_survey_id": primary,
        "capture_date": str(capture) if capture else None,
    }
