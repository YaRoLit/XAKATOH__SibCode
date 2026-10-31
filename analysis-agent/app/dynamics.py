from datetime import datetime

from app.db.models import AnalysisReport
from app.settings import yaml_config


def compute_dynamics(current: dict, previous: AnalysisReport | None) -> dict:
    dyn = yaml_config.get("dynamics") or {}
    active = float(dyn.get("progress_active_delta", 2))
    regress = float(dyn.get("progress_regress_delta", -5))
    stalled_days = int(dyn.get("stalled_days", 14))
    alert_first = bool(dyn.get("alert_on_first_report", True))

    result = {
        "prev_report_id": None,
        "progress_delta": None,
        "days_since_prev": None,
        "progress_rate_per_week": None,
        "movement_status": "no_baseline",
        "dynamics_alert": None,
    }
    if previous is None or previous.progress_percent is None:
        result["movement_status"] = "no_baseline"
        if alert_first:
            result["dynamics_alert"] = "первый отчёт по объекту, нет базы для сравнения динамики"
        return result

    cur_progress = current.get("progress_percent")
    cur_stage = current.get("detected_stage_id")
    prev_stage = previous.detected_stage_id
    captured = current.get("captured_at")
    prev_captured = previous.captured_at
    days = None
    if captured and prev_captured:
        days = max(0, int((captured - prev_captured).total_seconds() // 86400))

    delta = None
    if cur_progress is not None:
        delta = float(cur_progress) - float(previous.progress_percent)
    rate = None
    if delta is not None and days is not None:
        rate = round(delta * 7 / days, 2) if days > 0 else None

    status = "no_significant_change"
    alert = None
    if prev_stage is not None and cur_stage is not None and cur_stage > prev_stage:
        status = "progressing"
    elif prev_stage is not None and cur_stage is not None and cur_stage < prev_stage:
        status = "regressed"
        alert = "этап снизился — проверить"
    elif delta is not None and delta >= active:
        status = "progressing"
    elif delta is not None and delta <= regress:
        status = "regressed"
        alert = f"прогресс снизился на {abs(delta):.0f}%"
    elif delta is not None and abs(delta) < active and days is not None and days >= stalled_days:
        status = "stalled"
        alert = f"нет движения ≥ {stalled_days} дней"
    elif delta is not None and abs(delta) < active:
        status = "no_significant_change"

    result.update(
        {
            "prev_report_id": previous.id,
            "progress_delta": delta,
            "days_since_prev": days,
            "progress_rate_per_week": rate,
            "movement_status": status,
            "dynamics_alert": alert,
        }
    )
    return result
