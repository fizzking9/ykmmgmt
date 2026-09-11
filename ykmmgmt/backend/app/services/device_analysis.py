"""Device lifetime analysis — profile + cross-table incident timeline.

Given a device SN, this assembles a "lifetime" view: a device profile card
plus a unified, time-descending timeline of every incident recorded about
that device across *all* business tables that carry a device-SN column.

Business tables are created dynamically by the Schema Manager, so nothing
here hard-codes English table/column names:

* tables are discovered at request time from the model registry — any
  registered table exposing a device-SN column participates;
* the time column is taken from :data:`EXPLICIT_TIME_COLUMNS` for the few
  tables that carry several time columns; every other SN-bearing table is
  expected to have exactly one time column, which is auto-detected;
* columns are matched by their Chinese label (column comment), falling back
  to the raw column name, mirroring :mod:`app.services.home_metrics`.

Timeline cards are rendered generically (title / summary / amount / detail
fields) via small preference lists, so newly imported SN tables appear in
the timeline without code changes.
"""

import datetime as dt
from typing import Any

from sqlalchemy import Date, DateTime, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.services.schema_validator import (
    get_chinese_table_name,
    get_registered_model,
    get_registered_tables,
)

# ── Discovery rules ─────────────────────────────────────────────────────────

# Tables with several time columns need an explicit choice; keyed by both the
# Chinese display name and the physical name so either registration resolves.
EXPLICIT_TIME_COLUMNS: dict[str, str] = {
    "服务工单列表": "登记时间",
    "退费单导出列表": "创建时间",
    "设备套餐列表": "创建时间",
    "ai_acc_cs_record": "操作时间",
    "ai客服记录": "操作时间",
}

# Device-SN column labels (compared case-insensitively) and raw names.
SN_LABELS = {"sn", "设备sn", "设备号"}
SN_NAMES = {"sn", "device_sn", "devicesn"}

# Bookkeeping columns never shown / never treated as SN or time.
SKIP_COLUMNS = {"id", "imported_at", "created_at", "content_hash"}

RANGE_KEYS = ("day", "week", "month", "quarter", "half", "year", "all")

# ── Generic timeline-card rendering preferences ─────────────────────────────
# Ordered candidates: the first label present (with a non-empty value) wins.
TITLE_LABELS = ("工单号", "退费单号", "套餐名称", "问题类型", "订单号", "充值订单号")
SUMMARY_LABELS = (
    "状态", "当前状态", "服务类别", "服务项", "退款方式",
    "退费原因", "问题大类", "方案", "商户名称",
)
AMOUNT_LABELS = ("实退金额", "实际支付金额", "退费金额", "退款金额", "操作金额")

MAX_SUMMARY_PARTS = 3
MAX_FIELDS = 10


# ── Column resolution helpers ───────────────────────────────────────────────


def _columns(model: type[DeclarativeBase]) -> list[Any]:
    from sqlalchemy import inspect as sa_inspect

    return list(sa_inspect(model).columns)


def _label(col: Any) -> str:
    """The Chinese label (comment) of a column, falling back to its name."""
    return (getattr(col, "comment", None) or col.name).strip()


def _col_by_label(model: type[DeclarativeBase], label: str) -> Any | None:
    """Resolve a column by Chinese label, falling back to the raw name."""
    fallback = None
    for col in _columns(model):
        if _label(col) == label:
            return col
        if col.name == label:
            fallback = col
    return fallback


def _sn_column(model: type[DeclarativeBase]) -> Any | None:
    """The device-SN column, matched case-insensitively by label or name."""
    for col in _columns(model):
        if col.name in SKIP_COLUMNS:
            continue
        if _label(col).lower() in SN_LABELS or col.name.lower() in SN_NAMES:
            return col
    return None


def _is_time_like(col: Any) -> bool:
    if isinstance(col.type, (DateTime, Date)):
        return True
    label = _label(col)
    return label.endswith("时间") or label.endswith("日期")


def _time_column(model: type[DeclarativeBase], display: str, physical: str) -> Any | None:
    """Explicit time column for multi-time tables; else the single time column."""
    explicit = EXPLICIT_TIME_COLUMNS.get(display) or EXPLICIT_TIME_COLUMNS.get(physical)
    if explicit:
        return _col_by_label(model, explicit)
    candidates = [
        col for col in _columns(model)
        if col.name not in SKIP_COLUMNS and _is_time_like(col)
    ]
    return candidates[0] if len(candidates) == 1 else None


