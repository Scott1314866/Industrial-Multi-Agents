from __future__ import annotations

import asyncio

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from industrial_agents.config import Settings
from industrial_agents.web.app import create_app


@pytest.mark.asyncio
async def test_authenticated_diagnosis_flow(tmp_path) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'api.db'}",
        execution_mode="inline",
        rag_mode="fake",
        jwt_secret="test-secret-with-at-least-thirty-two-characters",
    )
    app = create_app(settings)
    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            login = await client.post(
                "/api/v1/auth/login",
                json={"email": "engineer@moldwise.local", "password": "Engineer123!"},
            )
            assert login.status_code == 200
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            me = await client.get("/api/v1/auth/me", headers=headers)
            assert me.json()["role"] == "engineer"
            conversation = await client.post(
                "/api/v1/conversations",
                headers=headers,
                json={"machine_id": "IMM-320B", "title": "液压趋势诊断"},
            )
            run = await client.post(
                f"/api/v1/conversations/{conversation.json()['id']}/runs",
                headers=headers,
                json={"query": "H-08 报警且油温升高，请分析液压故障"},
            )
            assert run.status_code == 202
            for _ in range(50):
                response = await client.get(f"/api/v1/runs/{run.json()['id']}", headers=headers)
                if response.json()["status"] in {"completed", "failed"}:
                    break
                await asyncio.sleep(0.03)
            assert response.json()["status"] == "completed"
            assert response.json()["result"]["evidence"]
            ledger = await client.get("/api/v1/runs", headers=headers)
            assert ledger.status_code == 200
            assert ledger.json()[0]["id"] == run.json()["id"]


@pytest.mark.asyncio
async def test_refresh_rotation_reuse_detection_and_session_revocation(tmp_path) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'sessions.db'}",
        execution_mode="inline",
        rag_mode="fake",
        jwt_secret="test-secret-with-at-least-thirty-two-characters",
    )
    app = create_app(settings)
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            login = await client.post(
                "/api/v1/auth/login",
                json={"email": "engineer@moldwise.local", "password": "Engineer123!"},
            )
            old_refresh = login.cookies.get("ima_refresh")
            assert old_refresh

            sessions = await client.get(
                "/api/v1/auth/sessions",
                headers={"Authorization": f"Bearer {login.json()['access_token']}"},
            )
            assert sessions.status_code == 200
            assert sessions.json()[0]["current"] is True

            refreshed = await client.post("/api/v1/auth/refresh")
            assert refreshed.status_code == 200
            assert refreshed.cookies.get("ima_refresh") != old_refresh
            refreshed_access = refreshed.json()["access_token"]

            async with AsyncClient(transport=transport, base_url="http://test") as replay_client:
                replay_client.cookies.set("ima_refresh", old_refresh, path="/api/v1/auth")
                replay = await replay_client.post("/api/v1/auth/refresh")
            assert replay.status_code == 401
            assert replay.json()["detail"]["code"] == "REFRESH_TOKEN_REUSED"

            revoked = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {refreshed_access}"},
            )
            assert revoked.status_code == 401
            assert revoked.json()["detail"]["code"] == "SESSION_REVOKED"


@pytest.mark.asyncio
async def test_logout_and_explicit_session_revocation_invalidate_access(tmp_path) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'logout.db'}",
        execution_mode="inline",
        rag_mode="fake",
        jwt_secret="test-secret-with-at-least-thirty-two-characters",
    )
    app = create_app(settings)
    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            login = await client.post(
                "/api/v1/auth/login",
                json={"email": "engineer@moldwise.local", "password": "Engineer123!"},
            )
            access = login.json()["access_token"]
            headers = {"Authorization": f"Bearer {access}"}
            sessions = (await client.get("/api/v1/auth/sessions", headers=headers)).json()
            session_id = sessions[0]["id"]
            response = await client.delete(f"/api/v1/auth/sessions/{session_id}", headers=headers)
            assert response.status_code == 204
            assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 401

            second_login = await client.post(
                "/api/v1/auth/login",
                json={"email": "engineer@moldwise.local", "password": "Engineer123!"},
            )
            second_headers = {"Authorization": f"Bearer {second_login.json()['access_token']}"}
            assert (await client.post("/api/v1/auth/logout")).status_code == 204
            assert (await client.get("/api/v1/auth/me", headers=second_headers)).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("customer@moldwise.local", "Customer123!"),
        ("admin@moldwise.local", "Admin123!"),
    ],
)
async def test_machine_grants_apply_to_customers_and_admins(tmp_path, email: str, password: str) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / email.split('@')[0]}.db",
        execution_mode="inline",
        rag_mode="fake",
        jwt_secret="test-secret-with-at-least-thirty-two-characters",
    )
    app = create_app(settings)
    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            user = await app.state.runtime.repository.get_user_by_email(email)
            assert user
            assert await app.state.runtime.repository.revoke_machine(user.id, "IMM-320B")

            machines = await client.get("/api/v1/machines", headers=headers)
            assert "IMM-320B" not in {item["id"] for item in machines.json()}
            assert (await client.get("/api/v1/machines/IMM-320B/telemetry", headers=headers)).status_code == 404
            conversation = await client.post(
                "/api/v1/conversations",
                headers=headers,
                json={"machine_id": "IMM-320B", "title": "unauthorized"},
            )
            assert conversation.status_code == 404
