from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_operator
from app.db.models import User
from app.services import operator as operator_service

router = APIRouter(prefix="/api/operator", tags=["operator"])


@router.get("/tasks")
async def tasks(session: AsyncSession = Depends(get_db), _: User = Depends(require_operator)):
    return {"items": await operator_service.shooting_tasks(session)}


@router.get("/rejected")
async def rejected(session: AsyncSession = Depends(get_db), _: User = Depends(require_operator)):
    return {"items": await operator_service.rejected_photos(session)}


@router.get("/recent")
async def recent(session: AsyncSession = Depends(get_db), _: User = Depends(require_operator)):
    return {
        "surveys": await operator_service.recent_surveys(session),
        "batches": await operator_service.recent_batches(session),
    }