def discover_sources() -> list[dict[str, Any]]:
    """Every registered table that exposes both a device-SN and a time column."""
    sources: list[dict[str, Any]] = []
    for physical in get_registered_tables():
        model = get_registered_model(physical)
        if model is None:
            continue
        display = get_chinese_table_name(physical)
        sn_col = _sn_column(model)
        time_col = _time_column(model, display, physical)
        if sn_col is None or time_col is None or sn_col is time_col:
            continue
        sources.append(
            {
                "key": physical,
                "display": display,
                "model": model,
                "sn": sn_col,
                "time": time_col,
            }
        )
    return sources


# ── Time-frame handling ─────────────────────────────────────────────────────


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return (dt.date(year + 1, 1, 1) - dt.date(year, 12, 1)).days
    return (dt.date(year, month + 1, 1) - dt.date(year, month, 1)).days


def _shift_months(day: dt.date, months: int) -> dt.date:
    index = day.month - 1 - months
    year = day.year + index // 12
    month = index % 12 + 1
    return dt.date(year, month, min(day.day, _days_in_month(year, month)))


def range_start(key: str, now: dt.datetime | None = None) -> dt.datetime | None:
    """Inclusive lower bound for a time-frame key; None means 「所有」.

    Raises ValueError for an unknown key (the router turns it into a 422).
    """
    today = (now or dt.datetime.now()).date()
    if key == "all":
        return None
    if key == "day":
        start = today
    elif key == "week":
        start = today - dt.timedelta(days=6)
    elif key == "month":
        start = _shift_months(today, 1)
    elif key == "quarter":
        start = _shift_months(today, 3)
    elif key == "half":
        start = _shift_months(today, 6)
    elif key == "year":
        start = _shift_months(today, 12)
    else:
        raise ValueError(key)
    return dt.datetime.combine(start, dt.time.min)


# ── Value formatting / generic card building ────────────────────────────────


def _format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dt.datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time.min).strftime("%Y-%m-%d %H:%M:%S")
    return str(value).strip()


def _as_datetime(value: Any) -> dt.datetime | None:
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time.min)
    if isinstance(value, str):
        text = value.strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
            try:
                return dt.datetime.strptime(text, fmt)
            except ValueError:
                continue
    return None


def _as_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _instance_values(model: type[DeclarativeBase], instance: Any) -> dict[str, Any]:
    """{column_name: value} for one ORM instance."""
    return {col.name: getattr(instance, col.name, None) for col in _columns(model)}


def _row_pairs(
    model: type[DeclarativeBase], values: dict[str, Any],
) -> list[tuple[Any, str, str]]:
    """[(column, label, formatted_value)] for every non-bookkeeping column."""
    pairs: list[tuple[Any, str, str]] = []
    for col in _columns(model):
        if col.name in SKIP_COLUMNS:
            continue
        pairs.append((col, _label(col), _format_value(values.get(col.name))))
    return pairs


def _pick(pairs: list[tuple[Any, str, str]], labels: tuple[str, ...]) -> str:
    """First non-empty formatted value whose label is in ``labels``."""
    by_label = {label: value for _, label, value in pairs}
    for label in labels:
        value = by_label.get(label, "")
        if value:
            return value
    return ""


