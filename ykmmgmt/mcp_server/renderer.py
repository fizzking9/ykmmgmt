"""matplotlib renderer — turns visualization data into deterministic PNG charts.

Consumes the exact payload of ``GET /api/visualizations/{id}/data``
(columns, rows, column_types, chart_type, config_json) and writes a PNG.

The backend ``/data`` endpoint returns RAW view rows — the UI aggregates
client-side before Recharts draws anything. To produce charts identical to
what users see, this module replicates that pipeline with the same semantics:

- ``processTimeSeriesRows``: date-x charts bucket by ``time_granularity`` and
  aggregate y columns with ``time_aggregation`` (default SUM)
- ``aggregateCategoricalRows``: bar charts with a categorical x aggregate per
  category with ``config.aggregation`` (default SUM; COUNT counts rows)
- ``limitCategories`` + ``pivotForGroupBy``: ``group_by_column`` splits into
  per-category series, top-10 categories kept, the rest merged into 其他
- pie: rows grouped by label, aggregated (default SUM), top-8 slices + 其他
- histogram: shared bins across all configured columns
- boxplot: per-category five-number summaries, top-10 categories

JS ``Number()`` coercion quirks (null/"" → 0) and placeholder labels
(未知/其他) are replicated deliberately for parity with the frontend.

Chart *styling* follows matplotlib conventions rather than copying the
Recharts theme — different library, different medium (a static PNG has no
hover, zoom, or brush): the frontend's color palette and light grid are
reused for familiarity, but ticks are chosen and formatted by matplotlib's
own locator/formatter (only 万/亿 units are layered on for large values),
categorical axes keep EVERY label because bars and boxes map 1:1 to their
categories, continuous date axes are thinned to a readable handful, legends
sit above the axes instead of on top of the data, and titles/captions come
from ``config_json`` (title/x_label/y_label).

Chinese text renders through an explicit CJK font fallback chain.
"""

import datetime as dt
import logging
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless — must be set before pyplot import

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.ticker import ScalarFormatter  # noqa: E402

# CJK-capable font candidates, tried in order (Windows → macOS → Linux)
_FONT_CANDIDATES = ("Microsoft YaHei", "SimHei", "PingFang SC", "Noto Sans CJK SC", "WenQuanYi Micro Hei")

_FIGSIZE = (10, 6)
_DPI = 150

# Chart styling — mirrors the frontend's industrial-standard constants
# (VisualizationBuilderPage.tsx) so an exported PNG reads like the in-app chart
_COLORS = ("#2563eb", "#dc2626", "#16a34a", "#ca8a04", "#9333ea", "#0891b2")  # COLOR_THEMES[0]
_TICK_COLOR = "#64748b"  # AXIS_TICK.fill
_AXIS_LINE_COLOR = "#cbd5e1"  # AXIS_LINE_STROKE
_GRID_COLOR = "#e2e8f0"  # GRID_STROKE
_TITLE_COLOR = "#0f172a"
_MARKERS = ("o", "s", "^", "D", "x", "*")  # SYMBOL_SHAPES parity
_MAX_X_TICKS = 8  # continuous (date/numeric) axes show at most this many ticks
_MAX_ANGLED_LABELS = 12  # beyond this, categorical labels go vertical and shrink
_LINE_DOT_MAX_POINTS = 60  # denser lines drop markers: a static image has no hover

# Frontend pipeline constants (VisualizationBuilderPage.tsx)
_UNKNOWN = "未知"  # categoryValue placeholder for null/empty
_OTHER = "其他"  # merged bucket for beyond-top-N categories/slices
_MAX_CATEGORIES = 10
_MAX_SCATTER_POINTS = 2000
_PIE_MAX_SLICES = 8
_PIE_MIN_LABEL_PERCENT = 4.0  # slices below 4% get no on-chart label


class RenderError(Exception):
    """The visualization payload cannot be rendered (bad config or data)."""


def _select_font() -> str | None:
    """First installed CJK font, or None (matplotlib default) if none exist."""
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in _FONT_CANDIDATES:
        if name in installed:
            return name
    return None


def _apply_font() -> None:
    """Point matplotlib at a CJK font so Chinese labels never tofu.

    Must run BEFORE any figure is created: axes capture the default font
    properties at creation time, so setting rcParams afterwards leaves tick
    labels on the fallback font. Applied once at module import (idempotent
    for tests that re-import or reset rcParams).
    """
    font = _select_font()
    if font is not None:
        plt.rcParams["font.family"] = font
    # U+2212 minus is missing from many CJK fonts — use ASCII hyphen
    plt.rcParams["axes.unicode_minus"] = False


