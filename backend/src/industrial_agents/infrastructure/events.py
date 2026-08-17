from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator

from redis.asyncio import Redis

from industrial_agents.domain.models import RunEvent


class MemoryEventBus:
    def __init__(self) -> None:
        self._history: dict[str, list[RunEvent]] = defaultdict(list)
        self._queues: dict[str, list[asyncio.Queue[RunEvent]]] = defaultdict(list)
        self._runs: asyncio.Queue[str] = asyncio.Queue()

    async def publish(self, event: RunEvent) -> None:
        self._history[event.run_id].append(event)
        for queue in self._queues[event.run_id]:
            await queue.put(event)

    async def subscribe(self, run_id: str, after_id: str | None = None) -> AsyncIterator[RunEvent]:
        start = 0
        if after_id:
            start = next((i + 1 for i, event in enumerate(self._history[run_id]) if event.id == after_id), 0)
        for event in self._history[run_id][start:]:
            yield event
            if event.type in {"run.completed", "run.failed", "run.input_required"}:
                return
        queue: asyncio.Queue[RunEvent] = asyncio.Queue()
        self._queues[run_id].append(queue)
        try:
            while True:
                event = await queue.get()
                yield event
                if event.type in {"run.completed", "run.failed", "run.input_required"}:
                    return
        finally:
            self._queues[run_id].remove(queue)

    async def enqueue(self, run_id: str) -> None:
        await self._runs.put(run_id)

    async def consume_runs(self, consumer: str) -> AsyncIterator[str]:
        del consumer
        while True:
            yield await self._runs.get()


class RedisEventBus:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def setup(self) -> None:
        try:
            await self.redis.xgroup_create("ima:runs", "ima-workers", id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def publish(self, event: RunEvent) -> None:
        await self.redis.xadd(
            f"ima:events:{event.run_id}",
            {"payload": event.model_dump_json()},
            maxlen=1000,
            approximate=True,
        )

    async def subscribe(self, run_id: str, after_id: str | None = None) -> AsyncIterator[RunEvent]:
        cursor = after_id or "0-0"
        key = f"ima:events:{run_id}"
        while True:
            entries = await self.redis.xread({key: cursor}, block=15_000, count=50)
            if not entries:
                continue
            for _, rows in entries:
                for entry_id, fields in rows:
                    cursor = entry_id.decode() if isinstance(entry_id, bytes) else str(entry_id)
                    payload = fields.get(b"payload") or fields.get("payload")
                    event = RunEvent.model_validate_json(payload)
                    event.id = cursor
                    yield event
                    if event.type in {"run.completed", "run.failed", "run.input_required"}:
                        return

    async def enqueue(self, run_id: str) -> None:
        await self.redis.xadd("ima:runs", {"run_id": run_id})

    async def consume_runs(self, consumer: str) -> AsyncIterator[str]:
        while True:
            entries = await self.redis.xreadgroup("ima-workers", consumer, {"ima:runs": ">"}, count=1, block=10_000)
            for _, rows in entries:
                for entry_id, fields in rows:
                    raw = fields.get(b"run_id") or fields.get("run_id")
                    run_id = raw.decode() if isinstance(raw, bytes) else str(raw)
                    yield run_id
                    await self.redis.xack("ima:runs", "ima-workers", entry_id)
