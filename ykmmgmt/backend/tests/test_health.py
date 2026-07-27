import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestHealthEndpoint:
    """GET /api/health — returns backend health status."""

    def test_returns_200_and_ok_status(self, client: TestClient):
        response = client.get("/api/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_response_content_type_is_json(self, client: TestClient):
        response = client.get("/api/health")

        assert response.headers["content-type"] == "application/json"

    def test_response_has_cors_headers(self, client: TestClient):
        response = client.get(
            "/api/health",
            headers={"Origin": "http://localhost:5173"},
        )

        # CORS headers are added when an Origin header is present
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert response.headers["access-control-allow-credentials"] == "true"


class TestAPIRoot:
    """GET / — no root endpoint is defined for this app."""

    def test_root_returns_404(self, client: TestClient):
        response = client.get("/")

        assert response.status_code == 404


class TestOpenAPIDocs:
    """OpenAPI docs are auto-generated and accessible."""

    def test_swagger_ui_is_accessible(self, client: TestClient):
        response = client.get("/docs")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_openapi_schema_is_accessible(self, client: TestClient):
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        assert schema["info"]["title"] == "YKMMgmt"
        assert schema["info"]["version"] == "0.1.0"
        assert "/api/health" in schema["paths"]

    def test_redoc_is_accessible(self, client: TestClient):
        response = client.get("/redoc")

        assert response.status_code == 200
