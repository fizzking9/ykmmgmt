"""Auth endpoints — login, refresh, logout, and current-user profile."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.user import LoginRequest, ProfileUpdate, UserProfile
from app.services.auth import (
    REFRESH_TOKEN_TYPE,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
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


@router.put("/profile", response_model=UserProfile)
async def update_profile(
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Self-service update of the current user's username and/or password.

    Unlike the admin user-management endpoints, hierarchy rules do not
    apply here — every authenticated account (root included) may change
    its own credentials. The current password is confirmed only when
    changing the password; username changes need no re-authentication.
    """
    if body.new_password is not None:
        if not body.current_password or not verify_password(body.current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="当前密码不正确")
        user.password_hash = hash_password(body.new_password)

    if body.username is not None and body.username != user.username:
        dup = await db.execute(select(User.id).where(User.username == body.username))
        if dup.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail=f"用户名 '{body.username}' 已存在")
        user.username = body.username

    await db.flush()
    await db.refresh(user)
    return _profile(user)