def _build_item(source: dict[str, Any], values: dict[str, Any]) -> dict[str, Any] | None:
    """Render one DB row as a timeline card; None when it has no usable time."""
    pairs = _row_pairs(source["model"], values)
    raw_time = values.get(source["time"].name)
    time_value = _format_value(raw_time)
    when = _as_datetime(raw_time)
    if when is None:
        return None

    sn_label = _label(source["sn"])
    time_label = _label(source["time"])
    by_label = {label: value for _, label, value in pairs}

    title = _pick(pairs, TITLE_LABELS)
    if not title:
        title = next(
            (v for _, lab, v in pairs if lab != sn_label and lab.endswith("号") and v), ""
        )
    if not title:
        title = next((v for _, lab, v in pairs if "名称" in lab and v), "")
    if not title:
        title = next((v for _, lab, v in pairs if lab != sn_label and v), "")
    if not title:
        title = by_label.get(sn_label, "")

    summary = "·".join(
        part
        for part in (
            by_label.get(label, "")
            for label in SUMMARY_LABELS
        )
        if part
    )
    summary = "·".join(summary.split("·")[:MAX_SUMMARY_PARTS])

    amount = _as_number(_pick(pairs, AMOUNT_LABELS))
    if amount is None:
        amount = next(
            (
                n
                for _, label, value in pairs
                if "金额" in label and (n := _as_number(value)) is not None
            ),
            None,
        )

    fields = [
        {"label": label, "value": value}
        for _, label, value in pairs
        if value and label not in (sn_label, time_label)
    ][:MAX_FIELDS]

    return {
        "source": source["key"],
        "source_label": source["display"],
        "time": time_value,
        "title": title,
        "summary": summary,
        "amount": amount,
        "fields": fields,
    }


# ── Device profile ──────────────────────────────────────────────────────────

PROFILE_LABELS = ("设备类型", "设备类型备注", "状态", "激活时间", "手机号")
MERCHANT_SOURCES = ("设备套餐列表", "退费单导出列表")


async def _latest_row(
    db: AsyncSession, source: dict[str, Any], sn: str,
) -> Any | None:
    stmt = (
        select(source["model"])
        .where(source["sn"] == sn)
        .order_by(desc(source["time"]))
        .limit(1)
    )
    return (await db.execute(stmt)).scalars().first()


async def _build_profile(
    db: AsyncSession,
    sn: str,
    sources: list[dict[str, Any]],
    counts: list[dict[str, Any]],
) -> dict[str, Any]:
    fields: list[dict[str, str]] = [{"label": "设备 SN", "value": sn}]

    so = next((s for s in sources if s["display"] == "服务工单列表"), None)
    if so is not None:
        row = await _latest_row(db, so, sn)
        if row is not None:
            by_label = {
                label: value
                for _, label, value in _row_pairs(so["model"], _instance_values(so["model"], row))
            }
            for label in PROFILE_LABELS:
                value = by_label.get(label, "")
                if value:
                    fields.append({"label": label, "value": value})

    merchant = ""
    for display in MERCHANT_SOURCES:
        src = next((s for s in sources if s["display"] == display), None)
        if src is None:
            continue
        row = await _latest_row(db, src, sn)
        if row is not None:
            by_label = {
                label: value
                for _, label, value in _row_pairs(src["model"], _instance_values(src["model"], row))
            }
            merchant = by_label.get("商户名称", "")
            if merchant:
                break
    if merchant:
        fields.append({"label": "商户", "value": merchant})

    return {
        "sn": sn,
        "fields": fields,
        "counts": counts,
        "total": sum(entry["count"] for entry in counts),
    }


# ── Public entry point ──────────────────────────────────────────────────────


async def analyze(
    db: AsyncSession, sn: str, range_key: str, limit: int,
) -> dict[str, Any]:
    """Assemble the device profile + merged incident timeline for ``sn``.

    Raises ValueError for an unknown ``range_key``. Tables that are not
    registered (or lack an SN / time column) are silently skipped, so a
    partially populated database degrades gracefully instead of erroring.
    """
    start = range_start(range_key)
    sources = discover_sources()

    timeline: list[dict[str, Any]] = []
    counts: list[dict[str, Any]] = []
    for source in sources:
        model, sn_col, time_col = source["model"], source["sn"], source["time"]

        where = [sn_col == sn]
        if start is not None:
            where.append(time_col >= start)

        count_stmt = select(func.count()).select_from(model).where(*where)
        count = int((await db.execute(count_stmt)).scalar() or 0)
        counts.append({"source": source["key"], "source_label": source["display"], "count": count})

        rows = (
            await db.execute(
                select(model).where(*where).order_by(desc(time_col)).limit(limit)
            )
        ).scalars().all()
        for instance in rows:
            item = _build_item(source, _instance_values(model, instance))
            if item is not None:
                timeline.append(item)

    timeline.sort(key=lambda item: item["time"], reverse=True)
    timeline = timeline[:limit]

    profile = await _build_profile(db, sn, sources, counts)
    return {
        "sn": sn,
        "range": range_key,
        "limit": limit,
        "profile": profile,
        "timeline": timeline,
    }
