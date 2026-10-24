"""Tests for the health endpoint."""

from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """GET /api/v1/health"""

    def test_health_returns_200_when_database_connected(self, client: TestClient):
        """Healthy app returns 200 with status=ok and database=connected."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

        body = response.json()
        assert body["success"] is True
        assert body["data"]["status"] == "ok"
        assert body["data"]["api_version"] == "v1"
        assert body["data"]["database"] == "connected"

    def test_health_returns_503_when_database_unavailable(
        self, monkeypatch: "pytest.MonkeyPatch", tmp_db_url: str
    ):
        """When the database is unreachable, health reports degraded/503."""
        import os
        monkeypatch.setenv("DATABASE_URL", "sqlite:////nonexistent/path/nope.db")

        from app.core.config import reset_settings
        from app.database.session import reset_engine

        reset_settings()
        reset_engine()

        # Point to a path that will fail connectivity (directory doesn't exist,
        # and we make the engine point to an invalid URL to force failure)
        monkeypatch.setenv("DATABASE_URL", "sqlite:////nonexistent/path/impossible/nope.db")
        reset_settings()
        reset_engine()

        # Mock the check to return False directly for reliable testing
        from unittest.mock import patch
        from app.main import create_app

        app = create_app()
        client = TestClient(app)

        with patch("app.api.health.check_database_connection", return_value=False):
            response = client.get("/api/v1/health")

        assert response.status_code == 503
        body = response.json()
        assert body["success"] is False
        assert body["data"]["status"] == "degraded"
        assert body["data"]["database"] == "disconnected"

    def test_health_does_not_expose_secrets(self, client: TestClient):
        """Health response must not contain environment variables or file paths."""
        response = client.get("/api/v1/health")
        body_str = response.text.lower()

        assert "password" not in body_str
        assert "api_key" not in body_str
        assert "secret" not in body_str
        # Should not contain absolute file system paths
        assert "/users/" not in body_str

    def test_swagger_docs_accessible(self, client: TestClient):
        """Swagger UI must be accessible at /docs."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower() or "openapi" in response.text.lower()
