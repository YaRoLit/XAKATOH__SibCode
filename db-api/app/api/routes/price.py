from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_db, require_manager
from app.db.models import User
from app.services import objects as object_service
from app.services import price_estimate

router = APIRouter(prefix="/api/objects", tags=["price-estimate"])


@router.get("/{object_id}/price-estimate")
async def get_price_estimate(
    object_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(current_user),
):
    if await object_service.get_object(session, object_id) is None:
        raise HTTPException(status_code=404, detail="Объект не найден")
    return await price_estimate.estimate_state(session, object_id)


@router.post("/{object_id}/price-estimate")
async def create_price_estimate(
    object_id: str,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_manager),
):
    obj = await object_service.get_object(session, object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Объект не найден")
    try:
        return await price_estimate.request_estimate(session, obj, user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
