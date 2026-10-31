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
from app.services import coverage_calculator, object_matcher

log = get_logger(__name__)


async def _process_single_survey(session, survey, objects):
    """Обработка одного файла. Вынесена в отдельную функцию для asyncio.wait_for."""
    meta = survey.metadata_
    if not meta or "coordinates" not in meta or "altitude" not in meta:
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
        settings.validation.gps_buffer_m
    )
    if obj is None:
        await repo.update_survey(
            session, survey.id, status="needs_manual_match",
            validation_errors=survey.validation_errors + ["Объект не найден по координатам съемки"]
        )
        log.debug("worker: survey=%s needs_manual_match", survey.id)
        return

    img = cv2.imread(str(Path(survey.temp_path)), cv2.IMREAD_COLOR)
    if img is None:
        await repo.update_survey(
            session, survey.id, status="rejected",
            validation_errors=survey.validation_errors + ["Не удалось прочитать файл изображения"]
        )
        log.debug("worker: survey=%s rejected (imread failed)", survey.id)
        return

    coverage, norm, norm_corners = coverage_calculator.compute(img, meta, obj.plot_corners)

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

        # Дедупликация (тоже в try, чтобы не сломать завершение батча)
        try:
            if settings.dedup.enabled:
                await _dedup_pass(session, batch_id)
        except Exception as e:
            log.error("worker: dedup pass failed: %s", e, exc_info=True)

        await repo.set_batch_status(session, batch_id, "completed")
    log.debug("worker: batch=%s completed", batch_id)


async def _dedup_pass(session, batch_id: str) -> None:
    surveys = await repo.list_surveys(session, batch_id)
    groups: dict[str, list] = defaultdict(list)
    for s in surveys:
        if s.status == "validated" and s.object_id:
            groups[s.object_id].append(s)

    for object_id, group in groups.items():
        if len(group) < 2:
            continue
        group.sort(
            key=lambda s: (s.metadata_ or {}).get("datetime_original") or s.created_at.isoformat(),
            reverse=True
        )
        winner, *rest = group
        for loser in rest:
            await repo.update_survey(
                session, loser.id, status="duplicate", duplicate_of=winner.id,
                validation_errors=loser.validation_errors + [
                    f"Дубликат: основным выбран снимок {winner.filename} "
                    "(более поздний по времени съемки)"
                ]
            )
        log.debug("worker: dedup object=%s winner=%s duplicates=%s",
                  object_id, winner.id, [r.id for r in rest])