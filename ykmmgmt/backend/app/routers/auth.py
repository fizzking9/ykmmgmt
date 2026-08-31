"""Auth endpoints — login, refresh, logout, and current-user profile."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.user import LoginRequest, UserProfile
from app.services.auth import (
    REFRESH_TOKEN_TYPE,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_KWARGS = {
    "httponly": True,
    "samesite": "lax",
    "path": "/",
    "secure": settings.cookie_secure,
}


def _set_auth_cookies(response: Response, user_id: int) -> None:
    response.set_cookie("access_token", create_access_token(user_id), **COOKIE_KWARGS)
    response.set_cookie("refresh_token", create_refresh_token(user_id), **COOKIE_KWARGS)


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


def _profile(user: User) -> UserProfile:
    return UserProfile(id=user.id, username=user.username, role=user.role)


async def _load_active_user_by_id(user_id: int, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    return user


@router.post("/login", response_model=UserProfile)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """Verify credentials and set httpOnly auth cookies."""
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash) or not user.is_active:
        # Same message for unknown user / wrong password / deactivated —
        # do not leak which usernames exist
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    _set_auth_cookies(response, user.id)
    return _profile(user)


@router.post("/refresh", response_model=UserProfile)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Rotate the refresh token cookie and issue a fresh access token."""
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    try:
        user_id = decode_token(token, REFRESH_TOKEN_TYPE)
    except TokenError as e:
        raise HTTPException(status_code=401, detail="未登录或登录已过期") from e

    user = await _load_active_user_by_id(user_id, db)
    _set_auth_cookies(response, user.id)
    return _profile(user)


@router.post("/logout")
async def logout(response: Response):
    """Clear both auth cookies."""
    _clear_auth_cookies(response)
    return {"detail": "已退出登录"}


@router.get("/me", response_model=UserProfile)
async def me(user: User = Depends(get_current_user)):
    """Return the current user's profile from the access token."""
    return _profile(user)
