from __future__ import annotations

import asyncio
import re

import asyncmy
from sqlalchemy.engine import make_url

from industrial_agents.config import get_settings


async def main() -> None:
    url = make_url(get_settings().database_url)
    database = url.database or "industrial_agents"
    if not re.fullmatch(r"[A-Za-z0-9_]+", database):
        raise ValueError("Database name contains unsupported characters")
    connection = await asyncmy.connect(
        host=url.host or "127.0.0.1",
        port=url.port or 3306,
        user=url.username,
        password=url.password,
        autocommit=True,
    )
    try:
        async with connection.cursor() as cursor:
            await cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
            )
    finally:
        connection.close()
    print(f"Database '{database}' is ready at {url.host}:{url.port}")


if __name__ == "__main__":
    asyncio.run(main())