def _apply_style() -> None:
    """Apply the shared chart style once, before any figure is created.

    Same reasoning as :func:`_apply_font` — axes capture rcParams at
    creation time, so this runs at module import.
    """
    # CJK fonts ship no semibold weight — matplotlib falls back to 700 and
    # warns on every render; the fallback is intended, so keep the log clean.
    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
    plt.rcParams.update(
        {
            "axes.edgecolor": _AXIS_LINE_COLOR,
            "axes.labelcolor": _TICK_COLOR,
            "axes.labelsize": 11,
            "axes.titlecolor": _TITLE_COLOR,
            "axes.titlesize": 13,
            "axes.titleweight": "semibold",
            "axes.unicode_minus": False,
            "xtick.color": _TICK_COLOR,
            "ytick.color": _TICK_COLOR,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            # No tick marks — the UI renders tickLine={false}
            "xtick.major.size": 0,
            "ytick.major.size": 0,
            "font.size": 11,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "legend.frameon": False,
            "legend.fontsize": 10,
            "lines.linewidth": 2,
            "lines.markersize": 4,
        }
    )


_apply_font()
_apply_style()


# ── JS-parity value helpers ──────────────────────────────────────────────────


def _js_number(val: Any) -> float:
    """JavaScript ``Number()`` semantics — the frontend aggregates with them.

    null and "" coerce to 0, booleans to 0/1, numeric strings parse;
    everything else is NaN.
    """
    if val is None:
        return 0.0
    if isinstance(val, bool):
        return 1.0 if val else 0.0
    if isinstance(val, str):
        if not val.strip():
            return 0.0
        try:
            return float(val)
        except ValueError:
            return math.nan
    try:
        return float(val)
    except (TypeError, ValueError):
        return math.nan


def _numeric_cell(val: Any) -> float:
    """Coerce one cell to float for plotting; NaN gaps for unusable values.

    Numeric *strings* ("0.05") count — text-typed view columns return
    numbers as strings. NaN (not row-dropping) keeps series aligned with
    the X axis: matplotlib renders NaN as a gap, matching the frontend.
    """
    if val is None:
        return math.nan
    try:
        return float(val)
    except (TypeError, ValueError):
        return math.nan


def _numeric(rows: list[dict], column: str) -> list[float]:
    """Coerce a column to floats, skipping non-numeric / missing cells.

    Only for aggregations (KPI) where position does not matter — plotting
    code must use :func:`_numeric_cell` per cell instead.
    """
    return [v for v in (_numeric_cell(r.get(column)) for r in rows) if not math.isnan(v)]


def _x_str(row: dict, column: str) -> str:
    val = row.get(column)
    return "" if val is None else str(val)


def _category_value(row: dict, column: str) -> str:
    """categoryValue(): null/empty becomes 未知 so every series has a label."""
    return _x_str(row, column) or _UNKNOWN


def _aggregate(values: list[float], method: str) -> float:
    """aggregateValues(): SUM/AVG/COUNT/MIN/MAX, default SUM, empty → 0."""
    if not values:
        return 0.0
    if method == "AVG":
        return sum(values) / len(values)
    if method == "COUNT":
        return float(len(values))
    if method == "MIN":
        return min(values)
    if method == "MAX":
        return max(values)
    return sum(values)  # SUM and unknown methods


def _require(config: dict[str, Any], key: str, name: str) -> Any:
    """Fetch a required config_json key; raise a Chinese RenderError if absent."""
    value = config.get(key)
    if value is None or value == "":
        raise RenderError(f"可视化「{name}」缺少渲染必需的配置项 '{key}'")
    return value


def _parse_date(value: str) -> dt.datetime | None:
    """Parse what JS ``new Date()`` accepts for reduced-precision ISO strings.

    "2026" and "2026-06" are valid JS dates (Jan 1 / Jun 1); Python's
    fromisoformat needs the missing parts appended.
    """
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    for candidate in (text, f"{text}-01", f"{text}-01-01"):
        try:
            return dt.datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _truncate_date(value: str, granularity: str) -> str:
    """truncateDate(): bucket key for a date value at the given granularity."""
    parsed = _parse_date(value)
    if parsed is None:
        return value
    if granularity == "day":
        return parsed.strftime("%Y-%m-%d")
    if granularity == "week":
        monday = (parsed - dt.timedelta(days=parsed.weekday())).date()
        return monday.isoformat()
    if granularity == "month":
        return parsed.strftime("%Y-%m")
    if granularity == "quarter":
        return f"{parsed.year}-Q{(parsed.month - 1) // 3 + 1}"
    if granularity == "year":
        return str(parsed.year)
    return value


def _date_columns(data: dict) -> set[str]:
    """Columns the frontend treats as dates (declared type wins over inference)."""
    column_types = data.get("column_types") or {}
    rows = data.get("rows") or []
    dates = {col for col, ctype in column_types.items() if ctype == "date"}
    for col in data.get("columns") or []:
        if col in dates:
            continue
        sample = [r.get(col) for r in rows if r.get(col) is not None][:5]
        if sample and all(_parse_date(str(v)) is not None for v in sample):
            dates.add(col)
    return dates


