"""Home dashboard metrics — fixed KPIs and an hourly trend for one day.

The home page is a *fixed* (non-customizable) dashboard: its indicators are
hard-wired business definitions rather than user-configured tiles. Because
business tables are created dynamically by the Schema Manager, every metric
resolves its table by Chinese display name and its columns by Chinese label
(column comment) at request time — no English table/column names are
hard-coded, so renamed or recreated tables keep working.

Extending the dashboard is declarative: add an entry to :data:`KPI_DEFS`
(and compute it in :func:`_service_order_kpis` / :func:`_refund_kpis`) or a
group/series to :data:`TREND_GROUPS` / :data:`TREND_SERIES`; the frontend
renders whatever the payload lists, so new indicators appear without UI
changes.
"""

import datetime as dt
from typing import Any

from sqlalchemy import Date, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.services.schema_validator import (
    CHINESE_TO_ENGLISH_TABLE,
    get_registered_model,
)

# ── Business table / column labels (Chinese, as shown in the Schema Manager) ──

SERVICE_ORDER_TABLE = "服务工单列表"
REFUND_EXPORT_TABLE = "退费单导出列表"

SO_SN = "SN"
SO_ORDER = "工单号"
SO_CATEGORY = "服务类别"
SO_ITEM = "服务项"
SO_DATE = "登记时间"
SO_FINISH = "完成时间"
SO_STATUS = "状态"
SO_REGISTRAR = "登记人"
SO_REMARK = "备注"
SO_HANDLER = "处理人"

RE_AMOUNT = "实退金额"
RE_DATE = "创建时间"

REFUND_CATEGORY = "退款"
COMPLAINT_KEYWORD = "投诉"
# 服务项 values that denote a complaint even without the 投诉 keyword
COMPLAINT_EXTRA_ITEMS = ["全国12315平台", "公共服务平台", "消费者协会"]
# 登记人 values surfaced as 被投诉主体; anything else is treated as null
ACCUSED_SUBJECTS = ["深圳市云客猫科技有限公司", "大秦WiFi管家"]

# Cap on complaint detail rows returned per day (the table scrolls)
COMPLAINT_DETAIL_LIMIT = 500
# Status kept when one 工单号 appears both pending and finished
COMPLAINT_PREFERRED_STATUS = "已完成"
# Bound on raw rows pulled per day before de-duplication
COMPLAINT_RAW_LIMIT = 5000

# ── Declarative shape of the dashboard ───────────────────────────────────────
# ``format`` drives frontend number rendering ("int" | "currency");
# ``higher_is_better`` is the metric polarity used to color the day-over-day
# change (increase on a lower-is-better metric reads as bad / red).

KPI_DEFS: list[dict[str, Any]] = [
    {"key": "reception", "label": "接待数", "format": "int", "higher_is_better": False},
    {"key": "sessions", "label": "会话数", "format": "int", "higher_is_better": False},
    {"key": "refund_count", "label": "退款笔数", "format": "int", "higher_is_better": False},
    {"key": "refund_amount", "label": "退款金额", "format": "currency", "higher_is_better": False},
    {"key": "complaints", "label": "投诉数", "format": "int", "higher_is_better": False},
]

# Trend tabs (multi-select). Each group lists the series keys it shows.
TREND_GROUPS: list[dict[str, Any]] = [
    {"key": "reception", "label": "接待", "series": ["reception", "sessions"]},
    {"key": "complaint", "label": "投诉", "series": ["complaints"]},
]

TREND_SERIES: list[dict[str, str]] = [
    {"key": "reception", "label": "接待数"},
    {"key": "sessions", "label": "会话数"},
    {"key": "complaints", "label": "投诉数"},
]

HOURS = [f"{h:02d}:00" for h in range(24)]


# ── Resolution helpers ────────────────────────────────────────────────────────


def _resolve_model(chinese_table: str) -> type[DeclarativeBase] | None:
    """Return the registered dynamic model for a Chinese display name."""
    english = CHINESE_TO_ENGLISH_TABLE.get(chinese_table)
    if english is None:
        return None
    return get_registered_model(english)


def _col(model: type[DeclarativeBase], label: str) -> Any | None:
    """Return the table column whose Chinese label (comment) equals ``label``.

    Falls back to matching the raw column name so tables whose comments were
    cleared still resolve. Returns None when nothing matches.
    """
    from sqlalchemy import inspect as sa_inspect

    mapper = sa_inspect(model)
    fallback = None
    for col in mapper.columns:
        comment = (getattr(col, "comment", None) or "").strip()
        if comment == label:
            return col
        if col.name == label:
            fallback = col
    return fallback


