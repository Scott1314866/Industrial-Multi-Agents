from __future__ import annotations

import asyncio

from redis.asyncio import Redis
from sqlalchemy import text

from industrial_agents.config import get_settings
from industrial_agents.infrastructure.database import Database
from industrial_agents.infrastructure.health import tcp_health


async def main() -> None:
    settings = get_settings()
    database = Database(settings.database_url)
    redis = Redis.from_url(settings.redis_url)
    try:
        async with database.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        print("mysql: available")
        await redis.ping()
        print("redis: available")
        milvus = await tcp_health(settings.milvus_host, settings.milvus_port)
        print(f"milvus: {milvus['status']}")
    finally:
        await redis.aclose()
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
