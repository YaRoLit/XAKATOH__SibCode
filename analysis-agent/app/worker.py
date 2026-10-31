import logging
import shutil
import uuid
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


def process_job(job: dict) -> None:
    session = SessionLocal()
    tmp_dir = Path("/tmp") / uuid.uuid4().hex
    tmp_dir.mkdir(parents=True, exist_ok=True)
    queue_id = job["id"]
    survey_id = job["survey_id"]
    object_id = job["object_id"]
    try:
        survey = repo.load_survey(session, survey_id)
        if survey is None:
            raise RuntimeError(f"survey {survey_id} not found")
        captured_at = survey.get("created_at")
        plan = repo.load_plan(session, object_id)
        plan_text = (plan.description or "").strip() if plan else ""
        mode = "with_plan" if plan_text else "no_plan"
        version, prompt = render_prompt(mode)

        image = storage.file_path(survey.get("s3_key"))
        if image is None:
            _fail(
                session, job, survey, mode, version,
                "файл не найден",
                attention_reason="файл не найден",
            )
            return

        newer = repo.newer_completed_exists(session, object_id, captured_at) if captured_at else None
        if newer is not None:
            _skip_stale(session, job, survey, mode, version, newer)
            return

        context = (
            f"Объект: {object_id}. Адрес: {survey.get('address') or '—'}. "
            f"Кадастровый номер: {survey.get('cadastral_number') or '—'}. "
            f"Дата съёмки: {captured_at}. "
        )
        if mode == "with_plan":
            context += f"\nПлан строительства:\n{plan_text}"
        else:
            context += "План строительства не задан."
        context += " Определи этап, прогресс и вызови crop_image_tool хотя бы один раз."

        log.info("run agent", extra={"extra_data": {"survey_id": survey_id, "mode": mode}})
        result = run_agent(mode, str(image), str(tmp_dir), context, prompt)
        if result["report"] is None:
            raise RuntimeError(f"невалидный JSON от модели: {result['parse_error']}")

        report = result["report"]
        crops_meta = _persist_crops(survey_id, result["crops_meta"])
        payload = report.model_dump()
        payload["crops_meta"] = crops_meta

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

        values = _base_values(survey, mode, version, result)
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
        html_key = _write_html(values, payload, survey)
        values["report_html_key"] = html_key
        saved = repo.upsert_report(session, values)
        repo.finish_queue(session, queue_id, "completed")
        log.info(
            "report saved",
            extra={"extra_data": {"report_id": saved.id, "survey_id": survey_id, "movement": dyn.get("movement_status")}},
        )
    except Exception as exc:
        log.exception("job failed")
        survey = repo.load_survey(session, survey_id) or {"id": survey_id, "object_id": object_id}
        _fail(session, job, survey, "no_plan", "n/a", str(exc), attention_reason=str(exc))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        session.close()


def _persist_crops(survey_id: int, crops_meta: list) -> list:
    stored = []
    for crop in crops_meta:
        local = crop.get("local_path")
        key = f"agent_reports/{survey_id}/crop_{crop.get('index')}.jpg"
        if local and Path(local).exists():
            storage.write_bytes(key, Path(local).read_bytes())
            crop = dict(crop)
            crop["storage_key"] = key
            crop.pop("local_path", None)
        stored.append(crop)
    return stored


def _write_html(report: dict, payload: dict, survey: dict) -> str:
    key = f"agent_reports/{survey['id']}/report.html"
    html = render_html(report, payload, survey, survey.get("s3_key"))
    storage.write_bytes(key, html)
    return key


def _base_values(survey: dict, mode: str, version: str, result: dict) -> dict:
    return {
        "survey_id": survey["id"],
        "object_id": survey.get("object_id"),
        "captured_at": survey.get("created_at"),
        "report_mode": mode,
        "prompt_version": version,
        "llm_calls": result.get("llm_calls"),
        "crops_used": result.get("crops_used"),
        "tokens_in": result.get("tokens_in"),
        "tokens_out": result.get("tokens_out"),
        "processing_ms": result.get("processing_ms"),
    }


def _fail(session, job, survey, mode, version, error_message, attention_reason=None) -> None:
    values = {
        "survey_id": survey.get("id") or job["survey_id"],
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


def _skip_stale(session, job, survey, mode, version, newer) -> None:
    captured = survey.get("created_at")
    newer_at = newer.captured_at
    msg = f"снимок от {captured} старше последнего отчёта по объекту от {newer_at} — анализ пропущен"
    values = {
        "survey_id": survey["id"],
        "object_id": survey.get("object_id"),
        "captured_at": captured,
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
    log.info("survey skipped as stale", extra={"extra_data": {"survey_id": survey["id"]}})
