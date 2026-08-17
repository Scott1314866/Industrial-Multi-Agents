from __future__ import annotations

import asyncio
import uuid
from contextlib import AsyncExitStack
from typing import Any, Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from redis.asyncio import Redis

from industrial_agents.application import InjectionMoldingOrchestratorGraph
from industrial_agents.config import Settings
from industrial_agents.domain.models import GraphRequest, RunEvent, RunStatus
from industrial_agents.infrastructure.checkpoint import StandardRedisSaver
from industrial_agents.infrastructure.database import Database, Repository
from industrial_agents.infrastructure.events import MemoryEventBus, RedisEventBus
from industrial_agents.infrastructure.llm import OpenAICompatibleComposer
from industrial_agents.infrastructure.rag import A2ARagGateway, FakeRagGateway
from industrial_agents.infrastructure.telemetry import SimulatedTelemetryGateway


class Runtime:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.stack = AsyncExitStack()
        self.database = Database(settings.database_url)
        self.repository = Repository(self.database.sessions)
        self.telemetry = SimulatedTelemetryGateway()
        self.rag = (
            FakeRagGateway()
            if settings.rag_mode == "fake"
            else A2ARagGateway(settings.rag_a2a_url, settings.rag_timeout_seconds)
        )
        self.redis: Redis | None = None
        self.events: MemoryEventBus | RedisEventBus
        self.graph: InjectionMoldingOrchestratorGraph | None = None
        self.checkpoint_mode = "memory"
        self._tasks: set[asyncio.Task[None]] = set()

    async def start(self) -> None:
        await self.database.setup(seed_demo=self.settings.environment != "production")
        checkpointer: BaseCheckpointSaver[Any] = InMemorySaver()
        if self.settings.execution_mode == "redis":
            self.redis = Redis.from_url(self.settings.redis_url, decode_responses=False)
            await self.redis.ping()
            events = RedisEventBus(self.redis)
            await events.setup()
            self.events = events
            try:
                from langgraph.checkpoint.redis.aio import AsyncRedisSaver

                redis_checkpointer = await self.stack.enter_async_context(
                    AsyncRedisSaver.from_conn_string(self.settings.redis_url)
                )
                await redis_checkpointer.asetup()
                checkpointer = redis_checkpointer
                self.checkpoint_mode = "redis"
            except Exception:
                # Standard Redis lacks the RediSearch/RedisJSON modules used by the official saver.
                checkpointer = StandardRedisSaver(self.redis)
                self.checkpoint_mode = "redis-keyvalue"
        else:
            self.events = MemoryEventBus()
        composer = (
            OpenAICompatibleComposer(
                api_key=self.settings.llm_api_key,
                base_url=self.settings.llm_base_url,
                model=self.settings.llm_model,
            )
            if self.settings.llm_api_key
            else None
        )
        self.graph = InjectionMoldingOrchestratorGraph(self.rag, self.telemetry, checkpointer, composer=composer)

    async def close(self) -> None:
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        if self.redis:
            await self.redis.aclose()
        await self.stack.aclose()
        await self.database.close()

    async def submit(self, run_id: str) -> None:
        if self.settings.execution_mode == "redis":
            await self.events.enqueue(run_id)
            return
        task = asyncio.create_task(self.execute(run_id), name=f"ima-run-{run_id}")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def execute(self, run_id: str) -> None:
        row = await self.repository.get_run(run_id)
        if not row or not self.graph:
            return
        await self.repository.update_run(run_id, RunStatus.RUNNING)
        await self.events.publish(
            RunEvent(
                id=str(uuid.uuid4()),
                run_id=run_id,
                type="run.started",
                message="分析任务已启动",
                data={"machine_id": row.machine_id},
            )
        )
        try:
            request = GraphRequest.model_validate(row.request_payload)
            result = await self.graph.invoke(request)
            for finding in result.findings:
                await self.events.publish(
                    RunEvent(
                        id=str(uuid.uuid4()),
                        run_id=run_id,
                        type="agent.completed",
                        node=finding.agent,
                        message=finding.diagnosis,
                        data={
                            "confidence": finding.confidence,
                            "risk_level": finding.risk_level,
                            "status": finding.status,
                        },
                    )
                )
            for evidence in result.evidence:
                await self.events.publish(
                    RunEvent(
                        id=str(uuid.uuid4()),
                        run_id=run_id,
                        type="citation",
                        message=evidence.title,
                        data=evidence.model_dump(mode="json"),
                    )
                )
            await self.repository.update_run(run_id, result.status, result=result)
            event_type: Literal["run.input_required", "run.completed"] = (
                "run.input_required" if result.status == RunStatus.INPUT_REQUIRED else "run.completed"
            )
            await self.events.publish(
                RunEvent(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    type=event_type,
                    message=result.answer,
                    data=result.model_dump(mode="json"),
                )
            )
            await self.repository.audit(
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                action="run.completed",
                resource_type="run",
                resource_id=run_id,
                detail={"risk_level": result.risk_level, "confidence": result.confidence},
            )
        except Exception as exc:
            await self.repository.update_run(run_id, RunStatus.FAILED, error=type(exc).__name__)
            await self.events.publish(
                RunEvent(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    type="run.failed",
                    message="分析任务执行失败，请稍后重试或联系平台管理员。",
                    data={"error_code": "GRAPH_EXECUTION_FAILED"},
                )
            )
