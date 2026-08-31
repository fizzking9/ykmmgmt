"""Authorization tests — lockdown, L3 read-only, admin/root mutations."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from tests.conftest import anonymous_cookies, auth_cookies

# Endpoints representing every protected router
READ_ENDPOINTS = [
    "/api/tables",
    "/api/views",
    "/api/visualizations",
    "/api/dashboards",
    "/api/imports",
]
MUTATING_ENDPOINTS = [
    ("POST", "/api/views", 422),  # body validation runs after the 403 check is moot; auth checked first
    ("DELETE", f"/api/views/{uuid.uuid4()}", 404),
    ("DELETE", f"/api/visualizations/{uuid.uuid4()}", 404),
    ("DELETE", f"/api/dashboards/{uuid.uuid4()}", 404),
    ("GET", "/api/schema/tables", 200),  # schema reads are admin-only
    ("GET", "/api/users", 200),  # user management is admin-only
]


@pytest.mark.usefixtures("_dispose_engine_after_test")
class TestUnauthenticated:
    async def test_all_read_endpoints_return_401(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies=anonymous_cookies()) as client:
            for url in READ_ENDPOINTS:
                resp = await client.get(url)
                assert resp.status_code == 401, f"{url} returned {resp.status_code}"

    async def test_mutating_endpoints_return_401(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies=anonymous_cookies()) as client:
            for method, url, _ in MUTATING_ENDPOINTS:
                resp = await client.request(method, url)
                assert resp.status_code == 401, f"{method} {url} returned {resp.status_code}"

    async def test_health_remains_public(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies=anonymous_cookies()) as client:
            resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


@pytest.mark.usefixtures("_dispose_engine_after_test")
class TestL3User:
    async def test_get_requests_succeed(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("user")) as client:
            for url in READ_ENDPOINTS:
                resp = await client.get(url)
                assert resp.status_code == 200, f"{url} returned {resp.status_code}"

    async def test_mutations_return_403(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("user")) as client:
            for method, url, _ in MUTATING_ENDPOINTS:
                resp = await client.request(method, url)
                assert resp.status_code == 403, f"{method} {url} returned {resp.status_code}"

    async def test_import_upload_returns_403(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("user")) as client:
            resp = await client.post(
                "/api/imports",
                files={"file": ("x.csv", b"a,b\n1,2", "text/csv")},
                data={"target_table": "whatever"},
            )
        assert resp.status_code == 403

    async def test_schema_management_blocked(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("user")) as client:
            resp = await client.post(
                "/api/schema/tables",
                json={"name": "l3_should_fail", "columns": [{"name": "x", "type": "Text"}]},
            )
        assert resp.status_code == 403


@pytest.mark.usefixtures("_dispose_engine_after_test")
class TestAdminAndRoot:
    async def test_admin_can_create_dashboard(self):
        transport = ASGITransport(app=app)
        name = f"authz_dash_{uuid.uuid4().hex[:8]}"
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("admin")) as client:
            resp = await client.post(
                "/api/dashboards",
                json={"name": name, "description": "authz test", "layout_json": []},
            )
            assert resp.status_code == 201, resp.text
            dash_id = resp.json()["id"]

            # cleanup
            resp = await client.delete(f"/api/dashboards/{dash_id}")
            assert resp.status_code == 204

    async def test_root_can_create_dashboard(self):
        transport = ASGITransport(app=app)
        name = f"authz_dash_{uuid.uuid4().hex[:8]}"
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("root")) as client:
            resp = await client.post(
                "/api/dashboards",
                json={"name": name, "description": "authz test", "layout_json": []},
            )
            assert resp.status_code == 201, resp.text
            dash_id = resp.json()["id"]

            resp = await client.delete(f"/api/dashboards/{dash_id}")
            assert resp.status_code == 204

    async def test_admin_schema_reads_succeed(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("admin")) as client:
            resp = await client.get("/api/schema/tables")
        assert resp.status_code == 200
