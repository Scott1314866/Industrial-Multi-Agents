from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Cookie, Header, HTTPException, Response, status
from fastapi.responses import StreamingResponse

from industrial_agents.domain.models import GraphRequest, Role
from industrial_agents.domain.security import create_token, decode_token, token_digest
from industrial_agents.infrastructure.database import RunRow, UserRow
from industrial_agents.web.dependencies import AuthenticatedUser, CurrentUser, RuntimeDep
from industrial_agents.web.schemas import (
    AuthSessionResponse,
    ConversationCreate,
    ConversationResponse,
    LoginRequest,
    RunCreate,
    RunResponse,
    TokenResponse,
    UserResponse,
)

router = APIRouter()


def _user_response(user: UserRow | AuthenticatedUser) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        tenant_id=user.tenant_id,
    )


def _run_response(row: RunRow) -> RunResponse:
    return RunResponse(
        id=row.id,
        conversation_id=row.conversation_id,
        machine_id=row.machine_id,
        status=row.status,
        query=row.query,
        result=row.result_payload,
        error=row.error_message,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _set_refresh_cookie(response: Response, runtime: RuntimeDep, refresh: str) -> None:
    response.set_cookie(
        "ima_refresh",
        refresh,
        httponly=True,
        secure=runtime.settings.environment == "production",
        samesite="lax",
        max_age=runtime.settings.refresh_token_days * 86400,
        path=f"{runtime.settings.api_prefix}/auth",
    )


def _clear_refresh_cookie(response: Response, runtime: RuntimeDep) -> None:
    response.delete_cookie("ima_refresh", path=f"{runtime.settings.api_prefix}/auth")


def _refresh_error(code: str, runtime: RuntimeDep) -> HTTPException:
    cookie = (
        f'ima_refresh=""; HttpOnly; Max-Age=0; Path={runtime.settings.api_prefix}/auth; SameSite=lax'
        + ("; Secure" if runtime.settings.environment == "production" else "")
    )
    return HTTPException(status_code=401, detail={"code": code}, headers={"Set-Cookie": cookie})


async def _require_machine(runtime: RuntimeDep, user: CurrentUser, machine_id: str) -> None:
    if not await runtime.machine_access.can_access(user.id, machine_id):
        raise HTTPException(status_code=404, detail={"code": "MACHINE_NOT_FOUND"})


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, response: Response, runtime: RuntimeDep) -> TokenResponse:
    user = await runtime.repository.authenticate(payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "邮箱或密码错误"},
        )
    session_id = str(uuid.uuid4())
    refresh_id = str(uuid.uuid4())
    expires_at = datetime.now(UTC) + timedelta(days=runtime.settings.refresh_token_days)
    refresh = create_token(
        subject=user.id,
        role=user.role,
        tenant_id=user.tenant_id,
        token_type="refresh",
        settings=runtime.settings,
        session_id=session_id,
        token_id=refresh_id,
    )
    await runtime.repository.create_auth_session(
        session_id=session_id,
        user_id=user.id,
        token_id=refresh_id,
        token_digest=token_digest(refresh),
        expires_at=expires_at,
    )
    access = create_token(
        subject=user.id,
        role=user.role,
        tenant_id=user.tenant_id,
        token_type="access",
        settings=runtime.settings,
        session_id=session_id,
    )
    _set_refresh_cookie(response, runtime, refresh)
    await runtime.repository.audit(
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="auth.login",
        resource_type="user",
        resource_id=user.id,
    )
    return TokenResponse(
        access_token=access,
        expires_in=runtime.settings.access_token_minutes * 60,
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    runtime: RuntimeDep,
    ima_refresh: str | None = Cookie(default=None),
) -> TokenResponse:
    if not ima_refresh:
        raise HTTPException(status_code=401, detail={"code": "MISSING_REFRESH_TOKEN"})
    try:
        payload = decode_token(ima_refresh, runtime.settings, expected_type="refresh")
    except jwt.PyJWTError as exc:
        raise _refresh_error("INVALID_REFRESH_TOKEN", runtime) from exc
    user = await runtime.repository.get_user(str(payload["sub"]))
    if not user or not user.active:
        raise _refresh_error("USER_DISABLED", runtime)
    session_id = payload.get("sid")
    if not isinstance(session_id, str) or not isinstance(payload.get("jti"), str):
        raise _refresh_error("INVALID_REFRESH_TOKEN", runtime)
    refresh_id = str(uuid.uuid4())
    expires_at = datetime.now(UTC) + timedelta(days=runtime.settings.refresh_token_days)
    refresh = create_token(
        subject=user.id,
        role=user.role,
        tenant_id=user.tenant_id,
        token_type="refresh",
        settings=runtime.settings,
        session_id=session_id,
        token_id=refresh_id,
    )
    rotation = await runtime.repository.rotate_refresh_token(
        session_id=session_id,
        old_digest=token_digest(ima_refresh),
        new_token_id=refresh_id,
        new_digest=token_digest(refresh),
        expires_at=expires_at,
    )
    if rotation != "rotated":
        code = "REFRESH_TOKEN_REUSED" if rotation == "reused" else "INVALID_REFRESH_TOKEN"
        raise _refresh_error(code, runtime)
    access = create_token(
        subject=user.id,
        role=user.role,
        tenant_id=user.tenant_id,
        token_type="access",
        settings=runtime.settings,
        session_id=session_id,
    )
    _set_refresh_cookie(response, runtime, refresh)
    return TokenResponse(access_token=access, expires_in=runtime.settings.access_token_minutes * 60)


