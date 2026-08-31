"""Create the initial root (super admin) account from environment variables.

Reads ``ROOT_USERNAME`` / ``ROOT_PASSWORD`` from .env (see app.core.config).
Idempotent — safe to run repeatedly: if a root account already exists,
the password is left untouched.

Usage (from backend/):
    python -m scripts.seed_root
"""

import asyncio
import sys

from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory, engine
from app.models.user import ROLE_ROOT, User
from app.services.auth import hash_password


async def seed_root() -> int:
    if not settings.root_username or not settings.root_password:
        print("错误: 未配置 ROOT_USERNAME / ROOT_PASSWORD 环境变量，无法创建初始账号", file=sys.stderr)
        return 1

    async with async_session_factory() as session:
        # Idempotency is keyed by USERNAME, not role — the database may hold
        # other root-role accounts (e.g. test fixtures) and that must not
        # break re-runs or create duplicates.
        result = await session.execute(
            select(User).where(User.username == settings.root_username)
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            print(f"用户 '{existing.username}' 已存在，跳过创建")
            return 0

        user = User(
            username=settings.root_username,
            password_hash=hash_password(settings.root_password),
            role=ROLE_ROOT,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        print(f"已创建 root 账号 '{settings.root_username}'")
        return 0


if __name__ == "__main__":

    async def _main() -> int:
        try:
            return await seed_root()
        finally:
            await engine.dispose()

    sys.exit(asyncio.run(_main()))