# ── Frontend data-pipeline replicas ──────────────────────────────────────────


def _process_time_series_rows(
    rows: list[dict],
    x_column: str,
    y_columns: list[str],
    config: dict,
    is_time_series: bool,
) -> list[dict]:
    """processTimeSeriesRows(): x filter, date range, bucket + aggregate."""
    filtered = [r for r in rows if r.get(x_column) is not None and _x_str(r, x_column) != ""]

    if is_time_series:
        range_start = config.get("date_range_start")
        if range_start:
            filtered = [r for r in filtered if _x_str(r, x_column) >= str(range_start)]
        range_end = config.get("date_range_end")
        if range_end:
            parsed_end = _parse_date(str(range_end))
            if parsed_end is not None:
                # JS adds one day so the end date itself is included
                end_exclusive = (parsed_end + dt.timedelta(days=1)).strftime("%Y-%m-%d")
                filtered = [r for r in filtered if _x_str(r, x_column) < end_exclusive]

    if not is_time_series:
        return filtered

    granularity = config.get("time_granularity") or "none"
    # No aggregation — raw rows sorted chronologically
    if granularity == "none":
        return sorted(filtered, key=lambda r: _x_str(r, x_column))

    aggregation = config.get("time_aggregation") or "SUM"
    group_col = config.get("group_by_column") or ""
    buckets: dict[str, list[dict]] = {}
    for row in filtered:
        bucket_key = _truncate_date(_x_str(row, x_column), granularity)
        group_key = _category_value(row, group_col) if group_col else ""
        key = f"{bucket_key}||{group_key}" if group_col else bucket_key
        buckets.setdefault(key, []).append(row)

    result = []
    for key, bucket_rows in buckets.items():
        bucket_key, _, group_key = key.partition("||")
        out: dict[str, Any] = {x_column: bucket_key}
        if group_col and group_key:
            out[group_col] = group_key
        for y_col in y_columns:
            values = [v for v in (_js_number(r.get(y_col)) for r in bucket_rows) if not math.isnan(v)]
            out[y_col] = _aggregate(values, aggregation)
        result.append(out)
    result.sort(key=lambda r: _x_str(r, x_column))
    return result


def _aggregate_categorical_rows(
    rows: list[dict],
    x_column: str,
    y_columns: list[str],
    group_col: str,
    method: str,
) -> list[dict]:
    """aggregateCategoricalRows(): bar charts with categorical x aggregate per category."""
    buckets: dict[str, tuple[str, str, list[dict]]] = {}
    for row in rows:
        x_val = _x_str(row, x_column)
        cat = _category_value(row, group_col) if group_col else ""
        key = f"{x_val}||{cat}" if group_col else x_val
        if key not in buckets:
            buckets[key] = (x_val, cat, [])
        buckets[key][2].append(row)

    out = []
    for x_val, cat, bucket_rows in buckets.values():
        row_out: dict[str, Any] = {x_column: x_val}
        if group_col and cat:
            row_out[group_col] = cat
        for y_col in y_columns:
            if method == "COUNT":
                # COUNT counts rows regardless of the Y value
                row_out[y_col] = float(len(bucket_rows))
            else:
                values = [v for v in (_js_number(r.get(y_col)) for r in bucket_rows) if not math.isnan(v)]
                row_out[y_col] = _aggregate(values, method)
        out.append(row_out)
    out.sort(key=lambda r: _x_str(r, x_column))
    return out


def _limit_categories(rows: list[dict], group_col: str) -> tuple[list[dict], list[str]]:
    """limitCategories(): keep the top-10 most frequent categories, 其他 for the rest."""
    if not group_col:
        return rows, []
    counts = Counter(_category_value(r, group_col) for r in rows)
    top = sorted(c for c, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:_MAX_CATEGORIES])
    if len(counts) <= _MAX_CATEGORIES:
        return rows, top
    top_set = set(top)
    remapped = [dict(r, **{group_col: _OTHER}) if _category_value(r, group_col) not in top_set else r for r in rows]
    return remapped, [*top, _OTHER]


def _pivot_for_group_by(
    rows: list[dict],
    x_column: str,
    y_columns: list[str],
    group_col: str,
    categories: list[str],
) -> tuple[list[dict], list[tuple[str, str]]]:
    """pivotForGroupBy(): one row per x value; one series per (y column, category).

    Returns (pivot rows, series keys as (row key, legend label)).
    """
    multi_y = len(y_columns) > 1
    series_keys: list[tuple[str, str]] = []
    for y_col in y_columns:
        for cat in categories:
            label = f"{cat} · {y_col}" if multi_y else cat
            series_keys.append((f"{y_col}||{cat}", label))

    by_x: dict[str, dict[str, Any]] = {}
    for row in rows:
        x_val = _x_str(row, x_column)
        out_row = by_x.setdefault(x_val, {x_column: x_val})
        cat = _category_value(row, group_col)
        for y_col in y_columns:
            out_row[f"{y_col}||{cat}"] = row.get(y_col)
    data = [by_x[x_val] for x_val in sorted(by_x)]
    return data, series_keys