def _columns(model: type[DeclarativeBase] | None, labels: tuple[str, ...]) -> dict[str, Any]:
    """Resolve several labels at once; missing ones are simply absent."""
    if model is None:
        return {}
    resolved: dict[str, Any] = {}
    for label in labels:
        col = _col(model, label)
        if col is not None:
            resolved[label] = col
    return resolved


def _as_number(value: Any) -> float:
    """Coerce Decimal/None DB values into a JSON-safe float."""
    if value is None:
        return 0.0
    return float(value)


def _iso(value: Any) -> str | None:
    """Coerce date/datetime DB values into ISO strings (None passthrough)."""
    if value is None:
        return None
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return str(value)


def _complaint_condition(item: Any) -> Any:
    """True for complaint work orders: 服务项 mentions 投诉 or is a platform."""
    return or_(item.contains(COMPLAINT_KEYWORD), item.in_(COMPLAINT_EXTRA_ITEMS))


# ── Metric computation ────────────────────────────────────────────────────────


def _so_columns() -> dict[str, Any]:
    """Resolve the 服务工单列表 columns the metrics rely on."""
    model = _resolve_model(SERVICE_ORDER_TABLE)
    return _columns(model, (SO_SN, SO_ORDER, SO_CATEGORY, SO_ITEM, SO_DATE))


async def _service_order_kpis(db: AsyncSession, day: dt.date) -> dict[str, int]:
    """Daily aggregates derived from 服务工单列表."""
    cols = _so_columns()
    date_col = cols.get(SO_DATE)
    sn = cols.get(SO_SN)
    order = cols.get(SO_ORDER)
    category = cols.get(SO_CATEGORY)
    item = cols.get(SO_ITEM)
    if date_col is None:
        return {}

    day_expr = cast(date_col, Date) == day

    # Each term only when its inputs resolved
    terms: list[tuple[str, Any]] = []
    if sn is not None:
        terms.append(("reception", func.count(sn.distinct())))
    if order is not None:
        terms.append(("sessions", func.count(order.distinct())))
    if order is not None and category is not None:
        terms.append(("refund_count", func.count(order.distinct()).filter(category == REFUND_CATEGORY)))
    if order is not None and item is not None:
        terms.append(("complaints", func.count(order.distinct()).filter(_complaint_condition(item))))
    if not terms:
        return {}

    stmt = select(*[expr.label(key) for key, expr in terms]).where(day_expr)
    row = (await db.execute(stmt)).one()
    mapping = row._mapping  # noqa: SLF001 - SQLAlchemy Row mapping
    return {key: int(mapping[key] or 0) for key, _ in terms}


async def _service_order_hourly(db: AsyncSession, day: dt.date) -> dict[str, list[int]]:
    """Hourly buckets for the trend chart, derived from 服务工单列表."""
    hourly: dict[str, list[int]] = {s["key"]: [0] * 24 for s in TREND_SERIES}
    cols = _so_columns()
    date_col = cols.get(SO_DATE)
    sn = cols.get(SO_SN)
    order = cols.get(SO_ORDER)
    item = cols.get(SO_ITEM)
    if date_col is None:
        return hourly

    day_expr = cast(date_col, Date) == day
    hour_expr = func.extract("hour", date_col)
    trend_terms: list[tuple[str, Any]] = []
    if sn is not None:
        trend_terms.append(("reception", func.count(sn.distinct())))
    if order is not None:
        trend_terms.append(("sessions", func.count(order.distinct())))
    if order is not None and item is not None:
        trend_terms.append(("complaints", func.count(order.distinct()).filter(_complaint_condition(item))))
    if not trend_terms:
        return hourly

    stmt = (
        select(hour_expr.label("hour"), *[expr.label(key) for key, expr in trend_terms])
        .where(day_expr)
        .group_by(hour_expr)
    )
    for row in await db.execute(stmt):
        mapping = row._mapping  # noqa: SLF001
        hour = int(mapping["hour"] or 0)
        if 0 <= hour < 24:
            for key, _ in trend_terms:
                hourly[key][hour] = int(mapping[key] or 0)

    return hourly


async def _refund_metrics(db: AsyncSession, day: dt.date) -> dict[str, float]:
    """KPIs derived from 退费单导出列表 (currently only 退款金额)."""
    kpis: dict[str, float] = {}
    model = _resolve_model(REFUND_EXPORT_TABLE)
    cols = _columns(model, (RE_AMOUNT, RE_DATE))
    amount = cols.get(RE_AMOUNT)
    date_col = cols.get(RE_DATE)
    if model is None or amount is None or date_col is None:
        return kpis

    stmt = select(func.coalesce(func.sum(amount), 0)).where(cast(date_col, Date) == day)
    kpis["refund_amount"] = _as_number((await db.execute(stmt)).scalar())
    return kpis


