from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse, Response

from industrial_agents.config import Settings, get_settings
from industrial_agents.infrastructure.health import tcp_health
from industrial_agents.runtime import Runtime
from industrial_agents.web.routes import router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        runtime = Runtime(settings)
        await runtime.start()
        app.state.runtime = runtime
        yield
        await runtime.close()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Last-Event-ID", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        return response

    @app.get("/healthz", tags=["operations"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", tags=["operations"])
    async def readyz(request: Request) -> dict[str, object]:
        runtime: Runtime = request.app.state.runtime
        rag = await runtime.rag.health()
        milvus = await tcp_health(settings.milvus_host, settings.milvus_port)
        return {
            "status": "ready",
            "rag": rag,
            "checkpoint": {"status": "available", "mode": runtime.checkpoint_mode},
            "milvus": {
                **milvus,
                "database": settings.milvus_database,
                "collection": settings.milvus_collection,
                "ownership": "external-rag",
            },
        }

    app.include_router(router, prefix=settings.api_prefix)
    return app


app = create_app()
