from __future__ import annotations

import uuid

import pytest

from industrial_agents.application import InjectionMoldingOrchestratorGraph
from industrial_agents.domain.models import GraphRequest, RiskLevel, Role, RunStatus
from industrial_agents.infrastructure.rag import FakeRagGateway
from industrial_agents.infrastructure.telemetry import SimulatedTelemetryGateway


@pytest.mark.asyncio
async def test_graph_routes_fault_and_maintenance_in_parallel() -> None:
    graph = InjectionMoldingOrchestratorGraph(FakeRagGateway(), SimulatedTelemetryGateway())
    result = await graph.invoke(
        GraphRequest(
            request_id=str(uuid.uuid4()),
            run_id=str(uuid.uuid4()),
            thread_id=str(uuid.uuid4()),
            tenant_id="tenant-test",
            user_id="engineer-test",
            role=Role.ENGINEER,
            machine_id="IMM-320B",
            query="H-08 报警，油温持续升高，请诊断并制定维护检查清单",
        )
    )
    assert result.status is RunStatus.COMPLETED
    assert {item.agent for item in result.findings} == {"fault_diagnosis", "predictive_maintenance"}
    assert result.evidence
    assert result.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
    assert "不会写入 PLC" in "".join(result.warnings)


@pytest.mark.asyncio
async def test_graph_requests_more_specific_input() -> None:
    graph = InjectionMoldingOrchestratorGraph(FakeRagGateway(), SimulatedTelemetryGateway())
    result = await graph.invoke(
        GraphRequest(
            request_id="request",
            run_id="run",
            thread_id="thread",
            tenant_id="tenant",
            user_id="user",
            role=Role.CUSTOMER,
            machine_id="IMM-240A",
            query="有问题",
        )
    )
    assert result.status is RunStatus.INPUT_REQUIRED
    assert "补充" in result.answer
