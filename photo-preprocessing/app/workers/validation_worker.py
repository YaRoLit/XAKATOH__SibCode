import asyncio
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

from app.config import settings
from app.core.logging import get_logger
from app.db import repositories as repo
from app.db.session import SessionLocal
from app.services import coverage_calculator, object_matcher, period_gate

log = get_logger(__name__)


async def _process_single_survey(session, survey, objects):
    """Обработка одного файла. Вынесена в отдельную функцию для asyncio.wait_for."""
    meta = survey.metadata_
    if not meta or "coordinates" not in meta:
        await repo.update_survey(
            session, survey.id, status="rejected",
            validation_errors=survey.validation_errors + ["Неполные метаданные для валидации"]
        )
        log.debug("worker: survey=%s rejected (incomplete metadata)", survey.id)
        return

    obj = object_matcher.match(
        meta["coordinates"]["lat"],
        meta["coordinates"]["lon"],
        objects,
        settings.validation.gps_buffer_m,
        settings.validation.centroid_buffer_m,
    )
    if obj is None:
        await repo.update_survey(
            session, survey.id, status="needs_manual_match",
            validation_errors=survey.validation_errors + ["Объект не найден по координатам съемки"]
        )
        log.debug("worker: survey=%s needs_manual_match", survey.id)
        return

    photo_day = period_gate.exif_date(survey)
    last_period = await period_gate.last_stored_period(session, obj.id)
    stale = period_gate.stale_reason(photo_day, last_period)
    if stale:
        await repo.update_survey(
            session, survey.id, status="rejected", object_id=obj.id,
            validation_errors=survey.validation_errors + [stale],
        )
        log.debug("worker: survey=%s rejected stale day=%s last=%s", survey.id, photo_day, last_period)
        return

    img = cv2.imread(str(Path(survey.temp_path)), cv2.IMREAD_COLOR)
    if img is None:
        await repo.update_survey(
            session, survey.id, status="rejected",
            validation_errors=survey.validation_errors + ["Не удалось прочитать файл изображения"]
        )
        log.debug("worker: survey=%s rejected (imread failed)", survey.id)
        return

    corners = obj.plot_corners or []
    if len(corners) == 1:
        # Одна точка = центроид: GPS уже попал в радиус, покрытие по полигону не считаем.
        coverage = 1.0
    elif "altitude" not in (meta or {}):
        # Временно: высота отключена, GSD-покрытие без неё ненадёжно.
        coverage = 1.0
    else:
        coverage, _, _ = coverage_calculator.compute(img, meta, corners)

    if coverage < settings.validation.min_coverage:
        await repo.update_survey(
            session, survey.id, status="rejected", object_id=obj.id,
            coverage=coverage,
            validation_errors=survey.validation_errors + [
                f"Покрытие участка {coverage:.0%} ниже порога {settings.validation.min_coverage:.0%}"
            ]
        )
        log.debug("worker: survey=%s rejected coverage=%.2f", survey.id, coverage)
        return

    # Превью НЕ генерируем здесь — оно делается on-demand при запросе /surveys/{id}/photo
    await repo.update_survey(
        session, survey.id, status="validated",
        object_id=obj.id, coverage=coverage
    )
    log.debug("worker: survey=%s validated obj=%s coverage=%.2f", survey.id, obj.id, coverage)


async def run_validation(batch_id: str) -> None:
    log.debug("worker: start batch=%s", batch_id)
    async with SessionLocal() as session:

        reset_count = await repo.reset_stuck_surveys(session, batch_id)
        if reset_count > 0:
            log.warning("worker: reset %d stuck 'processing' surveys to 'pending'", reset_count)
        
        surveys = await repo.get_pending_surveys(session, batch_id)

        surveys = await repo.get_pending_surveys(session, batch_id)
        objects = await repo.active_objects(session)
        timeout = settings.validation.file_timeout_sec

        for survey in surveys:
            t0 = time.monotonic()
            await repo.update_survey(session, survey.id, status="processing")

            try:
                # Обёртка в wait_for: если обработка дольше таймаута — летит TimeoutError
                await asyncio.wait_for(
                    _process_single_survey(session, survey, objects),
                    timeout=timeout
                )
                elapsed = time.monotonic() - t0
                log.debug("worker: survey=%s finished in %.2fs", survey.id, elapsed)

            except asyncio.TimeoutError:
                log.warning("worker: survey=%s TIMEOUT after %.1fs", survey.id, timeout)
                await repo.update_survey(
                    session, survey.id, status="rejected",
                    validation_errors=survey.validation_errors + [
                        f"Превышено время обработки ({timeout:.0f} сек). Файл пропущен."
                    ]
                )
            except Exception as e:
                log.error("worker: survey=%s FAILED: %s", survey.id, e, exc_info=True)
                await repo.update_survey(
                    session, survey.id, status="rejected",
                    validation_errors=survey.validation_errors + [
                        f"Внутренняя ошибка обработки: {type(e).__name__}: {e}"
                    ]
                )

        try:
            rejected_old = await period_gate.reject_older_days_in_batch(session, batch_id)
            if rejected_old:
                log.debug("worker: batch=%s rejected %s photos from older days", batch_id, rejected_old)
        except Exception as e:
            log.error("worker: period gate failed: %s", e, exc_info=True)

        await repo.set_batch_status(session, batch_id, "completed")
        try:
            grouped: dict[str, list[str]] = defaultdict(list)
            for survey in await repo.list_surveys(session, batch_id):
                if survey.status == "validated" and survey.object_id:
                    grouped[survey.object_id].append(survey.filename)
            for object_id, names in grouped.items():
                await repo.notify_new_photos(session, object_id, names, batch_id)
        except Exception as e:
            log.error("worker: photo notify failed: %s", e, exc_info=True)
    log.debug("worker: batch=%s completed", batch_id)