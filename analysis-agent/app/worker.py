import logging
import shutil
import uuid
from datetime import date, datetime
from pathlib import Path

from app.agent.graphs import run_agent
from app.db import repo
from app.db.session import SessionLocal
from app.dynamics import compute_dynamics
from app.html_report import render_html
from app.settings import format_stage_label, render_prompt, yaml_config
from app import storage

log = logging.getLogger("analysis_agent")


def _merge_attention(agent_flag: bool, agent_reason: str | None, dyn_alert: str | None) -> tuple[bool, str | None]:
    reasons = [item for item in (agent_reason, dyn_alert) if item]
    return (agent_flag or bool(dyn_alert), "; ".join(reasons) if reasons else None)


def _parse_exif_dt(raw) -> datetime | None:
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return None


def _survey_dt(survey: dict) -> datetime | None:
    meta = survey.get("metadata") or {}
    return _parse_exif_dt(meta.get("datetime_original")) or survey.get("created_at")


def _survey_date(survey: dict) -> date | None:
    dt = _survey_dt(survey)
    return dt.date() if dt else None


def _photo_meta(survey: dict) -> dict:
    meta = survey.get("metadata") or {}
    orientation = meta.get("orientation") or {}
    altitude = meta.get("altitude") or {}
    return {
        "datetime_original": meta.get("datetime_original"),
        "captured_at": survey.get("created_at"),
        "yaw": orientation.get("yaw"),
        "altitude": altitude.get("relative"),
        "coordinates": meta.get("coordinates"),
    }


def _as_int_list(value) -> list[int]:
    if not value:
        return []
    if isinstance(value, str):
        import json
        try:
            value = json.loads(value)
        except ValueError:
            return []
    out = []
    for item in value:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


def prepare_working_set(surveys: list[dict], job: dict) -> tuple[list[dict], list[dict]]:
    max_photos = int((yaml_config.get("multi_photo") or {}).get("max_photos_per_analysis", 8))
    dated = [(_survey_date(s), s) for s in surveys]
    known = [d for d, _ in dated if d]
    max_date = max(known) if known else job.get("capture_date")
    assessments = []
    working = []
    for day, survey in dated:
        if max_date and day and day < max_date:
            assessments.append(
                {
                    "photo_index": 0,
                    "survey_id": survey["id"],
                    "relevance": "outdated",
                    "note": "другая дата съёмки в батче",
                }
            )
        else:
            working.append(survey)
    working.sort(key=lambda s: _survey_dt(s) or datetime.min)
    overflow = working[max_photos:]
    working = working[:max_photos]
    for survey in overflow:
        assessments.append(
            {
                "photo_index": 0,
                "survey_id": survey["id"],
                "relevance": "outdated",
                "note": "лимит max_photos_per_analysis",
            }
        )
    photos = []
    for index, survey in enumerate(working, start=1):
        path = storage.file_path(survey.get("s3_key"))
        if path is None:
            assessments.append(
                {
                    "photo_index": index,
                    "survey_id": survey["id"],
                    "relevance": "outdated",
                    "note": "файл не найден",
                }
            )
            continue
        photos.append(
            {
                "index": index,
                "survey_id": survey["id"],
                "path": str(path),
                "meta": _photo_meta(survey),
                "survey": survey,
            }
        )
    return photos, assessments