def _prepared_xy(
    data: dict,
    config: dict,
    name: str,
    *,
    categorical_agg: bool,
) -> tuple[str, list[str], list[tuple[str, list[float]]]]:
    """Shared bar/line prep: run the frontend pipeline end to end.

    Returns (x column, x labels, series) with series = [(label, values aligned
    to the x labels, NaN where the frontend would show a gap)]. Categorical
    aggregation applies only to bar (the ``categorical_agg`` flag).
    """
    rows = data["rows"]
    x_column = _require(config, "x_column", name)
    y_columns = _require(config, "y_columns", name)
    if not rows:
        raise RenderError(f"可视化「{name}」没有可渲染的数据行")

    is_time_series = x_column in _date_columns(data)
    processed = _process_time_series_rows(rows, x_column, y_columns, config, is_time_series)
    if not processed:
        raise RenderError(f"可视化「{name}」没有可渲染的数据行")

    group_col = config.get("group_by_column") or ""
    limited, categories = _limit_categories(processed, group_col)
    # Bar X is categorical: aggregate per category (date-x keeps the
    # time-series bucketing path) — same order as the frontend
    if categorical_agg and not is_time_series:
        final_rows = _aggregate_categorical_rows(
            limited, x_column, y_columns, group_col, config.get("aggregation") or "SUM"
        )
    else:
        final_rows = limited

    if group_col and categories:
        pivot_rows, series_keys = _pivot_for_group_by(final_rows, x_column, y_columns, group_col, categories)
        x_labels = [_x_str(r, x_column) for r in pivot_rows]
        series = [(label, [_numeric_cell(r.get(key)) for r in pivot_rows]) for key, label in series_keys]
    else:
        x_labels = [_x_str(r, x_column) for r in final_rows]
        series = [(y, [_numeric_cell(r.get(y)) for r in final_rows]) for y in y_columns]
    if not x_labels:
        raise RenderError(f"可视化「{name}」没有可渲染的数据行")
    return x_column, x_labels, series


# ── Axis formatting, styling & per-chart-type renderers ────────────────────────────


def _trim_number(n: float) -> str:
    """Shortest fixed-decimal label that keeps a tick value exact.

    Six decimals covers every "nice" tick step locators produce
    (1/2/5 × 10^k) and strips float noise (0.30000000000000004 → 0.3).
    """
    s = f"{n:.6f}".rstrip("0").rstrip(".")
    return s or "0"


class _ChineseUnitFormatter(ScalarFormatter):
    """matplotlib's own adaptive tick labels, plus 万/亿 for large values.

    Below 1e4 the label is delegated to :class:`ScalarFormatter`, which
    derives its precision from the tick *spacing* the locator chose for the
    current data range — so a 0.005-scale axis and a 1.005-scale axis both
    stay distinguishable with no hand-picked decimal count. Only the large
    magnitudes, where Chinese business units read better than digits, are
    rescaled.
    """

    def __call__(self, value: float, pos=None) -> str:
        if value != value:  # NaN
            return ""
        abs_v = abs(value)
        if abs_v >= 1e8:
            return f"{_trim_number(value / 1e8)}亿"
        if abs_v >= 1e4:
            return f"{_trim_number(value / 1e4)}万"
        return super().__call__(value, pos)


_QUARTER_KEY = re.compile(r"^\d{4}-Q\d$")
_DATE_ONLY = re.compile(r"^\d{4}(-\d{2})?(-\d{2})?$")


def _format_axis_date(value: str, show_time: bool) -> str:
    """formatAxisDate(): bucket keys pass through; datetimes trim to the date."""
    if not value:
        return value
    if _QUARTER_KEY.match(value) or _DATE_ONLY.match(value):
        return value
    parsed = _parse_date(value)
    if parsed is None:
        return value
    date_part = parsed.strftime("%Y-%m-%d")
    return f"{date_part} {parsed.strftime('%H:%M')}" if show_time else date_part


def _thin_ticks(count: int, max_ticks: int = _MAX_X_TICKS) -> list[int]:
    """Indices of at most ``max_ticks`` labels — first and last always kept."""
    if count <= max_ticks:
        return list(range(count))
    stride = math.ceil((count - 1) / (max_ticks - 1))
    idx = list(range(0, count, stride))
    if idx[-1] != count - 1:
        idx.append(count - 1)
    return idx


