from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_manager
from app.db.models import User
from app.schemas import AlertActionIn
from app.services.alerts import add_action, get_alert, list_alerts, serialize_alert

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
async def alerts(
    status: str | None = None,
    object_id: str | None = None,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_manager),
):
    items = await list_alerts(session, status=status, object_id=object_id)
    return {"items": [await serialize_alert(session, a) for a in items]}


@router.get("/{alert_id}")
async def alert_detail(
    alert_id: str,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_manager),
):
    alert = await get_alert(session, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Проблема не найдена")
    return await serialize_alert(session, alert)


@router.post("/{alert_id}/actions")
async def alert_action(
    alert_id: str,
    body: AlertActionIn,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(require_manager),
):
    alert = await get_alert(session, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Проблема не найдена")
    try:
        alert = await add_action(session, alert, user.id, status=body.status, comment=body.comment)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return await serialize_alert(session, alert)