def process_job(job: dict) -> None:
    session = SessionLocal()
    tmp_dir = Path("/tmp") / uuid.uuid4().hex
    tmp_dir.mkdir(parents=True, exist_ok=True)
    queue_id = job["id"]
    object_id = job["object_id"]
    survey_ids = _as_int_list(job.get("survey_ids")) or ([job["survey_id"]] if job.get("survey_id") else [])
    primary_id = job.get("primary_survey_id") or (survey_ids[0] if survey_ids else None)
    try:
        surveys = repo.load_surveys(session, survey_ids)
        if not surveys:
            raise RuntimeError(f"surveys {survey_ids} not found")
        photos, discarded = prepare_working_set(surveys, job)
        primary = next((p for p in photos if p["survey_id"] == primary_id), None) or (photos[0] if photos else None)
        cover = (primary or {}).get("survey") or surveys[0]
        captured_at = max((_survey_dt(s) for s in (p["survey"] for p in photos)), default=_survey_dt(cover))
        capture_day = job.get("capture_date") or (captured_at.date() if captured_at else None)
        plan = repo.load_plan(session, object_id)
        plan_text = (plan.description or "").strip() if plan else ""
        mode = "with_plan" if plan_text else "no_plan"
        version, prompt = render_prompt(mode, photo_count=len(photos))

        if not photos:
            _fail(session, job, cover, mode, version, "нет рабочих фото", attention_reason="нет рабочих фото")
            return

        if capture_day:
            newer = repo.newer_completed_exists(session, object_id, capture_day)
            if newer is not None:
                _skip_stale(session, job, cover, mode, version, newer, capture_day)
                return

        context = (
            f"Объект: {object_id}. Адрес: {cover.get('address') or '—'}. "
            f"Кадастровый номер: {cover.get('cadastral_number') or '—'}. "
            f"Дата съёмки: {capture_day or captured_at}. "
            f"Фото в анализе: {len(photos)}. Обложка (primary): фото {primary['index'] if primary else 1}."
        )
        if mode == "with_plan":
            context += f"\nПлан строительства:\n{plan_text}"
        else:
            context += " План строительства не задан."
        if len(photos) == 1:
            context += " Определи этап, прогресс и вызови crop_photo_tool хотя бы один раз."
        else:
            context += " Сначала осмотри миниатюры, затем select_photo_tool и crop_photo_tool."

        log.info(
            "run agent",
            extra={"extra_data": {"batch_id": job.get("batch_id"), "object_id": object_id, "photos": len(photos), "mode": mode}},
        )
        result = run_agent(mode, photos, str(tmp_dir), context, prompt)
        if result["report"] is None:
            raise RuntimeError(f"невалидный JSON от модели: {result['parse_error']}")

        report = result["report"]
        crops_meta = _persist_crops(job, result["crops_meta"])
        payload = report.model_dump()
        payload["crops_meta"] = crops_meta
        payload["selected_photo_indices"] = payload.get("selected_photo_indices") or result.get("selected_views") or []
        payload["photo_assessments"] = (payload.get("photo_assessments") or []) + discarded
        _apply_object_match(payload)
        _normalize_empty_plot(payload)

        ids = payload.get("detected_stage_ids") or []
        detected_stage_id = max(ids) if ids else None
        prev = repo.latest_completed_before(session, object_id, captured_at) if captured_at else None
        dyn = compute_dynamics(
            {
                "progress_percent": payload.get("progress_percent"),
                "detected_stage_id": detected_stage_id,
                "captured_at": captured_at,
            },
            prev,
        )
        attention, reason = _merge_attention(
            bool(payload.get("attention_required")),
            payload.get("attention_reason"),
            dyn.get("dynamics_alert"),
        )
        if payload.get("object_match") == "mismatch":
            attention = True
            reason = reason or payload.get("mismatch_description") or "снимок не соответствует объекту"
            payload["attention_required"] = True
            payload["attention_reason"] = reason

        values = _base_values(job, cover, mode, version, result, captured_at, capture_day, survey_ids, primary_id)
        values.update(
            {
                "agent_status": "completed",
                "object_match": payload.get("object_match"),
                "detected_stage_id": detected_stage_id,
                "detected_stage": format_stage_label(ids),
                "stage_progress_percent": payload.get("stage_progress_percent"),
                "progress_percent": payload.get("progress_percent"),
                "compliance_status": payload.get("compliance_status"),
                "deviation_days": payload.get("deviation_days"),
                "deviation_severity": payload.get("deviation_severity"),
                "attention_required": attention,
                "attention_reason": reason,
                "overall_confidence": payload.get("overall_confidence"),
                "image_quality": payload.get("image_quality"),
                "looks_residential": payload.get("looks_residential"),
                "prev_report_id": dyn.get("prev_report_id"),
                "progress_delta": dyn.get("progress_delta"),
                "days_since_prev": dyn.get("days_since_prev"),
                "progress_rate_per_week": dyn.get("progress_rate_per_week"),
                "movement_status": dyn.get("movement_status"),
                "report_json": payload,
            }
        )
        html_key = _write_html(values, payload, cover)
        values["report_html_key"] = html_key
        saved = repo.upsert_report(session, values)
        repo.finish_queue(session, queue_id, "completed")
        log.info(
            "report saved",
            extra={"extra_data": {"report_id": saved.id, "batch_id": job.get("batch_id"), "movement": dyn.get("movement_status")}},
        )
    except Exception as exc:
        log.exception("job failed")
        cover = {"id": primary_id, "object_id": object_id, "batch_id": job.get("batch_id")}
        try:
            cover = repo.load_survey(session, primary_id) or cover
        except Exception:
            pass
        _fail(session, job, cover, "no_plan", "n/a", str(exc), attention_reason=str(exc))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        session.close()


_BUILD_MARKERS = (
    "фундамент", "стен", "короб", "кровл", "крыш", "котлован", "опалуб",
    "свая", "сваи", "бетон", "кирпич", "каркас", "перекрыт", "отсыпк",
)


def _checklist_item(item) -> tuple[str, str]:
    if isinstance(item, dict):
        return str(item.get("feature") or "").lower(), str(item.get("status") or "")
    return str(getattr(item, "feature", "") or "").lower(), str(getattr(item, "status", "") or "")


def _has_construction_markers(payload: dict) -> bool:
    for item in payload.get("checklist") or []:
        feature, status = _checklist_item(item)
        if status in {"present", "partial"} and any(hint in feature for hint in _BUILD_MARKERS):
            return True
    return False


