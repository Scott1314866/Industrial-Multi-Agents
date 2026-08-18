from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, cast

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from industrial_agents.domain.security import decode_token
from industrial_agents.runtime import Runtime


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    email: str
    display_name: str
    role: str
    tenant_id: str
    session_id: str


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_runtime(request: Request) -> Runtime:
    return cast(Runtime, request.app.state.runtime)


async def current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> AuthenticatedUser:
    try:
        payload = decode_token(token, runtime.settings)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "登录状态无效或已过期"},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    session_id = payload.get("sid")
    if not isinstance(session_id, str):
        raise HTTPException(status_code=401, detail={"code": "SESSION_REQUIRED"})
    user = await runtime.repository.get_user(str(payload["sub"]))
    if not user or not user.active:
        raise HTTPException(status_code=401, detail={"code": "USER_DISABLED"})
    if not await runtime.repository.get_active_session(session_id, user.id):
        raise HTTPException(status_code=401, detail={"code": "SESSION_REVOKED"})
    return AuthenticatedUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        tenant_id=user.tenant_id,
        session_id=session_id,
    )


CurrentUser = Annotated[AuthenticatedUser, Depends(current_user)]
RuntimeDep = Annotated[Runtime, Depends(get_runtime)]