# ── Complaint detail (投诉明细) ───────────────────────────────────────────────

# Table field key → Chinese column label on 服务工单列表
_COMPLAINT_FIELDS: dict[str, str] = {
    "order_no": SO_ORDER,
    "device_sn": SO_SN,
    "register_time": SO_DATE,
    "finish_time": SO_FINISH,
    "status": SO_STATUS,
    "registrar": SO_REGISTRAR,
    "category": SO_ITEM,
    "content": SO_REMARK,
    "handler": SO_HANDLER,
}


async def compute_complaints(db: AsyncSession, day: dt.date, limit: int = COMPLAINT_DETAIL_LIMIT) -> dict[str, Any]:
    """Complaint work orders for ``day`` as table rows (newest first).

    One 工单号 can appear twice (a 待处理 snapshot plus the 已完成 record);
    the finished row wins so each order shows once. ``total`` is the
    de-duplicated count for the day; ``rows`` is capped at ``limit``.
    Columns the dashboard has not mapped yet (来源 / 补充) are returned as
    null so the frontend can render placeholders.
    """
    model = _resolve_model(SERVICE_ORDER_TABLE)
    if model is None:
        return {"total": 0, "rows": []}

    cols: dict[str, Any] = {}
    for key, label in _COMPLAINT_FIELDS.items():
        col = _col(model, label)
        if col is not None:
            cols[key] = col
    if "register_time" not in cols or "category" not in cols:
        return {"total": 0, "rows": []}

    condition = _complaint_condition(cols["category"])
    day_expr = cast(cols["register_time"], Date) == day

    stmt = (
        select(*cols.values())
        .where(day_expr, condition)
        .order_by(cols["register_time"].desc())
        .limit(COMPLAINT_RAW_LIMIT)
    )

    def _clean(value: Any) -> Any:
        if isinstance(value, str):
            return value.strip() or None
        return value

    raw: list[dict[str, Any]] = []
    for row in await db.execute(stmt):
        mapping = row._mapping  # noqa: SLF001
        values = {key: _clean(mapping[col.name]) for key, col in cols.items()}
        registrar = values.get("registrar")
        raw.append(
            {
                "order_no": values.get("order_no"),
                "device_sn": values.get("device_sn"),
                "register_time": _iso(values.get("register_time")),
                "finish_time": _iso(values.get("finish_time")),
                "status": values.get("status"),
                # Not yet derived from business data — placeholder column
                "source": None,
                "accused_subject": registrar if registrar in ACCUSED_SUBJECTS else None,
                "category": values.get("category"),
                "content": values.get("content"),
                "supplement": None,
                "handler": values.get("handler"),
            }
        )

    # De-duplicate per order: the 已完成 record wins over a pending snapshot.
    # Rows arrive newest-first, so the first row seen per status group is the
    # newest of that group.
    best: dict[Any, dict[str, Any]] = {}
    for row in raw:
        key = row["order_no"]
        current = best.get(key)
        if current is None:
            best[key] = row
        elif current["status"] != COMPLAINT_PREFERRED_STATUS and row["status"] == COMPLAINT_PREFERRED_STATUS:
            best[key] = row

    rows = sorted(best.values(), key=lambda r: r["register_time"] or "", reverse=True)
    return {"total": len(rows), "rows": rows[:limit]}


# ── Public entry point ────────────────────────────────────────────────────────


async def compute_overview(db: AsyncSession, day: dt.date) -> dict[str, Any]:
    """Assemble the full home payload (KPI cards + hourly trend) for ``day``.

    Each KPI also carries ``prev_value`` (the same metric for ``day - 1``) so
    the frontend can render a day-over-day percent change.
    """
    prev_day = day - dt.timedelta(days=1)

    so_kpis = await _service_order_kpis(db, day)
    re_kpis = await _refund_metrics(db, day)
    hourly = await _service_order_hourly(db, day)
    prev_so_kpis = await _service_order_kpis(db, prev_day)
    prev_re_kpis = await _refund_metrics(db, prev_day)

    values: dict[str, Any] = {**so_kpis, **re_kpis}
    prev_values: dict[str, Any] = {**prev_so_kpis, **prev_re_kpis}
    kpis = [
        {
            **defn,
            "value": values.get(defn["key"], 0 if defn["format"] == "int" else 0.0),
            "prev_value": prev_values.get(defn["key"], 0 if defn["format"] == "int" else 0.0),
        }
        for defn in KPI_DEFS
    ]

    return {
        "date": day.isoformat(),
        "kpis": kpis,
        "trend": {
            "groups": TREND_GROUPS,
            "hours": HOURS,
            "series": [{**s, "values": hourly.get(s["key"], [0] * 24)} for s in TREND_SERIES],
        },
    }