def _set_x_ticks(ax, positions: list[float], labels: list[str], *, rotate: bool = True) -> None:
    """Thinned ticks for a *continuous* x axis (line/scatter date slots).

    Only for axes where a label is a position on a continuum — a handful of
    dates reads like a normal line plot, whereas every one of 200 would not.
    Categorical axes use :func:`_set_category_x_ticks` instead.
    """
    if not labels:
        return
    idx = _thin_ticks(len(labels))
    ax.set_xticks([positions[i] for i in idx])
    ax.set_xticklabels(
        [labels[i] for i in idx],
        rotation=30 if rotate else 0,
        ha="right" if rotate else "center",
    )


def _set_category_x_ticks(ax, positions: list[float], labels: list[str]) -> None:
    """Categorical axes keep EVERY label — bars/boxes map 1:1 to categories.

    Hiding categories would leave bars unidentifiable in a static image (no
    hover, no zoom), so crowded axes rotate to vertical and shrink instead.
    """
    if not labels:
        return
    ax.set_xticks(positions)
    if len(labels) > _MAX_ANGLED_LABELS:
        ax.set_xticklabels(labels, rotation=90, ha="center", fontsize=8)
    else:
        ax.set_xticklabels(labels, rotation=30, ha="right")


def _display_x_labels(x_labels: list[str], data: dict, x_column: str, config: dict) -> list[str]:
    """Date x columns get the frontend's axis date format (honors show_time)."""
    if x_column not in _date_columns(data):
        return list(x_labels)
    show_time = bool(config.get("show_time"))
    return [_format_axis_date(label, show_time) for label in x_labels]


def _format_y_axis(ax) -> None:
    """Let matplotlib pick the tick precision; add 万/亿 on top."""
    ax.yaxis.set_major_formatter(_ChineseUnitFormatter())


def _style_axes(ax, *, vertical_grid: bool = False, y_margin: float | None = None) -> None:
    """Light grid, bottom+left frame, no tick marks.

    The left spine stays: without it a series peaking above the top tick
    looks like it escapes the plot. ``y_margin`` adds headroom so dense line
    charts do not hug the top edge.
    """
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(_AXIS_LINE_COLOR)
    ax.grid(True, axis="y", color=_GRID_COLOR, linewidth=0.8, zorder=0)
    if vertical_grid:
        ax.grid(True, axis="x", color=_GRID_COLOR, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    if y_margin is not None:
        ax.margins(y=y_margin)


def _add_legend(ax, *, ncol: int | None = None) -> None:
    """Frameless legend ABOVE the axes — never overlapping the data.

    A legend inside the plot area sits on top of the series it describes,
    which reads as noise in a static image.
    """
    handles, labels = ax.get_legend_handles_labels()
    if not handles:
        return
    ax.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        ncol=ncol or min(len(labels), 5),
        frameon=False,
        fontsize=10,
    )


def _series_color(index: int) -> str:
    return _COLORS[index % len(_COLORS)]


def _apply_labels(ax, config: dict, name: str) -> None:
    """Title and axis captions taken from ``config_json``.

    ``config.title`` wins (the visualization name is the fallback); the
    ``x_label`` / ``y_label`` captions are only drawn when set. The title
    clears the legend when one sits above the axes.
    """
    has_legend = ax.get_legend() is not None
    ax.set_title(config.get("title") or name, pad=32 if has_legend else 12)
    x_label = config.get("x_label") or ""
    y_label = config.get("y_label") or ""
    if x_label:
        ax.set_xlabel(x_label, labelpad=8)
    if y_label:
        ax.set_ylabel(y_label, labelpad=8)


def _render_bar(ax, data: dict, config: dict, name: str) -> None:
    x_column, x_labels, series = _prepared_xy(data, config, name, categorical_agg=True)
    group_col = config.get("group_by_column") or ""
    stack = bool(config.get("stack_bars")) and bool(group_col)
    if stack:
        bottoms = [0.0] * len(x_labels)
        for i, (label, values) in enumerate(series):
            heights = [0.0 if math.isnan(v) else v for v in values]
            ax.bar(
                range(len(x_labels)),
                heights,
                bottom=bottoms,
                width=0.8,
                color=_series_color(i),
                label=label,
                zorder=3,
            )
            bottoms = [b + h for b, h in zip(bottoms, heights, strict=True)]
        positions = [float(i) for i in range(len(x_labels))]
    else:
        width = 0.8 / len(series)
        for i, (label, values) in enumerate(series):
            offsets = [xi + i * width for xi in range(len(x_labels))]
            ax.bar(offsets, values, width=width, color=_series_color(i), label=label, zorder=3)
        if len(series) > 1:
            positions = [xi + width * (len(series) - 1) / 2 for xi in range(len(x_labels))]
        else:
            positions = [float(xi) for xi in range(len(x_labels))]
    _set_category_x_ticks(ax, positions, _display_x_labels(x_labels, data, x_column, config))
    _format_y_axis(ax)
    _style_axes(ax)
    _add_legend(ax)


