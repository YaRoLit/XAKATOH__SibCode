from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, get_db
from app.core.security import create_token, verify_password
from app.db.models import User
from app.schemas import LoginRequest, TokenOut, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_db)):
    res = await session.execute(select(User).where(User.login == body.login))
    user = res.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    token = create_token(user.id, user.role, user.login)
    return TokenOut(token=token, user=_user_out(user))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)):
    return _user_out(user)


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, login=user.login, role=user.role, display_name=user.display_name)
