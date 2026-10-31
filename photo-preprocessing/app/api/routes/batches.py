from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models import Survey
from app.services import batch_service

router = APIRouter(prefix="/v1/batches", tags=["batches"])


@router.post("")
async def create_batch(operator_id: str = "op_001", session: AsyncSession = Depends(get_db)):
    return {"batch_id": await batch_service.create_batch(session, operator_id)}


@router.post("/{batch_id}/upload")
async def upload(batch_id: str, files: list[UploadFile] = File(...), session: AsyncSession = Depends(get_db)):
    if await _get_or_404(session, batch_id):
        return await batch_service.upload_files(session, batch_id, files)


@router.post("/{batch_id}/process")
async def process(batch_id: str, session: AsyncSession = Depends(get_db)):
    await _get_or_404(session, batch_id)
    await batch_service.start_processing(session, batch_id)
    return {"status": "processing_started"}


@router.get("/{batch_id}/progress")
async def progress(batch_id: str, session: AsyncSession = Depends(get_db)):
    batch = await _get_or_404(session, batch_id)
    res = await session.execute(
        select(Survey.status, func.count()).where(Survey.batch_id == batch_id).group_by(Survey.status))
    counts = dict(res.all())
    return {"batch_status": batch.status, "total": sum(counts.values()), **counts}


@router.get("/{batch_id}/results")
async def results(batch_id: str, session: AsyncSession = Depends(get_db)):
    await _get_or_404(session, batch_id)
    surveys = await repo_list(session, batch_id)
    order = {"rejected": 0, "needs_manual_match": 1, "duplicate": 2, "validated": 3, "pending": 4, "processing": 4}
    surveys.sort(key=lambda s: order.get(s.status, 5))
    return {"batch_id": batch_id, "files": [_survey_brief(s) for s in surveys]}


@router.post("/{batch_id}/confirm")
async def confirm(batch_id: str, session: AsyncSession = Depends(get_db)):
    await _get_or_404(session, batch_id)
    return await batch_service.confirm(session, batch_id)


async def _get_or_404(session: AsyncSession, batch_id: str):
    from app.db import repositories as repo
    batch = await repo.get_batch(session, batch_id)
    if batch is None:
        raise HTTPException(404, "Batch not found")
    return batch


async def repo_list(session: AsyncSession, batch_id: str):
    from app.db import repositories as repo
    return await repo.list_surveys(session, batch_id)


def _survey_brief(s: Survey) -> dict:
    return {"survey_id": s.id, "filename": s.filename, "status": s.status,
            "object_id": s.object_id, "coverage": s.coverage,
            "duplicate_of": s.duplicate_of, "errors": s.validation_errors}