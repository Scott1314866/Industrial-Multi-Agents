from __future__ import annotations

import operator
import re
from typing import Annotated, Any, Literal, TypedDict, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from industrial_agents.domain.models import (
    AgentFinding,
    AgentStatus,
    Evidence,
    GraphRequest,
    GraphResponse,
    MachineContext,
    RagQuery,
    Recommendation,
    RiskLevel,
    RunStatus,
)
from industrial_agents.domain.ports import AnswerComposer, RagGateway, TelemetryGateway

AgentName = Literal["fault_diagnosis", "process_optimization", "quality_analysis", "predictive_maintenance"]


class GraphState(TypedDict, total=False):
    request_id: str
    run_id: str
    thread_id: str
    tenant_id: str
    user_id: str
    role: str
    machine_id: str
    query: str
    intents: list[AgentName]
    entities: dict[str, Any]
    machine_context: dict[str, Any]
    findings: Annotated[list[dict[str, Any]], operator.add]
    evidence: list[dict[str, Any]]
    warnings: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]
    risk_level: str
    confidence: float
    answer: str
    status: str


INTENT_TERMS: dict[AgentName, tuple[str, ...]] = {
    "fault_diagnosis": (
        "故障",
        "报警",
        "异常",
        "停机",
        "液压",
        "电气",
        "伺服",
        "通信",
        "异响",
        "漏油",
    ),
    "process_optimization": (
        "参数",
        "工艺",
        "压力",
        "温度",
        "速度",
        "周期",
        "保压",
        "优化",
    ),
    "quality_analysis": (
        "飞边",
        "缩水",
        "银纹",
        "橘皮",
        "缺陷",
        "产品",
        "尺寸",
        "质量",
        "外观",
    ),
    "predictive_maintenance": (
        "维护",
        "保养",
        "寿命",
        "模次",
        "检修",
        "预防",
        "趋势",
    ),
}


def _risk_rank(value: RiskLevel | str) -> int:
    return {"low": 0, "medium": 1, "high": 2, "critical": 3}[str(value)]


