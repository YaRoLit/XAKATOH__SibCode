from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.models import User
from app.db.session import get_session as get_db

__all__ = ["get_db", "current_user", "require_manager", "require_operator"]


async def current_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Нужна авторизация")
    token = authorization[len("Bearer "):].strip()
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Недействительный токен")
    user = await session.get(User, payload.get("sub"))
    if user is None:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return user


def require_manager(user: User = Depends(current_user)) -> User:
    if user.role != "manager":
        raise HTTPException(status_code=403, detail="Доступ только для менеджера")
    return user


def require_operator(user: User = Depends(current_user)) -> User:
    if user.role not in {"operator", "manager"}:
        raise HTTPException(status_code=403, detail="Доступ только для оператора")
    return user
