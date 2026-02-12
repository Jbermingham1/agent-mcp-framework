"""Tests for the health check HTTP endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from agent_mcp_framework.health import create_health_app


@pytest.fixture
def health_app():
    return create_health_app(service_name="test-server", version="0.1.0")


@pytest.fixture
async def client(health_app):
    transport = ASGITransport(app=health_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_returns_200(client):
    response = await client.get("/health")
    assert response.status_code == 200


async def test_health_returns_status_ok(client):
    response = await client.get("/health")
    data = response.json()
    assert data["status"] == "healthy"


async def test_health_returns_service_name(client):
    response = await client.get("/health")
    data = response.json()
    assert data["service"] == "test-server"


async def test_health_returns_version(client):
    response = await client.get("/health")
    data = response.json()
    assert data["version"] == "0.1.0"


async def test_health_returns_timestamp(client):
    response = await client.get("/health")
    data = response.json()
    assert "timestamp" in data


async def test_root_returns_service_info(client):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "test-server"
    assert "mcp" in data["description"].lower() or "agent" in data["description"].lower()


async def test_readiness_returns_200(client):
    response = await client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
