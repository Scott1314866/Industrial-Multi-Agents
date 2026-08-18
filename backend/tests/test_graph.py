from __future__ import annotations

import uuid

import pytest

from industrial_agents.application import InjectionMoldingOrchestratorGraph
from industrial_agents.domain.models import GraphRequest, RagQuery, RagResult, RiskLevel, Role, RunStatus
from industrial_agents.infrastructure.rag import FakeRagGateway
from industrial_agents.infrastructure.telemetry import SimulatedTelemetryGateway


class NoEvidenceRagGateway:
    async def retrieve(self, query: RagQuery) -> RagResult:
        del query
        return RagResult(status="no_evidence")

    async def health(self) -> dict[str, str]:
        return {"status": "available", "mode": "test"}


class CountingComposer:
    def __init__(self) -> None:
        self.calls = 0

    async def compose(self, payload: dict[str, object]) -> str:
        del payload
        self.calls += 1
        return "不应公开的模型建议"


class PartialEvidenceRagGateway:
    def __init__(self) -> None:
        self.fake = FakeRagGateway()

    async def retrieve(self, query: RagQuery) -> RagResult:
        if query.knowledge_domain == "diagnosis":
            return await self.fake.retrieve(query)
        return RagResult(status="no_evidence")

    async def health(self) -> dict[str, str]:
        return {"status": "available", "mode": "test"}


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


@pytest.mark.asyncio
async def test_safety_guard_denies_unsubstantiated_findings_and_skips_composer() -> None:
    composer = CountingComposer()
    graph = InjectionMoldingOrchestratorGraph(
        NoEvidenceRagGateway(), SimulatedTelemetryGateway(), composer=composer
    )
    result = await graph.invoke(
        GraphRequest(
            request_id="request-deny",
            run_id="run-deny",
            thread_id="thread-deny",
            tenant_id="tenant",
            user_id="user",
            role=Role.ENGINEER,
            machine_id="IMM-320B",
            query="请诊断 H-08 液压故障并给出维护建议",
        )
    )
    assert result.safety_decision == "deny"
    assert result.risk_level is RiskLevel.HIGH
    assert result.confidence <= 0.49
    assert composer.calls == 0
    assert "冷却回路" not in result.answer
    assert "冷却回路" not in "".join(item.diagnosis for item in result.findings)
    assert all(item.evidence == [] for item in result.findings)
    assert all(item.diagnosis == "证据不足，无法形成可执行的诊断结论。" for item in result.findings)


@pytest.mark.asyncio
async def test_high_risk_evidence_is_restricted_and_skips_composer() -> None:
    composer = CountingComposer()
    graph = InjectionMoldingOrchestratorGraph(
        FakeRagGateway(), SimulatedTelemetryGateway(), composer=composer
    )
    result = await graph.invoke(
        GraphRequest(
            request_id="request-restricted",
            run_id="run-restricted",
            thread_id="thread-restricted",
            tenant_id="tenant",
            user_id="user",
            role=Role.ENGINEER,
            machine_id="IMM-320B",
            query="请诊断 H-08 液压故障",
        )
    )
    assert result.safety_decision == "restricted"
    assert composer.calls == 0
    assert result.findings
    assert all("不自行修改" in item.recommendations[0].detail for item in result.findings)


@pytest.mark.asyncio
async def test_safety_guard_error_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = InjectionMoldingOrchestratorGraph(FakeRagGateway(), SimulatedTelemetryGateway())

    def fail_guard(state: object) -> object:
        del state
        raise RuntimeError("policy unavailable")

    monkeypatch.setattr(graph, "_evaluate_safety", fail_guard)
    result = await graph.invoke(
        GraphRequest(
            request_id="request-error",
            run_id="run-error",
            thread_id="thread-error",
            tenant_id="tenant",
            user_id="user",
            role=Role.ENGINEER,
            machine_id="IMM-240A",
            query="请分析当前设备故障",
        )
    )
    assert result.safety_decision == "deny"
    assert result.safety_reason_codes == ["SAFETY_GUARD_ERROR"]


@pytest.mark.asyncio
async def test_partial_branch_evidence_denies_combined_response() -> None:
    graph = InjectionMoldingOrchestratorGraph(PartialEvidenceRagGateway(), SimulatedTelemetryGateway())
    result = await graph.invoke(
        GraphRequest(
            request_id="request-partial",
            run_id="run-partial",
            thread_id="thread-partial",
            tenant_id="tenant",
            user_id="user",
            role=Role.ENGINEER,
            machine_id="IMM-320B",
            query="请诊断 H-08 液压故障并制定维护清单",
        )
    )
    assert result.safety_decision == "deny"
    assert {item.agent for item in result.findings} == {"fault_diagnosis", "predictive_maintenance"}
    assert result.evidence == []
    assert all(item.evidence == [] for item in result.findings)
