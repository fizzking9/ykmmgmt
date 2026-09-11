"""Tests for the home dashboard endpoint — GET /api/home/overview.

The endpoint resolves business tables by Chinese display name and columns by
Chinese label. The positive path registers the real dynamic tables (the same
restore the server runs at startup) and cross-checks the payload against
plain name-based SQL, which validates both the label resolution and the
aggregation SQL without inventing a second table that shares a display name.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Date, cast, func, select

from app.services.home_metrics import ACCUSED_SUBJECTS, COMPLAINT_EXTRA_ITEMS
from main import app

pytestmark = pytest.mark.usefixtures("_dispose_engine_after_test")


@pytest.mark.asyncio
async def test_overview_shape():
    """The payload always carries the full declarative shape."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/home/overview", params={"date": "2026-03-01"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["date"] == "2026-03-01"
        labels = [k["label"] for k in body["kpis"]]
        assert labels == ["接待数", "会话数", "退款笔数", "退款金额", "投诉数"]
        assert len(body["trend"]["hours"]) == 24
        assert [g["label"] for g in body["trend"]["groups"]] == ["接待", "投诉"]
        assert len(body["trend"]["series"]) == 3


@pytest.mark.asyncio
async def test_overview_invalid_date():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/home/overview", params={"date": "not-a-date"})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_overview_matches_direct_sql():
    """KPIs and hourly buckets equal an independent name-based SQL computation."""
    from app.core.database import async_session_factory, engine
    from app.services import schema_manager as sm
    from app.services.schema_validator import get_registered_model

    # Same restore the server performs at startup so the real tables resolve
    async with engine.connect() as conn:
        await sm.restore_dynamic_tables(conn)

    so = get_registered_model("service_order")
    refund = get_registered_model("refund_export")
    assert so is not None and refund is not None
    t = so.__table__
    rt = refund.__table__

    async with async_session_factory() as s:
        day = (await s.execute(select(func.max(cast(t.c.register_time, Date))))).scalar()
    if day is None:
        pytest.skip("service_order has no rows")
    on_day = cast(t.c.register_time, Date) == day

    async with async_session_factory() as s:
        exp_reception = (await s.execute(select(func.count(t.c.device_sn.distinct())).where(on_day))).scalar()
        exp_sessions = (await s.execute(select(func.count(t.c.order_no.distinct())).where(on_day))).scalar()
        exp_refund_count = (
            await s.execute(select(func.count(t.c.order_no.distinct())).where(on_day, t.c.service_category == "退款"))
        ).scalar()
        exp_complaints = (
            await s.execute(
                select(func.count(t.c.order_no.distinct())).where(
                    on_day,
                    t.c.service_item.like("%投诉%") | t.c.service_item.in_(COMPLAINT_EXTRA_ITEMS),
                )
            )
        ).scalar()
        exp_refund_amount = (
            await s.execute(
                select(func.coalesce(func.sum(rt.c.actual_refund_amount), 0)).where(cast(rt.c.create_time, Date) == day)
            )
        ).scalar()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/home/overview", params={"date": day.isoformat()})
        assert resp.status_code == 200
        body = resp.json()
        values = {k["label"]: k["value"] for k in body["kpis"]}
        assert values["接待数"] == exp_reception
        assert values["会话数"] == exp_sessions
        assert values["退款笔数"] == exp_refund_count
        assert values["投诉数"] == exp_complaints
        assert values["退款金额"] == pytest.approx(float(exp_refund_amount))

        series = {s_["label"]: s_["values"] for s_ in body["trend"]["series"]}
        # Hourly buckets partition the day: their totals equal the daily KPIs
        assert sum(series["接待数"]) == exp_reception
        assert sum(series["会话数"]) == exp_sessions
        assert sum(series["投诉数"]) == exp_complaints
        assert all(len(v) == 24 for v in series.values())


@pytest.mark.asyncio
async def test_complaints_detail_rows():
    """投诉明细 rows match the broadened complaint condition and column mapping."""
    from app.core.database import async_session_factory, engine
    from app.services import schema_manager as sm
    from app.services.schema_validator import get_registered_model

    async with engine.connect() as conn:
        await sm.restore_dynamic_tables(conn)

    so = get_registered_model("service_order")
    assert so is not None
    t = so.__table__

    async with async_session_factory() as s:
        day = (await s.execute(select(func.max(cast(t.c.register_time, Date))))).scalar()
    if day is None:
        pytest.skip("service_order has no rows")

    condition = t.c.service_item.like("%投诉%") | t.c.service_item.in_(COMPLAINT_EXTRA_ITEMS)
    async with async_session_factory() as s:
        exp_orders = (
            await s.execute(
                select(func.count(t.c.order_no.distinct())).where(cast(t.c.register_time, Date) == day, condition)
            )
        ).scalar()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/home/complaints", params={"date": day.isoformat()})
        assert resp.status_code == 200
        body = resp.json()
        # One row per order: a 已完成 record replaces the pending snapshot
        assert body["total"] == exp_orders
        assert len(body["rows"]) == min(exp_orders, 500)
        order_nos = [r["order_no"] for r in body["rows"]]
        assert len(order_nos) == len(set(order_nos))
        for row in body["rows"]:
            assert {
                "order_no",
                "device_sn",
                "register_time",
                "finish_time",
                "status",
                "source",
                "accused_subject",
                "category",
                "content",
                "supplement",
                "handler",
            } <= set(row)
            assert row["accused_subject"] is None or row["accused_subject"] in ACCUSED_SUBJECTS
            # 来源 / 补充 are unmapped placeholders for now
            assert row["source"] is None and row["supplement"] is None

    # A non-已完成 row may only survive when the order has no 已完成 record
    async with async_session_factory() as s:
        for row in [r for r in body["rows"] if r["status"] != "已完成"][:10]:
            finished = (
                await s.execute(
                    select(func.count()).select_from(t).where(t.c.order_no == row["order_no"], t.c.status == "已完成")
                )
            ).scalar()
            assert finished == 0
