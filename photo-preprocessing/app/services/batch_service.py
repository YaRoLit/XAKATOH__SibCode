import hashlib
import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.db import repositories as repo
from app.services import metadata_extractor, quality_checker, storage
from app.workers import validation_worker
import asyncio

log = get_logger(__name__)


async def create_batch(session: AsyncSession, operator_id: str) -> str:
    batch_id = str(uuid.uuid4())
    (Path(settings.upload_dir) / batch_id).mkdir(parents=True, exist_ok=True)
    await repo.create_batch(session, batch_id, operator_id)
    log.debug("batch: created %s operator=%s", batch_id, operator_id)
    return batch_id


async def upload_files(session: AsyncSession, batch_id: str, files: list[UploadFile]) -> dict:
    batch_dir = Path(settings.upload_dir) / batch_id
    accepted, rejected = 0, []
    for file in files:
        content = await file.read()
        errors = metadata_extractor.extract(content)["errors"]
        meta = metadata_extractor.extract(content)["metadata"] if not errors else {}
        errors += quality_checker.check(content)
        file_hash = hashlib.sha256(content).hexdigest()

        blocking = None
        if settings.idempotency.enabled and not errors:
            blocking = await repo.find_hash_blocking(session, file_hash)
        if blocking:
            errors.append(f"Файл уже загружен ранее (батч {blocking.batch_id}, survey {blocking.id})")

        if errors:
            await repo.add_survey(session, batch_id=batch_id, filename=file.filename,
                                  file_hash=file_hash, status="rejected",
                                  metadata_=meta or None, validation_errors=errors)
            rejected.append({"filename": file.filename, "reasons": errors})
            log.debug("upload: %s rejected at upload: %s", file.filename, errors)
            continue

        temp_path = batch_dir / file.filename
        temp_path.write_bytes(content)
        await repo.add_survey(session, batch_id=batch_id, filename=file.filename,
                              file_hash=file_hash, status="pending",
                              metadata_=meta, temp_path=str(temp_path))
        accepted += 1
        log.debug("upload: %s accepted (%d bytes)", file.filename, len(content))
    return {"accepted": accepted, "rejected": len(rejected), "rejected_files": rejected}


async def start_processing(session: AsyncSession, batch_id: str) -> None:
    await repo.set_batch_status(session, batch_id, "processing")
    asyncio.create_task(validation_worker.run_validation(batch_id))
    log.debug("batch: %s processing started", batch_id)


async def confirm(session: AsyncSession, batch_id: str) -> dict:
    batch = await repo.get_batch(session, batch_id)
    if batch is None or batch.status != "completed":
        return {"status": "error", "message": f"Батч не готов к подтверждению (status={batch.status if batch else None})"}
    
    surveys = await repo.list_surveys(session, batch_id)
    failed = []
    uploaded = 0
    
    for s in surveys:
        # Загружаем в хранилище ТОЛЬКО оригинал, если он еще не загружен и файл существует
        if s.status == "validated" and not s.s3_key and s.temp_path and Path(s.temp_path).exists():
            raw_key = f"raw/{s.object_id}/{batch_id}/{s.filename}"
            try:
                storage.upload(raw_key, Path(s.temp_path).read_bytes())
                await repo.update_survey(session, s.id, s3_key=raw_key)
                await repo.insert_queue_row(session, s.id, s.object_id)
                uploaded += 1
                log.debug("confirm: survey=%s -> S3 (original only) %s", s.id, raw_key)
            except Exception as e:
                failed.append({"survey_id": s.id, "filename": s.filename, "error": str(e)})
                log.error("confirm: survey=%s S3 FAILED: %s", s.id, e)
                
        # Непривязанные файлы помечаем как отклоненные
        if s.status == "needs_manual_match":
            await repo.update_survey(session, s.id, status="rejected",
                                     validation_errors=s.validation_errors +
                                     ["Объект не определён до подтверждения; фото удалено из temp. "
                                      "Повторная загрузка разрешена."])

    if failed:
        return {"status": "error", "message": "Часть файлов не загружена...", "uploaded": uploaded, "failed": failed}

    # Очистка временной папки
    batch_dir = Path(settings.upload_dir) / batch_id
    log.debug("confirm: attempting to remove temp dir %s", batch_dir)
    
    if batch_dir.exists():
        import shutil
        try:
            shutil.rmtree(batch_dir)  # <-- ВАЖНО: без ignore_errors=True
            log.debug("confirm: temp dir %s removed successfully", batch_dir)
        except Exception as e:
            log.error("confirm: FAILED to remove temp dir %s. Error: %s", batch_dir, e)
            
    await repo.set_batch_status(session, batch_id, "confirmed")
    return {"status": "ok", "uploaded_to_storage": uploaded}