@router.post("/auth/logout", status_code=204, response_class=Response)
async def logout(
    response: Response,
    runtime: RuntimeDep,
    ima_refresh: str | None = Cookie(default=None),
) -> Response:
    if ima_refresh:
        await runtime.repository.revoke_auth_session_by_digest(token_digest(ima_refresh))
    _clear_refresh_cookie(response, runtime)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/auth/me", response_model=UserResponse)
async def me(user: CurrentUser) -> UserResponse:
    return _user_response(user)


@router.get("/auth/sessions", response_model=list[AuthSessionResponse])
async def list_auth_sessions(user: CurrentUser, runtime: RuntimeDep) -> list[AuthSessionResponse]:
    rows = await runtime.repository.list_auth_sessions(user.id)
    return [
        AuthSessionResponse(
            id=row.id,
            created_at=row.created_at,
            last_seen_at=row.last_seen_at,
            expires_at=row.expires_at,
            current=row.id == user.session_id,
        )
        for row in rows
    ]


@router.delete("/auth/sessions/{session_id}", status_code=204, response_class=Response)
async def revoke_auth_session(
    session_id: str,
    response: Response,
    user: CurrentUser,
    runtime: RuntimeDep,
) -> Response:
    revoked = await runtime.repository.revoke_auth_session(session_id, user.id)
    if not revoked:
        raise HTTPException(status_code=404, detail={"code": "SESSION_NOT_FOUND"})
    if session_id == user.session_id:
        _clear_refresh_cookie(response, runtime)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/machines")
async def list_machines(user: CurrentUser, runtime: RuntimeDep) -> list[dict[str, object]]:
    return await runtime.machine_access.list_machines(user.id)


@router.get("/machines/{machine_id}/telemetry")
async def machine_telemetry(machine_id: str, user: CurrentUser, runtime: RuntimeDep) -> dict[str, object]:
    await _require_machine(runtime, user, machine_id)
    context = await runtime.telemetry.get_context(machine_id)
    return context.model_dump(mode="json")


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    payload: ConversationCreate, user: CurrentUser, runtime: RuntimeDep
) -> ConversationResponse:
    await _require_machine(runtime, user, payload.machine_id)
    row = await runtime.repository.create_conversation(
        tenant_id=user.tenant_id,
        user_id=user.id,
        machine_id=payload.machine_id,
        title=payload.title,
    )
    return ConversationResponse.model_validate(row, from_attributes=True)


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(user: CurrentUser, runtime: RuntimeDep) -> list[ConversationResponse]:
    rows = await runtime.repository.list_conversations(user.tenant_id, user.id, user.role == Role.ADMIN.value)
    allowed = await runtime.machine_access.allowed_machine_ids(user.id)
    return [ConversationResponse.model_validate(row, from_attributes=True) for row in rows if row.machine_id in allowed]


@router.post("/conversations/{conversation_id}/runs", response_model=RunResponse, status_code=202)
async def create_run(
    conversation_id: str,
    payload: RunCreate,
    user: CurrentUser,
    runtime: RuntimeDep,
    x_request_id: str | None = Header(default=None),
) -> RunResponse:
    conversation = await runtime.repository.get_conversation(conversation_id, user.tenant_id)
    if not conversation:
        raise HTTPException(status_code=404, detail={"code": "CONVERSATION_NOT_FOUND"})
    if conversation.user_id != user.id and user.role != Role.ADMIN.value:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})
    await _require_machine(runtime, user, conversation.machine_id)
    run_id = str(uuid.uuid4())
    request = GraphRequest(
        request_id=x_request_id or str(uuid.uuid4()),
        run_id=run_id,
        thread_id=conversation_id,
        tenant_id=user.tenant_id,
        user_id=user.id,
        role=Role(user.role),
        machine_id=conversation.machine_id,
        query=payload.query,
    )
    row = await runtime.repository.create_run(conversation_id, request)
    await runtime.submit(run_id)
    return _run_response(row)


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(run_id: str, user: CurrentUser, runtime: RuntimeDep) -> RunResponse:
    row = await runtime.repository.get_run(run_id, user.tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND"})
    if row.user_id != user.id and user.role != Role.ADMIN.value:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})
    await _require_machine(runtime, user, row.machine_id)
    return _run_response(row)


@router.get("/runs", response_model=list[RunResponse])
async def list_runs(user: CurrentUser, runtime: RuntimeDep) -> list[RunResponse]:
    rows = await runtime.repository.list_runs(
        user.tenant_id,
        user.id,
        user.role == Role.ADMIN.value,
    )
    allowed = await runtime.machine_access.allowed_machine_ids(user.id)
    return [_run_response(row) for row in rows if row.machine_id in allowed]


@router.get("/runs/{run_id}/events")
async def run_events(
    run_id: str,
    user: CurrentUser,
    runtime: RuntimeDep,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    row = await runtime.repository.get_run(run_id, user.tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND"})
    if row.user_id != user.id and user.role != Role.ADMIN.value:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})
    await _require_machine(runtime, user, row.machine_id)

    async def stream() -> AsyncIterator[str]:
        async for event in runtime.events.subscribe(run_id, last_event_id):
            data = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
            yield f"id: {event.id}\nevent: {event.type}\ndata: {data}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/agents")
async def agents(user: CurrentUser) -> list[dict[str, object]]:
    del user
    return [
        {"id": "fault_diagnosis", "name": "故障诊断", "status": "online", "accent": "amber"},
        {"id": "process_optimization", "name": "工艺优化", "status": "online", "accent": "cyan"},
        {"id": "quality_analysis", "name": "质量分析", "status": "online", "accent": "lime"},
        {"id": "predictive_maintenance", "name": "预测性维护", "status": "online", "accent": "orange"},
    ]


@router.get("/rag/status")
async def rag_status(user: CurrentUser, runtime: RuntimeDep) -> dict[str, str]:
    del user
    return await runtime.rag.health()
