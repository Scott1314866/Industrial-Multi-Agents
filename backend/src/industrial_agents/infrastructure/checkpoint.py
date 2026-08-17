from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator, Awaitable, Sequence
from typing import Any, cast
from urllib.parse import quote

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
    get_checkpoint_metadata,
)
from redis.asyncio import Redis


class StandardRedisSaver(BaseCheckpointSaver[str]):
    """LangGraph saver for standard Redis installations without Redis Stack modules.

    The official Redis saver remains the preferred adapter. This implementation is the
    compatibility path for factories that only expose core Redis commands.
    """

    def __init__(self, redis: Redis, *, prefix: str = "ima:langgraph") -> None:
        super().__init__()
        self.redis = redis
        self.prefix = prefix

    def _encode(self, value: Any) -> str:
        type_name, payload = self.serde.dumps_typed(value)
        return json.dumps(
            {"type": type_name, "data": base64.b64encode(payload).decode("ascii")},
            separators=(",", ":"),
        )

    def _decode(self, value: str | bytes) -> Any:
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        envelope = json.loads(value)
        return self.serde.loads_typed(
            (envelope["type"], base64.b64decode(envelope["data"]))
        )

    def _namespace_key(self, thread_id: str, checkpoint_ns: str) -> str:
        return f"{self.prefix}:checkpoint:{quote(thread_id, safe='')}:{quote(checkpoint_ns, safe='')}"

    def _writes_key(self, thread_id: str, checkpoint_ns: str, checkpoint_id: str) -> str:
        return (
            f"{self.prefix}:writes:{quote(thread_id, safe='')}:"
            f"{quote(checkpoint_ns, safe='')}:{quote(checkpoint_id, safe='')}"
        )

    async def _hkeys(self, key: str) -> list[Any]:
        return await cast(Awaitable[list[Any]], self.redis.hkeys(key))

    async def _hget(self, key: str, field: str) -> Any:
        return await cast(Awaitable[Any], self.redis.hget(key, field))

    async def _hvals(self, key: str) -> list[Any]:
        return await cast(Awaitable[list[Any]], self.redis.hvals(key))

    async def _smembers(self, key: str) -> set[Any]:
        return await cast(Awaitable[set[Any]], self.redis.smembers(key))

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        configurable = config["configurable"]
        thread_id = str(configurable["thread_id"])
        checkpoint_ns = str(configurable.get("checkpoint_ns", ""))
        key = self._namespace_key(thread_id, checkpoint_ns)
        checkpoint_id = get_checkpoint_id(config)
        if checkpoint_id is None:
            raw_ids = await self._hkeys(key)
            if not raw_ids:
                return None
            checkpoint_id = max(
                item.decode() if isinstance(item, bytes) else str(item) for item in raw_ids
            )
        raw = await self._hget(key, checkpoint_id)
        if raw is None:
            return None
        record = json.loads(raw)
        checkpoint = self._decode(record["checkpoint"])
        metadata = self._decode(record["metadata"])
        parent_id = record.get("parent_id")
        writes = await self._hvals(
            self._writes_key(thread_id, checkpoint_ns, checkpoint_id)
        )
        pending_writes = []
        for write in writes:
            entry = json.loads(write)
            pending_writes.append(
                (entry["task_id"], entry["channel"], self._decode(entry["value"]))
            )
        result_config: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }
        parent_config: RunnableConfig | None = None
        if parent_id:
            parent_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": parent_id,
                }
            }
        return CheckpointTuple(
            config=result_config,
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=parent_config,
            pending_writes=pending_writes,
        )

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        if config is None:
            raw_threads = await self._smembers(f"{self.prefix}:threads")
            thread_ids = [item.decode() if isinstance(item, bytes) else str(item) for item in raw_threads]
        else:
            thread_ids = [str(config["configurable"]["thread_id"])]
        yielded = 0
        before_id = get_checkpoint_id(before) if before else None
        requested_id = get_checkpoint_id(config) if config else None
        requested_ns = config["configurable"].get("checkpoint_ns") if config else None
        for thread_id in thread_ids:
            raw_namespaces = await self._smembers(
                f"{self.prefix}:namespaces:{quote(thread_id, safe='')}"
            )
            namespaces = [
                item.decode() if isinstance(item, bytes) else str(item)
                for item in raw_namespaces
            ]
            for checkpoint_ns in namespaces:
                if requested_ns is not None and checkpoint_ns != requested_ns:
                    continue
                raw_ids = await self._hkeys(self._namespace_key(thread_id, checkpoint_ns))
                ids = sorted(
                    (item.decode() if isinstance(item, bytes) else str(item) for item in raw_ids),
                    reverse=True,
                )
                for checkpoint_id in ids:
                    if requested_id and checkpoint_id != requested_id:
                        continue
                    if before_id and checkpoint_id >= before_id:
                        continue
                    item = await self.aget_tuple(
                        {
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": checkpoint_id,
                            }
                        }
                    )
                    if item is None:
                        continue
                    if filter and not all(item.metadata.get(key) == value for key, value in filter.items()):
                        continue
                    yield item
                    yielded += 1
                    if limit is not None and yielded >= limit:
                        return

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        del new_versions
        configurable = config["configurable"]
        thread_id = str(configurable["thread_id"])
        checkpoint_ns = str(configurable.get("checkpoint_ns", ""))
        checkpoint_id = checkpoint["id"]
        record = json.dumps(
            {
                "checkpoint": self._encode(checkpoint),
                "metadata": self._encode(get_checkpoint_metadata(config, metadata)),
                "parent_id": configurable.get("checkpoint_id"),
            },
            separators=(",", ":"),
        )
        pipeline = self.redis.pipeline(transaction=True)
        pipeline.hset(self._namespace_key(thread_id, checkpoint_ns), checkpoint_id, record)
        pipeline.sadd(f"{self.prefix}:threads", thread_id)
        pipeline.sadd(
            f"{self.prefix}:namespaces:{quote(thread_id, safe='')}", checkpoint_ns
        )
        await pipeline.execute()
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        del task_path
        configurable = config["configurable"]
        thread_id = str(configurable["thread_id"])
        checkpoint_ns = str(configurable.get("checkpoint_ns", ""))
        checkpoint_id = str(configurable["checkpoint_id"])
        key = self._writes_key(thread_id, checkpoint_ns, checkpoint_id)
        pipeline = self.redis.pipeline(transaction=True)
        for index, (channel, value) in enumerate(writes):
            write_index = WRITES_IDX_MAP.get(channel, index)
            field = f"{quote(task_id, safe='')}:{write_index}"
            record = json.dumps(
                {
                    "task_id": task_id,
                    "channel": channel,
                    "value": self._encode(value),
                },
                separators=(",", ":"),
            )
            if write_index >= 0:
                pipeline.hsetnx(key, field, record)
            else:
                pipeline.hset(key, field, record)
        await pipeline.execute()

    async def adelete_thread(self, thread_id: str) -> None:
        raw_namespaces = await self._smembers(
            f"{self.prefix}:namespaces:{quote(thread_id, safe='')}"
        )
        keys: list[str] = []
        for raw_namespace in raw_namespaces:
            checkpoint_ns = (
                raw_namespace.decode() if isinstance(raw_namespace, bytes) else str(raw_namespace)
            )
            checkpoint_key = self._namespace_key(thread_id, checkpoint_ns)
            raw_ids = await self._hkeys(checkpoint_key)
            keys.append(checkpoint_key)
            keys.extend(
                self._writes_key(
                    thread_id,
                    checkpoint_ns,
                    raw_id.decode() if isinstance(raw_id, bytes) else str(raw_id),
                )
                for raw_id in raw_ids
            )
        keys.append(f"{self.prefix}:namespaces:{quote(thread_id, safe='')}")
        pipeline = self.redis.pipeline(transaction=True)
        if keys:
            pipeline.delete(*keys)
        pipeline.srem(f"{self.prefix}:threads", thread_id)
        await pipeline.execute()
