from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from industrial_agents.domain.models import Evidence, RagQuery, RagResult

KNOWLEDGE: dict[str, list[dict[str, str]]] = {
    "diagnosis": [
        {
            "id": "manual-hydraulic-08",
            "title": "MX 系列液压系统维护手册",
            "section": "4.2 压力波动与油温升高",
            "snippet": "油温持续超过 55℃ 且系统压力下降时，应检查油位、滤芯压差、冷却回路和液压泵效率。",
        },
        {
            "id": "manual-servo-03",
            "title": "伺服驱动故障排查指南",
            "section": "3.1 负载异常",
            "snippet": "伺服负载持续高于 90% 时，先停机确认机械卡阻、联轴器松动和编码器反馈，禁止反复复位强行运行。",
        },
    ],
    "process": [
        {
            "id": "process-window-01",
            "title": "通用注塑工艺窗口规范",
            "section": "2.4 参数调整原则",
            "snippet": "参数优化应采用单变量、小步幅和批次验证原则；压力、速度与保压时间不得同时大幅调整。",
        }
    ],
    "quality": [
        {
            "id": "quality-flash-02",
            "title": "注塑件缺陷分析图谱",
            "section": "飞边与尺寸波动",
            "snippet": "飞边应依次核查锁模力、模具分型面、料温、注射压力和末段速度，并保留首件对比记录。",
        }
    ],
    "maintenance": [
        {
            "id": "maintenance-cycles-01",
            "title": "注塑机预防性维护标准",
            "section": "按模次维护",
            "snippet": "超过 18 万模次的设备应复核液压油、滤芯、导轨润滑、拉杆受力和关键紧固件状态。",
        }
    ],
}


class FakeRagGateway:
    async def retrieve(self, query: RagQuery) -> RagResult:
        await asyncio.sleep(0.04)
        rows = KNOWLEDGE.get(query.knowledge_domain, [])[: query.top_k]
        evidence = [
            Evidence(
                document_id=row["id"],
                title=row["title"],
                section=row["section"],
                snippet=row["snippet"],
                score=max(0.72, 0.94 - index * 0.07),
                version="2026.1",
                source_url=f"rag://{row['id']}",
            )
            for index, row in enumerate(rows)
        ]
        return RagResult(
            status="success" if evidence else "no_evidence",
            evidence=evidence,
            confidence=0.88 if evidence else 0,
            warnings=["当前使用 Fake RAG；生产结论需以正式知识库为准。"],
        )

    async def health(self) -> dict[str, str]:
        return {"status": "available", "mode": "fake"}


class A2ARagGateway:
    """All python-a2a protocol knowledge is localized in this adapter."""

    def __init__(self, url: str, timeout_seconds: float = 8.0) -> None:
        self.url = url
        self.timeout_seconds = timeout_seconds
        self._failures = 0
        self._opened_at = 0.0

    @retry(
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.2, min=0.2, max=1),
        reraise=True,
    )
    async def retrieve(self, query: RagQuery) -> RagResult:
        if self._failures >= 3 and time.monotonic() - self._opened_at < 30:
            return RagResult(status="failed", warnings=["RAG circuit breaker is open"])
        try:
            result = await asyncio.wait_for(self._send(query), timeout=self.timeout_seconds)
            self._failures = 0
            return result
        except Exception as exc:
            self._failures += 1
            self._opened_at = time.monotonic()
            if isinstance(exc, TimeoutError | ConnectionError):
                raise
            return RagResult(status="failed", warnings=[f"RAG response rejected: {type(exc).__name__}"])

    async def _send(self, query: RagQuery) -> RagResult:
        from python_a2a import A2AClient, Message, MessageRole, Task, TextContent

        client = A2AClient(self.url)
        payload = json.dumps(query.model_dump(), ensure_ascii=False)
        message = Message(content=TextContent(text=payload), role=MessageRole.USER)
        task = Task(id=f"rag-{uuid.uuid4()}", message=message.to_dict())
        response = await client.send_task_async(task)
        state = str(response.status.state).lower()
        if "completed" not in state:
            return RagResult(status="failed", warnings=[f"A2A task ended as {state}"])
        raw: Any = response.artifacts[0]["parts"][0]["text"]
        data = json.loads(raw) if isinstance(raw, str) else raw
        return RagResult.model_validate(data)

    async def health(self) -> dict[str, str]:
        try:
            from python_a2a import A2AClient

            client = await asyncio.wait_for(asyncio.to_thread(A2AClient, self.url), timeout=2)
            card = client.agent_card
            return {"status": "available", "mode": "a2a", "agent": getattr(card, "name", "rag")}
        except Exception:
            return {"status": "unavailable", "mode": "a2a"}
