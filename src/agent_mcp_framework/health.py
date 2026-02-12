"""Lightweight health check HTTP endpoint for containerized deployments."""

from __future__ import annotations

import datetime

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


def create_health_app(
    service_name: str = "agent-mcp-framework",
    version: str = "0.1.0",
) -> Starlette:
    """Create a Starlette app with health check endpoints.

    Endpoints:
        GET /        — Service info
        GET /health  — Liveness probe (always 200 if process is running)
        GET /ready   — Readiness probe
    """

    async def root(request: Request) -> JSONResponse:
        return JSONResponse({
            "service": service_name,
            "version": version,
            "description": "Multi-agent MCP pipeline framework",
        })

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({
            "status": "healthy",
            "service": service_name,
            "version": version,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })

    async def ready(request: Request) -> JSONResponse:
        return JSONResponse({
            "ready": True,
            "service": service_name,
        })

    return Starlette(
        routes=[
            Route("/", root),
            Route("/health", health),
            Route("/ready", ready),
        ],
    )