def _render_line(ax, data: dict, config: dict, name: str) -> None:
    x_column, x_labels, series = _prepared_xy(data, config, name, categorical_agg=False)
    positions = list(range(len(x_labels)))
    # Dense series keep the line but drop per-point symbols — markers on every
    # one of hundreds of points turn a trend into noise
    show_dots = len(x_labels) <= _LINE_DOT_MAX_POINTS
    for i, (label, values) in enumerate(series):
        ax.plot(
            positions,
            values,
            color=_series_color(i),
            linewidth=1.8,
            marker="o" if show_dots else None,
            markersize=4 if show_dots else 0,
            label=label,
            zorder=3,
        )
    _set_x_ticks(ax, [float(p) for p in positions], _display_x_labels(x_labels, data, x_column, config))
    _format_y_axis(ax)
    # Headroom so peaks do not hug the top edge of the frame
    _style_axes(ax, y_margin=0.08)
    _add_legend(ax)


def _sample_points(xs: list[float], ys: list[float]) -> tuple[list[float], list[float]]:
    """Deterministic stride sampling to MAX_SCATTER_POINTS (frontend parity)."""
    if len(xs) <= _MAX_SCATTER_POINTS:
        return xs, ys
    stride = len(xs) / _MAX_SCATTER_POINTS
    out_x: list[float] = []
    out_y: list[float] = []
    i = 0
    while len(out_x) < _MAX_SCATTER_POINTS:
        idx = math.floor(i * stride)
        out_x.append(xs[idx])
        out_y.append(ys[idx])
        i += 1
    return out_x, out_y


def _render_scatter(ax, data: dict, config: dict, name: str) -> None:
    x_column = _require(config, "x_column", name)
    y_columns = _require(config, "y_columns", name)
    rows = data["rows"]
    if not rows:
        raise RenderError(f"可视化「{name}」没有可渲染的数据行")

    is_time_series = x_column in _date_columns(data)
    processed = _process_time_series_rows(rows, x_column, y_columns, config, is_time_series)
    if not processed:
        raise RenderError(f"可视化「{name}」没有可渲染的数据行")
    group_col = config.get("group_by_column") or ""
    limited, categories = _limit_categories(processed, group_col)

    # xIsNumeric parity: numbers keep a numeric axis; everything else (dates,
    # text categories) becomes evenly spaced slots in first-appearance order
    sample = limited[:20]
    x_is_numeric = bool(sample) and all(not math.isnan(_numeric_cell(r.get(x_column))) for r in sample)

    x_order: list[str] = []
    if is_time_series:
        x_order = sorted({_x_str(r, x_column) for r in limited})
    elif not x_is_numeric:
        for row in limited:
            key = _x_str(row, x_column)
            if key not in x_order:
                x_order.append(key)

    if x_order:
        x_index = {v: float(i) for i, v in enumerate(x_order)}

        def to_x(row: dict) -> float:
            return x_index.get(_x_str(row, x_column), math.nan)

    else:

        def to_x(row: dict) -> float:
            return _numeric_cell(row.get(x_column))

    if group_col and categories:
        combos = [(y, cat) for y in y_columns for cat in categories]
    else:
        combos = [(y, "") for y in y_columns]

    plotted = False
    y_color_idx: dict[str, int] = {}
    cat_marker_idx: dict[str, int] = {}
    for y_col, cat in combos:
        # Color encodes the Y variable, marker shape the category — UI parity
        if y_col not in y_color_idx:
            y_color_idx[y_col] = len(y_color_idx)
        if cat and cat not in cat_marker_idx:
            cat_marker_idx[cat] = len(cat_marker_idx)
        if group_col:
            label = f"{cat} · {y_col}" if len(y_columns) > 1 else cat
        else:
            label = y_col
        xs: list[float] = []
        ys: list[float] = []
        for row in limited:
            if cat and _category_value(row, group_col) != cat:
                continue
            xv = to_x(row)
            yv = _numeric_cell(row.get(y_col))
            if math.isnan(xv) or math.isnan(yv):
                continue
            xs.append(xv)
            ys.append(yv)
        if not xs:
            continue
        xs, ys = _sample_points(xs, ys)
        ax.scatter(
            xs,
            ys,
            s=18,
            alpha=0.7,
            color=_series_color(y_color_idx[y_col]),
            marker=_MARKERS[cat_marker_idx.get(cat, 0) % len(_MARKERS)],
            label=label,
            zorder=3,
        )
        plotted = True
    if not plotted:
        raise RenderError(f"可视化「{name}」没有可渲染的数据行")

    if x_order:
        labels = _display_x_labels(x_order, data, x_column, config) if is_time_series else x_order
        _set_x_ticks(ax, [float(i) for i in range(len(x_order))], labels)
    _format_y_axis(ax)
    _style_axes(ax, vertical_grid=True, y_margin=0.08)
    _add_legend(ax)


