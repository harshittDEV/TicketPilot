"""
Tests for Tool and Skill REST API endpoints under /api/v1/tools and /api/v1/skills.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.integrations.registry import get_registry
from app.main import app
from app.skills.loader import get_skill_loader
from app.tools.browser.adapter import BrowserToolAdapter
from app.tools.desktop.adapter import DesktopToolAdapter


@pytest.fixture
def client():
    # Ensure tool adapters and skills are registered in the test client
    registry = get_registry()
    if not registry.is_registered("browser"):
        registry.register_tool("browser", BrowserToolAdapter(), force=True)
    if not registry.is_registered("desktop"):
        registry.register_tool("desktop", DesktopToolAdapter(), force=True)
    get_skill_loader().load_all()

    with TestClient(app) as test_client:
        yield test_client


class TestToolApiEndpoints:
    """Verify tool discovery and health endpoints."""

    def test_list_tools_returns_200(self, client):
        response = client.get("/api/v1/tools")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        tools = body["data"]
        names = [t["name"] for t in tools]
        assert "browser" in names

    def test_check_tool_health_success(self, client):
        response = client.get("/api/v1/tools/browser/health")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["tool"] == "browser"
        assert body["data"]["healthy"] is True

    def test_check_unknown_tool_health_returns_404(self, client):
        response = client.get("/api/v1/tools/nonexistent_tool_xyz/health")
        assert response.status_code == 404


class TestSkillApiEndpoints:
    """Verify skill discovery and metadata endpoints."""

    def test_list_skills_returns_200(self, client):
        response = client.get("/api/v1/skills")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        skills = body["data"]
        names = [s["name"] for s in skills]
        assert "browser_inspection" in names

    def test_get_skill_details_success(self, client):
        response = client.get("/api/v1/skills/browser_inspection")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        skill = body["data"]
        assert skill["name"] == "browser_inspection"
        assert len(skill["steps"]) == 4
        assert "browser" in skill["allowed_tools"]

    def test_get_nonexistent_skill_returns_404(self, client):
        response = client.get("/api/v1/skills/missing_skill_xyz")
        assert response.status_code == 404
