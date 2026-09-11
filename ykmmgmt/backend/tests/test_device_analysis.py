"""Tests for the device-analysis service and endpoint."""

import datetime as dt

import pytest
from httpx import ASGITransport, AsyncClient

from app.services import device_analysis as da

# ── Pure helpers: time-frame bounds ─────────────────────────────────────────


def test_range_start_all_is_unbounded():
    assert da.range_start("all") is None


def test_range_start_day_and_week():
    now = dt.datetime(2026, 9, 11, 15, 30, 0)
    assert da.range_start("day", now) == dt.datetime(2026, 9, 11, 0, 0)
    assert da.range_start("week", now) == dt.datetime(2026, 9, 5, 0, 0)


def test_range_start_month_and_year_shift():
    now = dt.datetime(2026, 9, 11, 0, 0)
    assert da.range_start("month", now) == dt.datetime(2026, 8, 11, 0, 0)
    assert da.range_start("quarter", now) == dt.datetime(2026, 6, 11, 0, 0)
    assert da.range_start("half", now) == dt.datetime(2026, 3, 11, 0, 0)
    assert da.range_start("year", now) == dt.datetime(2025, 9, 11, 0, 0)


def test_range_start_clamps_month_end():
    # 2026-03-31 minus one month → 2026-02-28 (Feb has no 31st)
    now = dt.datetime(2026, 3, 31, 0, 0)
    assert da.range_start("month", now) == dt.datetime(2026, 2, 28, 0, 0)


def test_range_start_unknown_key_raises():
    with pytest.raises(ValueError):
        da.range_start("fortnight")


# ── Endpoint: validation + graceful shape ───────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.usefixtures("_dispose_engine_after_test")
async def test_endpoint_rejects_invalid_range():
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/device-analysis/profile", params={"sn": "X", "range": "nope"}
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
@pytest.mark.usefixtures("_dispose_engine_after_test")
async def test_endpoint_rejects_empty_sn():
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/device-analysis/profile", params={"sn": "   "})
        assert resp.status_code == 422


@pytest.mark.asyncio
@pytest.mark.usefixtures("_dispose_engine_after_test")
async def test_endpoint_returns_wellformed_payload():
    """Whatever tables happen to be registered, the payload shape holds."""
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/device-analysis/profile",
            params={"sn": "00000000000000", "range": "all", "limit": 10},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["sn"] == "00000000000000"
        assert body["range"] == "all"
        assert body["limit"] == 10
        assert isinstance(body["timeline"], list)
        assert isinstance(body["profile"]["counts"], list)
        assert body["profile"]["total"] == sum(
            c["count"] for c in body["profile"]["counts"]
        )


# ── Discovery + integration against the live business tables ────────────────


@pytest.mark.asyncio
@pytest.mark.usefixtures("_dispose_engine_after_test")
async def test_discovery_and_timeline_against_live_tables():
    """With dynamic tables restored, mapped tables resolve their explicit time
    column and a real SN yields a sorted, limit-bounded timeline."""
    from sqlalchemy import select

    from app.core.database import async_session_factory, engine
    from app.services import schema_manager as sm
    from app.services.schema_validator import CHINESE_TO_ENGLISH_TABLE, get_registered_model
    from main import app

    async with engine.connect() as conn:
        await sm.restore_dynamic_tables(conn)

    so_name = CHINESE_TO_ENGLISH_TABLE.get("服务工单列表")
    so = get_registered_model(so_name) if so_name else None
    if so is None:
        pytest.skip("服务工单列表 is not registered in this environment")

    sources = {s["display"]: s for s in da.discover_sources()}
    assert "服务工单列表" in sources
    assert da._label(sources["服务工单列表"]["time"]) == "登记时间"
    assert da._label(sources["服务工单列表"]["sn"]) == "SN"

    sn_col = sources["服务工单列表"]["sn"]
    async with async_session_factory() as s:
        sn = (
            await s.execute(select(sn_col).where(sn_col.is_not(None)).limit(1))
        ).scalar()
    if not sn:
        pytest.skip("服务工单列表 has no rows")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/device-analysis/profile",
            params={"sn": sn, "range": "all", "limit": 20},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["profile"]["sn"] == sn
        assert body["profile"]["total"] >= 1
        assert len(body["timeline"]) <= 20

        times = [item["time"] for item in body["timeline"]]
        assert times == sorted(times, reverse=True)

        so_count = next(
            (c["count"] for c in body["profile"]["counts"] if c["source_label"] == "服务工单列表"),
            0,
        )
        assert so_count >= 1