def _pie_slices(data: dict, config: dict, name: str) -> list[tuple[str, float]]:
    """Pie data pipeline: group by label, aggregate, top-8 slices + 其他."""
    label_column = _require(config, "label_column", name)
    value_column = _require(config, "value_column", name)
    aggregation = config.get("aggregation") or "SUM"
    rows = data["rows"]
    if not rows:
        raise RenderError(f"可视化「{name}」没有可渲染的数据行")

    grouped: dict[str, list[Any]] = {}
    for row in rows:
        label = _category_value(row, label_column)
        grouped.setdefault(label, []).append(row.get(value_column))

    aggregated: list[tuple[str, float]] = []
    for label, raws in grouped.items():
        if aggregation == "COUNT":
            value = float(len(raws))
        else:
            # Number(raw) || 0 — non-numeric cells count as 0, matching the UI
            values = [v for v in (_js_number(raw) for raw in raws) if not math.isnan(v)]
            value = _aggregate(values, aggregation)
        aggregated.append((label, value))

    # Slices sorted descending — largest first, matching UI convention
    aggregated.sort(key=lambda pair: -pair[1])
    if len(aggregated) > _PIE_MAX_SLICES:
        rest = sum(v for _, v in aggregated[_PIE_MAX_SLICES:])
        aggregated = aggregated[:_PIE_MAX_SLICES] + [(_OTHER, rest)]
    return aggregated


def _render_pie(ax, data: dict, config: dict, name: str) -> None:
    slices = _pie_slices(data, config, name)
    total = sum(v for _, v in slices)
    if total <= 0:
        raise RenderError(f"可视化「{name}」的数值列全为 0，无法渲染饼图")
    values = [v for _, v in slices]
    # On-wedge text shows the share only; slice names live in the legend —
    # exactly how the in-app pie reads (tiny slices get no wedge label)
    wedges, _texts, _autotexts = ax.pie(
        values,
        colors=[_series_color(i) for i in range(len(values))],
        autopct=lambda pct: f"{pct:.1f}%" if pct >= _PIE_MIN_LABEL_PERCENT else "",
        pctdistance=0.75,
        startangle=90,
        counterclock=False,
        wedgeprops={"edgecolor": "white", "linewidth": 1},
        textprops={"fontsize": 10},
    )
    ax.axis("equal")
    ax.legend(
        wedges,
        [label for label, _ in slices],
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        frameon=False,
        fontsize=10,
    )


def _render_histogram(ax, data: dict, config: dict, name: str) -> None:
    columns = _require(config, "columns", name)
    bins = int(_require(config, "bins", name))
    rows = data["rows"]

    # Shared bins across all columns (buildHistogramData parity)
    per_column: dict[str, list[float]] = {}
    lo, hi = math.inf, -math.inf
    for col in columns:
        values = []
        for row in rows:
            raw = row.get(col)
            if raw is None:
                continue
            v = _js_number(raw)
            if math.isnan(v):
                continue
            values.append(v)
            lo = min(lo, v)
            hi = max(hi, v)
        per_column[col] = values
    if not math.isfinite(lo):
        raise RenderError(f"可视化「{name}」的数值列没有可统计的数据")
    # Degenerate case: all values identical — single-width bin around it
    if lo == hi:
        lo -= 0.5
        hi += 0.5

    width = (hi - lo) / bins
    counts = {col: [0] * bins for col in columns}
    for col, values in per_column.items():
        for v in values:
            idx = int((v - lo) / width)
            if idx >= bins:
                idx = bins - 1  # include the max value in the last bin
            counts[col][idx] += 1

    n = len(columns)
    centers = [lo + (i + 0.5) * width for i in range(bins)]
    multi = n > 1
    for i, col in enumerate(columns):
        # Overlapping full-width bins for multi-column histograms — the UI
        # expands each series back to the whole bin at 50% opacity
        ax.bar(
            centers,
            counts[col],
            width=width,
            color=_series_color(i),
            alpha=0.5 if multi else 0.85,
            edgecolor=_series_color(i) if multi else "none",
            linewidth=1 if multi else 0,
            label=col,
            zorder=3,
        )
    # Bin positions are a numeric continuum — let matplotlib choose the ticks
    # and format them (万/亿 included), instead of labelling every bin edge
    ax.set_xlim(lo, hi)
    ax.xaxis.set_major_formatter(_ChineseUnitFormatter())
    _format_y_axis(ax)
    _style_axes(ax)
    _add_legend(ax)