def _normalize_empty_plot(payload: dict) -> None:
    """Пустой участок без следов стройки — 0%, не 3% из низа земляной шкалы."""
    ids = [int(i) for i in (payload.get("detected_stage_ids") or []) if str(i).lstrip("-").isdigit()]
    progress = payload.get("progress_percent")
    if progress is None:
        return
    try:
        progress = int(progress)
    except (TypeError, ValueError):
        return
    earthworks_only = ids and max(ids) <= 0
    if not earthworks_only or progress <= 0 or progress > 8:
        return
    if _has_construction_markers(payload):
        return
    payload["progress_percent"] = 0
    payload["stage_progress_percent"] = 0
    note = "Пустой участок без видимых строительных работ — готовность 0%."
    comment = payload.get("progress_comment") or ""
    if note not in comment:
        payload["progress_comment"] = f"{comment} {note}".strip()


def _apply_object_match(payload: dict) -> None:
    working = [
        item for item in (payload.get("photo_assessments") or [])
        if isinstance(item, dict) and item.get("relevance") != "outdated"
    ]
    if working and all(item.get("relevance") == "mismatch" for item in working):
        payload["object_match"] = "mismatch"


def _persist_crops(job: dict, crops_meta: list) -> list:
    stored = []
    folder = job.get("batch_id") or job.get("primary_survey_id") or job.get("survey_id") or "unknown"
    object_id = job.get("object_id") or "object"
    for crop in crops_meta:
        local = crop.get("local_path")
        key = f"agent_reports/{folder}/{object_id}/crop_{crop.get('index')}.jpg"
        if local and Path(local).exists():
            storage.write_bytes(key, Path(local).read_bytes())
            crop = dict(crop)
            crop["storage_key"] = key
            crop.pop("local_path", None)
        stored.append(crop)
    return stored


def _write_html(report: dict, payload: dict, survey: dict) -> str:
    folder = report.get("batch_id") or survey.get("batch_id") or survey.get("id")
    object_id = report.get("object_id") or survey.get("object_id") or "object"
    key = f"agent_reports/{folder}/{object_id}/report.html"
    html = render_html(report, payload, survey, survey.get("s3_key"))
    storage.write_bytes(key, html)
    return key


def _base_values(job, survey, mode, version, result, captured_at, capture_day, survey_ids, primary_id) -> dict:
    return {
        "survey_id": primary_id,
        "primary_survey_id": primary_id,
        "survey_ids": survey_ids,
        "batch_id": job.get("batch_id") or survey.get("batch_id"),
        "capture_date": capture_day,
        "object_id": survey.get("object_id") or job.get("object_id"),
        "captured_at": captured_at,
        "report_mode": mode,
        "prompt_version": version,
        "llm_calls": result.get("llm_calls"),
        "crops_used": result.get("crops_used"),
        "tokens_in": result.get("tokens_in"),
        "tokens_out": result.get("tokens_out"),
        "processing_ms": result.get("processing_ms"),
    }


def _fail(session, job, survey, mode, version, error_message, attention_reason=None) -> None:
    survey_ids = _as_int_list(job.get("survey_ids")) or ([job.get("survey_id")] if job.get("survey_id") else [])
    primary_id = job.get("primary_survey_id") or survey.get("id") or job.get("survey_id")
    values = {
        "survey_id": primary_id,
        "primary_survey_id": primary_id,
        "survey_ids": survey_ids,
        "batch_id": job.get("batch_id") or survey.get("batch_id"),
        "capture_date": job.get("capture_date"),
        "object_id": survey.get("object_id") or job["object_id"],
        "captured_at": survey.get("created_at"),
        "report_mode": mode,
        "agent_status": "failed",
        "error_message": error_message,
        "attention_required": True,
        "attention_reason": attention_reason or error_message,
        "prompt_version": version,
        "report_json": {"error": error_message},
        "movement_status": None,
    }
    values["report_html_key"] = _write_html(values, values["report_json"], survey)
    repo.upsert_report(session, values)
    repo.finish_queue(session, job["id"], "failed")


def _skip_stale(session, job, survey, mode, version, newer, capture_day) -> None:
    newer_at = newer.capture_date or newer.captured_at
    msg = f"снимки от {capture_day} старше последнего отчёта по объекту от {newer_at} — анализ пропущен"
    survey_ids = _as_int_list(job.get("survey_ids")) or ([job.get("survey_id")] if job.get("survey_id") else [])
    primary_id = job.get("primary_survey_id") or survey.get("id")
    values = {
        "survey_id": primary_id,
        "primary_survey_id": primary_id,
        "survey_ids": survey_ids,
        "batch_id": job.get("batch_id") or survey.get("batch_id"),
        "capture_date": capture_day,
        "object_id": survey.get("object_id"),
        "captured_at": survey.get("created_at"),
        "report_mode": mode,
        "agent_status": "skipped",
        "error_message": msg,
        "attention_required": True,
        "attention_reason": msg,
        "prompt_version": version,
        "report_json": {"skip": msg},
    }
    values["report_html_key"] = _write_html(values, values["report_json"], survey)
    repo.upsert_report(session, values)
    repo.finish_queue(session, job["id"], "completed")
    log.info("group skipped as stale", extra={"extra_data": {"object_id": survey.get("object_id"), "capture_date": str(capture_day)}})
