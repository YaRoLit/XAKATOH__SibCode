from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_session as get_db

__all__ = ["get_db", "check_auth"]


def check_auth(authorization: str = Header(...)) -> None:
    """Проверяет Bearer токен."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    
    token = authorization[len("Bearer "):].strip()
    if token != settings.api_token:
        raise HTTPException(status_code=401, detail="Invalid token")