"""Pydantic schemas for auth and user management."""

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Roles accepted on input — `root` can never be assigned via the API
InputRole = Literal["admin", "user"]


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class UserProfile(BaseModel):
    id: int
    username: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100, description="用户名（3-100 字符）")
    password: str = Field(..., min_length=8, max_length=200, description="密码（至少 8 位）")
    role: InputRole = Field(..., description="角色: admin/user")


class UserUpdate(BaseModel):
    """Update role and/or reset password — all fields optional."""

    role: InputRole | None = Field(None, description="新角色: admin/user")
    password: str | None = Field(None, min_length=8, max_length=200, description="新密码（至少 8 位）")


class UserStatusUpdate(BaseModel):
    is_active: bool
