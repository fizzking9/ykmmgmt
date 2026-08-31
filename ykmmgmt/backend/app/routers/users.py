"""User management endpoints — hierarchy-enforced CRUD on /api/users.

Hierarchy rules (see specs/2026-08-28-auth-multi-user):
- root: sees all users; can create admins and users; can manage admins
  and users; the root account itself is immutable via the API.
- admin: sees admins and users (root hidden); can create/manage only
  `user` accounts; cannot touch other admins or root.
- Nobody can modify or deactivate their own account.
- The `root` role can never be assigned through the API.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_admin
from app.models.user import ROLE_ADMIN, ROLE_ROOT, ROLE_USER, User
from app.schemas.user import UserCreate, UserOut, UserStatusUpdate, UserUpdate
from app.services.auth import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


def _assert_not_self(actor: User, target_id: int) -> None:
    if actor.id == target_id:
        raise HTTPException(status_code=409, detail="不能对当前登录账号执行此操作")


def _assert_not_target_root(target: User) -> None:
    if target.role == ROLE_ROOT:
        raise HTTPException(status_code=409, detail="root 账号不允许通过接口修改")


def _assert_can_manage(actor: User, target: User) -> None:
    """Hierarchy check before any mutation on ``target``."""
    _assert_not_self(actor, target.id)
    _assert_not_target_root(target)
    if actor.role == ROLE_ADMIN and target.role != ROLE_USER:
        raise HTTPException(status_code=403, detail="管理员只能管理普通用户账号")


def _assert_can_assign(actor: User, role: str) -> None:
    """Whether ``actor`` may grant ``role`` to someone else."""
    if role == ROLE_ROOT:
        raise HTTPException(status_code=403, detail="root 角色不允许通过接口分配")
    if actor.role == ROLE_ADMIN and role != ROLE_USER:
        raise HTTPException(status_code=403, detail="管理员只能创建/设置普通用户角色")


async def _get_user_or_404(user_id: int, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail=f"用户 '{user_id}' 不存在")
    return user


@router.get("", response_model=list[UserOut])
async def list_users(actor: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """List users. Root sees all; admin sees admins and users (root hidden)."""
    stmt = select(User).order_by(User.id)
    if actor.role != ROLE_ROOT:
        stmt = stmt.where(User.role != ROLE_ROOT)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate,
    actor: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a user. Root may create admins and users; admin only users."""
    _assert_can_assign(actor, body.role)

    dup = await db.execute(select(User.id).where(User.username == body.username))
    if dup.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail=f"用户名 '{body.username}' 已存在")

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    body: UserUpdate,
    actor: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update role and/or reset password with hierarchy enforcement."""
    user = await _get_user_or_404(user_id, db)
    _assert_can_manage(actor, user)

    if body.role is not None:
        _assert_can_assign(actor, body.role)
        # admin may never grant admin to someone (already enforced), but
        # root may switch between admin/user freely
        if user.role == ROLE_ADMIN and actor.role == ROLE_ADMIN:
            raise HTTPException(status_code=403, detail="管理员不能修改其他管理员")
        user.role = body.role

    if body.password is not None:
        user.password_hash = hash_password(body.password)

    await db.flush()
    await db.refresh(user)
    return user


@router.put("/{user_id}/status", response_model=UserOut)
async def update_user_status(
    user_id: int,
    body: UserStatusUpdate,
    actor: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Activate or deactivate a user."""
    user = await _get_user_or_404(user_id, db)
    _assert_can_manage(actor, user)
    user.is_active = body.is_active
    await db.flush()
    await db.refresh(user)
    return user
