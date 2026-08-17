from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from industrial_agents.domain.security import decode_token
from industrial_agents.infrastructure.database import UserRow
from industrial_agents.runtime import Runtime

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_runtime(request: Request) -> Runtime:
    return request.app.state.runtime


async def current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> UserRow:
    try:
        payload = decode_token(token, runtime.settings)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "登录状态无效或已过期"},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    user = await runtime.repository.get_user(str(payload["sub"]))
    if not user or not user.active:
        raise HTTPException(status_code=401, detail={"code": "USER_DISABLED"})
    return user


CurrentUser = Annotated[UserRow, Depends(current_user)]
RuntimeDep = Annotated[Runtime, Depends(get_runtime)]
