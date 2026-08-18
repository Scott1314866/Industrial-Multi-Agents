from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from .models import MachineContext, RagQuery, RagResult, RunEvent


class RagGateway(Protocol):
    async def retrieve(self, query: RagQuery) -> RagResult: ...

    async def health(self) -> dict[str, str]: ...


class TelemetryGateway(Protocol):
    async def get_context(self, machine_id: str) -> MachineContext: ...

    def list_machines(self) -> list[dict[str, object]]: ...


class AnswerComposer(Protocol):
    async def compose(self, payload: dict[str, object]) -> str: ...


class EventBus(Protocol):
    async def publish(self, event: RunEvent) -> None: ...

    def subscribe(self, run_id: str, after_id: str | None = None) -> AsyncIterator[RunEvent]: ...

    async def enqueue(self, run_id: str) -> None: ...

    def consume_runs(self, consumer: str) -> AsyncIterator[str]: ...
