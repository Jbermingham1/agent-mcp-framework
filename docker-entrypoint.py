"""Entrypoint for containerized deployment.

Serves the container health endpoints (/, /health, /ready) used by
Docker and orchestrator probes. Requires the `serve` extra.
"""

import os

import uvicorn

from agent_mcp_framework import __version__
from agent_mcp_framework.health import create_health_app

app = create_health_app(
    service_name="agent-mcp-framework",
    version=__version__,
)

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host=host, port=port, log_level="info")
