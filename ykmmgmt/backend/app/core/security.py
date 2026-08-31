"""Auth dependencies: current-user resolution and role guards."""

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import ROLE_ADMIN, ROLE_ROOT, User
from app.services.auth import ACCESS_TOKEN_TYPE, TokenError, decode_token

# Consistent 401 body — the frontend treats this as "re-login required"
UNAUTHORIZED_DETAIL = "未登录或登录已过期"


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    """Resolve the active user from the ``access_token`` cookie."""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail=UNAUTHORIZED_DETAIL)

    try:
        user_id = decode_token(token, ACCESS_TOKEN_TYPE)
    except TokenError as e:
        raise HTTPException(status_code=401, detail=UNAUTHORIZED_DETAIL) from e

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail=UNAUTHORIZED_DETAIL)
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Allow admin and root only (L2+)."""
    if user.role not in (ROLE_ADMIN, ROLE_ROOT):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


async def require_root(user: User = Depends(get_current_user)) -> User:
    """Allow root only (L1)."""
    if user.role != ROLE_ROOT:
        raise HTTPException(status_code=403, detail="需要超级管理员权限")
    return user
