from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

import jwt
from pwdlib import PasswordHash

from industrial_agents.config import Settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return str(password_hash.hash(password))


def verify_password(password: str, encoded: str) -> bool:
    return bool(password_hash.verify(password, encoded))


def create_token(
    *,
    subject: str,
    role: str,
    tenant_id: str,
    token_type: str,
    settings: Settings,
    session_id: str | None = None,
    token_id: str | None = None,
) -> str:
    now = datetime.now(UTC)
    lifetime = (
        timedelta(minutes=settings.access_token_minutes)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_days)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "tenant_id": tenant_id,
        "type": token_type,
        "jti": token_id or str(uuid.uuid4()),
        "iat": now,
        "exp": now + lifetime,
    }
    if session_id:
        payload["sid"] = session_id
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def token_digest(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def decode_token(token: str, settings: Settings, expected_type: str = "access") -> dict[str, Any]:
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "role", "tenant_id", "type", "sid", "jti", "iat", "exp"]},
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Unexpected token type")
    if not all(isinstance(payload.get(name), str) for name in ("sub", "role", "tenant_id", "sid", "jti")):
        raise jwt.InvalidTokenError("Token claims are malformed")
    return payload
