from __future__ import annotations

import asyncio


async def tcp_health(host: str, port: int) -> dict[str, object]:
    try:
        async with asyncio.timeout(1.5):
            reader, writer = await asyncio.open_connection(host, port)
        del reader
        writer.close()
        await writer.wait_closed()
        return {"status": "available", "host": host, "port": port}
    except Exception:
        return {"status": "unavailable", "host": host, "port": port}
