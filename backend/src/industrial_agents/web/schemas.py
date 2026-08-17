from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255, pattern=r"^[^\s@]+@[^\s@]+$")
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    tenant_id: str


class ConversationCreate(BaseModel):
    machine_id: str = Field(min_length=3, max_length=64)
    title: str = Field(default="新诊断会话", min_length=1, max_length=200)


class ConversationResponse(BaseModel):
    id: str
    machine_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class RunCreate(BaseModel):
    query: str = Field(min_length=2, max_length=4000)
    idempotency_key: str | None = Field(default=None, max_length=100)


class RunResponse(BaseModel):
    id: str
    conversation_id: str
    machine_id: str
    status: str
    query: str
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