class InjectionMoldingOrchestratorGraph:
    """Deep module hiding routing, fan-out, evidence aggregation and safety behavior."""

    def __init__(
        self,
        rag: RagGateway,
        telemetry: TelemetryGateway,
        checkpointer: BaseCheckpointSaver[Any] | None = None,
        composer: AnswerComposer | None = None,
    ) -> None:
        self.rag = rag
        self.telemetry = telemetry
        self.composer = composer
        self.graph = self._build().compile(checkpointer=checkpointer)

    def _build(self) -> StateGraph[GraphState]:
        builder = StateGraph(GraphState)
        builder.add_node("prepare", self._prepare)
        builder.add_node("load_machine_context", self._load_machine_context)
        builder.add_node("fault_diagnosis", self._fault_diagnosis)
        builder.add_node("process_optimization", self._process_optimization)
        builder.add_node("quality_analysis", self._quality_analysis)
        builder.add_node("predictive_maintenance", self._predictive_maintenance)
        builder.add_node("aggregate", self._aggregate)
        builder.add_node("safety_guard", self._safety_guard)
        builder.add_node("finalize", self._finalize)
        builder.add_node("input_required", self._input_required)

        builder.add_edge(START, "prepare")
        builder.add_conditional_edges(
            "prepare",
            self._after_prepare,
            {"context": "load_machine_context", "input_required": "input_required"},
        )
        builder.add_conditional_edges(
            "load_machine_context",
            self._dispatch,
            [
                "fault_diagnosis",
                "process_optimization",
                "quality_analysis",
                "predictive_maintenance",
            ],
        )
        for node in INTENT_TERMS:
            builder.add_edge(node, "aggregate")
        builder.add_edge("aggregate", "safety_guard")
        builder.add_edge("safety_guard", "finalize")
        builder.add_edge("finalize", END)
        builder.add_edge("input_required", END)
        return builder

    async def invoke(self, request: GraphRequest) -> GraphResponse:
        initial = cast(
            GraphState,
            {
                **request.model_dump(mode="json"),
                "findings": [],
                "warnings": [],
                "errors": [],
            },
        )
        state = await self.graph.ainvoke(
            initial,
            config={"configurable": {"thread_id": request.thread_id}},
        )
        findings = [AgentFinding.model_validate(item) for item in state.get("findings", [])]
        evidence = [Evidence.model_validate(item) for item in state.get("evidence", [])]
        return GraphResponse(
            run_id=request.run_id,
            status=RunStatus(state.get("status", "completed")),
            answer=state.get("answer", "暂时无法形成结论。"),
            risk_level=RiskLevel(state.get("risk_level", "medium")),
            confidence=float(state.get("confidence", 0)),
            findings=findings,
            evidence=evidence,
            warnings=state.get("warnings", []),
        )

    async def _prepare(self, state: GraphState) -> GraphState:
        query = re.sub(r"\s+", " ", state["query"]).strip()
        intents = [name for name, terms in INTENT_TERMS.items() if any(term in query for term in terms)]
        if not intents and len(query) >= 8:
            intents = ["fault_diagnosis"]
        alarm_codes = re.findall(r"\b[A-Z][-_]?\d{2,4}\b", query.upper())
        return {
            "query": query,
            "intents": intents,
            "entities": {"alarm_codes": alarm_codes},
            "status": "running",
        }

    @staticmethod
    def _after_prepare(state: GraphState) -> str:
        if not state.get("intents") or len(state["query"]) < 4:
            return "input_required"
        return "context"

    async def _load_machine_context(self, state: GraphState) -> GraphState:
        context = await self.telemetry.get_context(state["machine_id"])
        return {"machine_context": context.model_dump(mode="json")}

    @staticmethod
    def _dispatch(state: GraphState) -> list[Send]:
        shared = dict(state)
        return [Send(intent, shared) for intent in state["intents"]]

    async def _retrieve(self, state: GraphState, domain: str):
        context = MachineContext.model_validate(state["machine_context"])
        return await self.rag.retrieve(
            RagQuery(
                query=state["query"],
                knowledge_domain=domain,  # type: ignore[arg-type]
                machine_model=context.model,
                alarm_codes=list({*context.alarm_codes, *state["entities"].get("alarm_codes", [])}),
                tenant_id=state["tenant_id"],
                permission_labels=[state["role"], "industrial_manual"],
                request_id=state["request_id"],
                run_id=state["run_id"],
            )
        )

    async def _fault_diagnosis(self, state: GraphState) -> GraphState:
        context = MachineContext.model_validate(state["machine_context"])
        rag = await self._retrieve(state, "diagnosis")
        latest = context.telemetry[-1]
        if latest.oil_temperature_c >= 55 or latest.injection_pressure_mpa < 10:
            diagnosis = "液压油温持续升高并伴随压力衰减，优先怀疑冷却回路、滤芯压差或液压泵效率下降。"
            risk = RiskLevel.HIGH
        elif latest.servo_load_pct >= 90:
            diagnosis = "伺服负载已进入高风险区，可能存在机械卡阻、联轴器或编码器反馈异常。"
            risk = RiskLevel.CRITICAL
        else:
            diagnosis = "当前主要参数未出现持续越限；建议结合报警历史检查瞬态信号和外围通信。"
            risk = RiskLevel.MEDIUM
        finding = AgentFinding(
            agent="fault_diagnosis",
            status=AgentStatus.COMPLETED if rag.evidence else AgentStatus.DEGRADED,
            confidence=min(0.95, 0.58 + rag.confidence * 0.38),
            risk_level=risk,
            diagnosis=diagnosis,
            recommendations=[
                Recommendation(
                    title="执行无损检查",
                    detail="核对报警时间线，检查油位/滤芯/冷却回路或伺服机械连接，禁止带故障强制复位。",
                    verification="记录停机前后 30 分钟趋势，并由设备工程师复核检查结果。",
                )
            ],
            evidence=rag.evidence,
            errors=[] if rag.status == "success" else ["知识库证据不可用"],
        )
        return {"findings": [finding.model_dump(mode="json")], "warnings": rag.warnings}

    async def _process_optimization(self, state: GraphState) -> GraphState:
        context = MachineContext.model_validate(state["machine_context"])
        rag = await self._retrieve(state, "process")
        latest = context.telemetry[-1]
        risk = RiskLevel.HIGH if context.status != "running" else RiskLevel.MEDIUM
        finding = AgentFinding(
            agent="process_optimization",
            status=AgentStatus.COMPLETED if rag.evidence else AgentStatus.DEGRADED,
            confidence=0.82 if rag.evidence else 0.52,
            risk_level=risk,
            diagnosis=(
                f"当前周期 {latest.cycle_time_s:.1f}s、注射压力 {latest.injection_pressure_mpa:.1f}MPa。"
                "应先稳定设备状态，再采用单变量、小步幅方式验证工艺窗口。"
            ),
            recommendations=[
                Recommendation(
                    title="建立受控工艺试验",
                    detail="保持其他参数不变，每次只调整一个变量，使用小批次首件确认；系统不下发 PLC 参数。",
                    verification="连续记录至少 20 模的周期、重量、外观和尺寸趋势。",
                )
            ],
            evidence=rag.evidence,
            errors=[] if rag.evidence else ["缺少正式工艺窗口证据"],
        )
        return {"findings": [finding.model_dump(mode="json")], "warnings": rag.warnings}

    async def _quality_analysis(self, state: GraphState) -> GraphState:
        context = MachineContext.model_validate(state["machine_context"])
        rag = await self._retrieve(state, "quality")
        score = context.telemetry[-1].quality_score
        finding = AgentFinding(
            agent="quality_analysis",
            status=AgentStatus.COMPLETED if rag.evidence else AgentStatus.DEGRADED,
            confidence=0.86 if rag.evidence else 0.55,
            risk_level=RiskLevel.HIGH if score < 92 else RiskLevel.MEDIUM,
            diagnosis=f"批次质量评分为 {score:.1f}，需从模具、材料与工艺三条路径进行交叉排查。",
            recommendations=[
                Recommendation(
                    title="锁定缺陷样本",
                    detail="隔离异常批次并保留首末件，先检查分型面和材料状态，再核对压力与末段速度趋势。",
                    verification="以尺寸、重量和外观三项结果确认根因，不以单一参数变化直接下结论。",
                )
            ],
            evidence=rag.evidence,
            errors=[] if rag.evidence else ["缺少质量标准引用"],
        )
        return {"findings": [finding.model_dump(mode="json")], "warnings": rag.warnings}

    async def _predictive_maintenance(self, state: GraphState) -> GraphState:
        context = MachineContext.model_validate(state["machine_context"])
        rag = await self._retrieve(state, "maintenance")
        risk = RiskLevel.HIGH if context.mold_cycles >= 180_000 else RiskLevel.LOW
        finding = AgentFinding(
            agent="predictive_maintenance",
            status=AgentStatus.COMPLETED if rag.evidence else AgentStatus.DEGRADED,
            confidence=0.84 if rag.evidence else 0.5,
            risk_level=risk,
            diagnosis=f"设备累计 {context.mold_cycles:,} 模次，已进入关键部件周期复核窗口。",
            recommendations=[
                Recommendation(
                    title="安排计划维护",
                    detail="检查液压油、滤芯、导轨润滑、拉杆受力、关键紧固件和伺服连接状态。",
                    verification="维护后执行空载、低速和首件三个阶段验收并归档趋势。",
                )
            ],
            evidence=rag.evidence,
            errors=[] if rag.evidence else ["维护标准证据不可用"],
        )
        return {"findings": [finding.model_dump(mode="json")], "warnings": rag.warnings}

    async def _aggregate(self, state: GraphState) -> GraphState:
        findings = [AgentFinding.model_validate(item) for item in state.get("findings", [])]
        evidence: dict[str, Evidence] = {}
        for finding in findings:
            for item in finding.evidence:
                evidence[item.document_id] = item
        confidence = sum(item.confidence for item in findings) / len(findings) if findings else 0
        risk = max((item.risk_level for item in findings), key=_risk_rank, default=RiskLevel.MEDIUM)
        return {
            "evidence": [item.model_dump(mode="json") for item in evidence.values()],
            "confidence": round(confidence, 3),
            "risk_level": str(risk),
        }

    async def _safety_guard(self, state: GraphState) -> GraphState:
        evidence = state.get("evidence", [])
        warnings: list[str] = ["所有参数建议均需现场工程师确认，系统不会写入 PLC。"]
        if not evidence:
            warnings.append("未获得有效知识库证据，已隐藏具体参数调整建议并建议转人工。")
            return {"risk_level": "high", "confidence": min(state.get("confidence", 0), 0.49), "warnings": warnings}
        if state.get("risk_level") in {"high", "critical"}:
            warnings.append("当前风险较高：请先停机或隔离异常，完成无损检查后再恢复生产。")
        return {"warnings": warnings}

    async def _finalize(self, state: GraphState) -> GraphState:
        findings = [AgentFinding.model_validate(item) for item in state.get("findings", [])]
        role = state["role"]
        sections = []
        for finding in findings:
            recommendations = "；".join(item.detail for item in finding.recommendations)
            sections.append(f"【{finding.agent}】{finding.diagnosis}\n建议：{recommendations}")
        answer = "\n\n".join(sections)
        if self.composer and findings:
            try:
                answer = await self.composer.compose(
                    {
                        "role": role,
                        "query": state["query"],
                        "risk_level": state.get("risk_level", "medium"),
                        "findings": [item.model_dump(mode="json") for item in findings],
                        "evidence": state.get("evidence", []),
                    }
                )
            except Exception:
                # Model availability must never erase deterministic, evidence-backed output.
                pass
        if role == "customer" and state.get("risk_level") in {"high", "critical"}:
            answer += "\n\n客户提示：请停止自行调参并联系授权售后工程师处理。"
        return {"answer": answer, "status": "completed"}

    async def _input_required(self, state: GraphState) -> GraphState:
        return {
            "status": "input_required",
            "risk_level": "low",
            "confidence": 0,
            "answer": "请补充具体故障现象、报警代码、产品缺陷或希望分析的工艺参数。",
        }