def _render_boxplot(ax, data: dict, config: dict, name: str) -> None:
    value_column = _require(config, "value_column", name)
    category_column = config.get("category_column") or ""
    rows = data["rows"]

    grouped: dict[str, list[float]] = {}
    for row in rows:
        raw = row.get(value_column)
        if raw is None:
            continue
        v = _js_number(raw)
        if math.isnan(v):
            continue
        cat = _category_value(row, category_column) if category_column else "全部"
        grouped.setdefault(cat, []).append(v)
    # Keep the top-10 categories by frequency for readability
    if category_column and len(grouped) > _MAX_CATEGORIES:
        kept = {c for c, _ in sorted(grouped.items(), key=lambda kv: -len(kv[1]))[:_MAX_CATEGORIES]}
        grouped = {c: vals for c, vals in grouped.items() if c in kept}
    order = sorted(grouped)
    if not order:
        raise RenderError(f"可视化「{name}」没有可渲染的数据行")
    bp = ax.boxplot(
        [grouped[c] for c in order],
        widths=0.6,
        patch_artist=True,
        medianprops={"linewidth": 2.5},
        whiskerprops={"linewidth": 1.5},
        capprops={"linewidth": 1.5},
        flierprops={"marker": "o", "markersize": 5, "markerfacecolor": "none", "linewidth": 1.5},
        zorder=3,
    )
    # One color per category, boxes at 25% fill — the UI's BoxplotShape look
    for i, box in enumerate(bp["boxes"]):
        color = _series_color(i)
        box.set(facecolor=color, edgecolor=color, alpha=0.25, linewidth=1.5)
        bp["medians"][i].set_color(color)
        bp["fliers"][i].set(markeredgecolor=color)
        for whisker in bp["whiskers"][2 * i : 2 * i + 2]:
            whisker.set_color(color)
        for cap in bp["caps"][2 * i : 2 * i + 2]:
            cap.set_color(color)
    _set_category_x_ticks(ax, [float(i + 1) for i in range(len(order))], order)
    _format_y_axis(ax)
    _style_axes(ax, y_margin=0.08)


def _format_kpi_value(value: float) -> str:
    """KPI tile value: thousands separators, adaptive precision for small scales.

    A fixed 2-decimal format rendered rates like 0.0042 as "0.00" — below 1.0
    the value keeps two significant digits instead.
    """
    if abs(value - round(value)) <= 1e-9:
        return f"{int(round(value)):,}"
    if abs(value) >= 1:
        return f"{value:,.2f}"
    return f"{float(f'{value:.2g}'):g}"


def _render_kpi_card(fig, data: dict, config: dict, name: str) -> None:
    value_column = _require(config, "value_column", name)
    label = config.get("label") or "指标"
    aggregation = (config.get("aggregation") or "SUM").upper()

    values = _numeric(data["rows"], value_column)
    if not values:
        raise RenderError(f"可视化「{name}」的数值列 '{value_column}' 没有可统计数据")
    if aggregation == "AVG":
        value = sum(values) / len(values)
    elif aggregation == "COUNT":
        value = float(len(values))
    elif aggregation == "MIN":
        value = min(values)
    elif aggregation == "MAX":
        value = max(values)
    else:  # SUM (default, matches the UI)
        value = sum(values)

    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.text(0.5, 0.62, str(label), ha="center", va="center", fontsize=20, color="#555555")
    ax.text(
        0.5,
        0.40,
        _format_kpi_value(value),
        ha="center",
        va="center",
        fontsize=44,
        fontweight="bold",
    )


_RENDERERS = {
    "bar": _render_bar,
    "line": _render_line,
    "pie": _render_pie,
    "scatter": _render_scatter,
    "histogram": _render_histogram,
    "boxplot": _render_boxplot,
}


def render_chart(name: str, data: dict, output_path: Path) -> None:
    """Render one visualization data payload to ``output_path`` as PNG.

    ``data`` is the ``/api/visualizations/{id}/data`` response:
    columns, rows, column_types, chart_type, config_json. Raises
    :class:`RenderError` for unsupported types or unusable configs.
    """
    chart_type = data.get("chart_type")
    config = data.get("config_json") or {}

    if chart_type == "table":
        raise RenderError("表格类可视化不支持图片渲染，应使用 CSV 导出")
    if chart_type == "kpi_card":
        fig = plt.figure(figsize=_FIGSIZE, dpi=_DPI)
        try:
            _render_kpi_card(fig, data, config, name)
            fig.savefig(output_path, format="png")
        finally:
            plt.close(fig)
        return

    renderer = _RENDERERS.get(chart_type)
    if renderer is None:
        raise RenderError(f"不支持的图表类型: {chart_type}")

    fig, ax = plt.subplots(figsize=_FIGSIZE, dpi=_DPI)
    try:
        renderer(ax, data, config, name)
        _apply_labels(ax, config, name)
        # bbox_inches="tight" keeps outside legends (pie) from being clipped
        fig.savefig(output_path, format="png", bbox_inches="tight", facecolor="white")
    finally:
        plt.close(fig)
