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
