from __future__ import annotations

import asyncio
import socket

from industrial_agents.config import get_settings
from industrial_agents.runtime import Runtime


async def serve() -> None:
    settings = get_settings()
    if settings.execution_mode != "redis":
        raise RuntimeError("Worker requires IMA_EXECUTION_MODE=redis")
    runtime = Runtime(settings)
    await runtime.start()
    consumer = f"{socket.gethostname()}-{id(runtime)}"
    try:
        async for run_id in runtime.events.consume_runs(consumer):
            await runtime.execute(run_id)
    finally:
        await runtime.close()


def run() -> None:
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
