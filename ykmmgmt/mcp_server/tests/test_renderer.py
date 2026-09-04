"""Tests for the matplotlib chart renderer (all chart types, PNG output)."""

import math
from pathlib import Path

import pytest
from mcp_server.renderer import (
    RenderError,
    _aggregate,
    _apply_labels,
    _format_axis_date,
    _format_kpi_value,
    _format_y_axis,
    _limit_categories,
    _pie_slices,
    _prepared_xy,
    _set_category_x_ticks,
    _set_x_ticks,
    _thin_ticks,
    _trim_number,
    _truncate_date,
    render_chart,
)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _assert_png(path: Path) -> None:
    """The file exists, is non-empty, and carries a PNG signature."""
    assert path.exists(), f"{path} was not created"
    content = path.read_bytes()
    assert len(content) > 100, "PNG file is suspiciously small"
    assert content.startswith(PNG_SIGNATURE), "file does not start with a PNG signature"


def _data(chart_type: str, config: dict, rows: list[dict], columns: list[str] | None = None) -> dict:
    """Build a /data-endpoint-shaped payload."""
    if columns is None:
        columns = list(rows[0].keys()) if rows else []
    return {
        "columns": columns,
        "rows": rows,
        "column_types": {},
        "chart_type": chart_type,
        "config_json": config,
    }


ROWS = [
    {"月份": "2026-06", "金额": 100.5, "数量": 3},
    {"月份": "2026-07", "金额": 250.25, "数量": 5},
    {"月份": "2026-08", "金额": 75.0, "数量": 2},
]


@pytest.mark.parametrize(
    "chart_type,config",
    [
        ("bar", {"x_column": "月份", "y_columns": ["金额", "数量"]}),
        ("bar", {"x_column": "月份", "y_columns": ["金额"]}),
        ("line", {"x_column": "月份", "y_columns": ["金额", "数量"]}),
        ("pie", {"label_column": "月份", "value_column": "金额"}),
        ("scatter", {"x_column": "数量", "y_columns": ["金额"]}),
        ("histogram", {"columns": ["金额"], "bins": 10}),
        ("boxplot", {"category_column": "月份", "value_column": "金额"}),
        ("boxplot", {"category_column": "", "value_column": "金额"}),
        ("kpi_card", {"value_column": "金额", "label": "总金额"}),
        ("kpi_card", {"value_column": "金额", "label": "平均值", "aggregation": "AVG"}),
    ],
)
def test_each_chart_type_renders_png(tmp_path, chart_type, config):
    path = tmp_path / "chart.png"
    render_chart("测试图表", _data(chart_type, config, ROWS), path)
    _assert_png(path)


def test_line_sorts_time_axis_by_date(tmp_path):
    """Line charts with date x columns render rows in chronological order."""
    rows = [
        {"日期": "2026-08-01", "金额": 3.0},
        {"日期": "2026-06-01", "金额": 1.0},
        {"日期": "2026-07-01", "金额": 2.0},
    ]
    path = tmp_path / "line.png"
    render_chart("时间排序", _data("line", {"x_column": "日期", "y_columns": ["金额"]}, rows), path)
    _assert_png(path)


def test_chinese_title_and_labels_render(tmp_path):
    """Chinese text (title, axis labels, categories) renders without raising."""
    path = tmp_path / "中文.png"
    render_chart(
        "中文标题测试",
        _data(
            "bar",
            {"x_column": "部门", "y_columns": ["销售额"]},
            [
                {"部门": "华东大区", "销售额": 1200.0},
                {"部门": "华南大区", "销售额": 980.5},
            ],
        ),
        path,
    )
    _assert_png(path)


def test_pie_honors_label_and_value_columns(tmp_path):
    """Pie renders label_column/value_column — not the first two columns."""
    rows = [
        {"月份": "2026-06", "销售额": 100.0, "数量": 9},
        {"月份": "2026-07", "销售额": 200.0, "数量": 1},
    ]
    path = tmp_path / "pie.png"
    render_chart("饼图", _data("pie", {"label_column": "月份", "value_column": "销售额"}, rows), path)
    _assert_png(path)


SPARSE_ROWS = [
    # Real-world failure: 收益率 had unusable cells in 5 of 230 rows —
    # bar/line must render with gaps, not fail on a length mismatch
    {"月份": "2026-01", "收益率": "0.05"},
    {"月份": "2026-02", "收益率": None},
    {"月份": "2026-03", "收益率": "n/a"},
    {"月份": "2026-04", "收益率": 0.08},
]


@pytest.mark.parametrize("chart_type", ["bar", "line"])
def test_sparse_numeric_column_renders_with_gaps(tmp_path, chart_type):
    """Non-numeric/missing cells become gaps — no length-mismatch error."""
    config = {"x_column": "月份", "y_columns": ["收益率"]}
    path = tmp_path / f"{chart_type}.png"
    render_chart("稀疏数据", _data(chart_type, config, SPARSE_ROWS), path)
    _assert_png(path)


def test_pie_accepts_numeric_string_values(tmp_path):
    """Real-world failure: text-typed value columns return numbers as strings —
    the pie must coerce them, not filter every row out."""
    rows = [
        {"渠道": "线上", "占比": "0.60"},
        {"渠道": "线下", "占比": "0.40"},
    ]
    path = tmp_path / "pie.png"
    render_chart("渠道占比", _data("pie", {"label_column": "渠道", "value_column": "占比"}, rows), path)
    _assert_png(path)


def test_pie_skips_only_unusable_rows(tmp_path):
    """A single bad row is dropped; the rest still renders."""
    rows = [
        {"渠道": "线上", "占比": "0.60"},
        {"渠道": "未知", "占比": None},
    ]
    path = tmp_path / "pie.png"
    render_chart("部分数据", _data("pie", {"label_column": "渠道", "value_column": "占比"}, rows), path)
    _assert_png(path)


# ── Aggregation pipeline parity with the frontend ──────────────────────────


def test_aggregate_values_methods():
    """aggregateValues(): SUM/AVG/COUNT/MIN/MAX with frontend defaults."""
    values = [1.0, 2.0, 6.0]
    assert _aggregate(values, "SUM") == 9.0
    assert _aggregate(values, "AVG") == 3.0
    assert _aggregate(values, "COUNT") == 3.0
    assert _aggregate(values, "MIN") == 1.0
    assert _aggregate(values, "MAX") == 6.0
    assert _aggregate([], "SUM") == 0.0
    assert _aggregate(values, "anything") == 9.0  # default SUM


def test_truncate_date_granularities():
    assert _truncate_date("2026-03-15T10:30:00", "month") == "2026-03"
    assert _truncate_date("2026-03-15", "quarter") == "2026-Q1"
    assert _truncate_date("2026-03-15", "year") == "2026"
    assert _truncate_date("2026-03-18", "week") == "2026-03-16"  # Monday
    assert _truncate_date("2026-03-15T10:30", "day") == "2026-03-15"
    # Reduced-precision ISO strings parse like JS new Date()
    assert _truncate_date("2026-03", "quarter") == "2026-Q1"
    # Unparseable values pass through as their own bucket
    assert _truncate_date("n/a", "month") == "n/a"


def test_bar_categorical_x_aggregates_per_category(tmp_path):
    """Bar with categorical x sums y values per category (frontend parity)."""
    rows = [
        {"部门": "华东", "销售额": 100.0},
        {"部门": "华东", "销售额": 50.0},
        {"部门": "华南", "销售额": 30.0},
        {"部门": "华南", "销售额": None},  # Number(null) → 0, matching the UI
    ]
    payload = _data("bar", {"x_column": "部门", "y_columns": ["销售额"]}, rows)
    _, x_labels, series = _prepared_xy(payload, payload["config_json"], "t", categorical_agg=True)
    assert x_labels == ["华东", "华南"]
    assert series == [("销售额", [150.0, 30.0])]
    path = tmp_path / "bar.png"
    render_chart("分类聚合", payload, path)
    _assert_png(path)


def test_line_time_series_buckets_by_granularity(tmp_path):
    """Date-x line buckets by time_granularity and applies time_aggregation."""
    rows = [
        {"日期": "2026-06-05", "金额": 10.0},
        {"日期": "2026-06-20", "金额": 15.0},
        {"日期": "2026-07-01", "金额": 7.0},
    ]
    config = {"x_column": "日期", "y_columns": ["金额"], "time_granularity": "month", "time_aggregation": "SUM"}
    payload = _data("line", config, rows)
    _, x_labels, series = _prepared_xy(payload, config, "t", categorical_agg=False)
    assert x_labels == ["2026-06", "2026-07"]
    assert series == [("金额", [25.0, 7.0])]


def test_bar_group_by_pivots_into_category_series(tmp_path):
    """group_by_column splits into one series per category with pivoted values."""
    rows = [
        {"月份": "2026-06", "区域": "华东", "金额": 10.0},
        {"月份": "2026-06", "区域": "华南", "金额": 20.0},
        {"月份": "2026-07", "区域": "华东", "金额": 30.0},
    ]
    config = {"x_column": "月份", "y_columns": ["金额"], "group_by_column": "区域"}
    payload = _data("bar", config, rows)
    _, x_labels, series = _prepared_xy(payload, config, "t", categorical_agg=True)
    assert x_labels == ["2026-06", "2026-07"]
    assert dict(series)["华东"] == [10.0, 30.0]
    huanan = dict(series)["华南"]
    assert huanan[0] == 20.0 and math.isnan(huanan[1])  # missing bucket → gap


def test_limit_categories_merges_tail_into_other():
    """Beyond top-10 categories, the rest remap to 其他 (frontend parity)."""
    rows = [{"品类": f"品类{i}", "v": 1} for i in range(12)]
    remapped, categories = _limit_categories(rows, "品类")
    assert categories[-1] == "其他"
    assert len(categories) == 11
    assert sum(1 for r in remapped if r["品类"] == "其他") == 2


def test_pie_slices_aggregate_and_cap_at_top_n():
    """Pie groups raw rows per label and merges slices beyond top-8."""
    rows = [{"渠道": f"渠道{i}", "占比": float(i + 1)} for i in range(10)]
    payload = _data("pie", {"label_column": "渠道", "value_column": "占比"}, rows)
    slices = _pie_slices(payload, payload["config_json"], "t")
    assert len(slices) == 9  # 8 top slices + 其他
    assert slices[0] == ("渠道9", 10.0)  # largest first
    assert slices[-1][0] == "其他"
    assert slices[-1][1] == 1.0 + 2.0  # smallest two merged


def test_pie_count_aggregation_counts_rows():
    """Pie COUNT counts rows per label regardless of the value."""
    rows = [
        {"渠道": "线上", "占比": 1.0},
        {"渠道": "线上", "占比": 2.0},
        {"渠道": "线下", "占比": 100.0},
    ]
    payload = _data("pie", {"label_column": "渠道", "value_column": "占比", "aggregation": "COUNT"}, rows)
    slices = dict(_pie_slices(payload, payload["config_json"], "t"))
    assert slices == {"线上": 2.0, "线下": 1.0}


def test_missing_config_key_raises(tmp_path):
    with pytest.raises(RenderError, match="x_column"):
        render_chart("缺配置", _data("bar", {"y_columns": ["金额"]}, ROWS), tmp_path / "x.png")


def test_empty_rows_raise(tmp_path):
    with pytest.raises(RenderError, match="没有可渲染的数据行"):
        render_chart(
            "空数据",
            _data("bar", {"x_column": "月份", "y_columns": ["金额"]}, []),
            tmp_path / "x.png",
        )


def test_table_rejected(tmp_path):
    with pytest.raises(RenderError, match="CSV"):
        render_chart(
            "表格",
            _data("table", {"visible_columns": ["月份"]}, ROWS),
            tmp_path / "x.png",
        )


def test_unknown_chart_type_raises(tmp_path):
    with pytest.raises(RenderError, match="不支持"):
        render_chart("未知类型", _data("area", {"x": "a"}, ROWS), tmp_path / "x.png")


def test_figures_closed_after_render(tmp_path):
    """Each render closes its figure — no leakage across many charts."""
    import matplotlib.pyplot as plt

    for i in range(5):
        render_chart(
            f"图表{i}",
            _data("bar", {"x_column": "月份", "y_columns": ["金额"]}, ROWS),
            tmp_path / f"chart_{i}.png",
        )
    assert plt.get_fignums() == [], "figures leaked after rendering"


def test_repeated_renders_are_deterministic(tmp_path):
    """Same input → byte-identical PNG (deterministic server-side rendering)."""
    payload = _data("bar", {"x_column": "月份", "y_columns": ["金额"]}, ROWS)
    first, second = tmp_path / "a.png", tmp_path / "b.png"
    render_chart("确定性", payload, first)
    render_chart("确定性", payload, second)
    assert first.read_bytes() == second.read_bytes()


# ── Axis tick formatting (matplotlib-native + 万/亿 units) ────────────────


def _y_tick_labels(ys: list[float]) -> list[str]:
    """Tick labels matplotlib produces for a series spanning ``ys``."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    try:
        ax.plot(range(len(ys)), ys)
        _format_y_axis(ax)
        fig.canvas.draw()
        return [t.get_text() for t in ax.get_yticklabels()]
    finally:
        plt.close(fig)


def test_trim_number_keeps_tick_values_exact():
    assert _trim_number(1.2) == "1.2"
    assert _trim_number(12) == "12"
    assert _trim_number(1.234567) == "1.234567"
    assert _trim_number(0.30000000000000004) == "0.3"  # float noise stripped


def test_y_ticks_use_chinese_units_for_large_values():
    labels = _y_tick_labels([12000.0, 14000.0, 16000.0])
    assert any("万" in label for label in labels)
    assert all("0000" not in label for label in labels)


def test_y_ticks_stay_distinguishable_on_small_scales():
    """Regression: a hardcoded 2-decimal format flattened these to 0.00/0.01."""
    labels = _y_tick_labels([0.0, 0.005, 0.02])
    assert len(set(labels)) == len(labels), f"collapsed ticks: {labels}"


def test_y_ticks_stay_distinguishable_above_one():
    """Values above 1 that sit close together stay distinct (1.005 vs 1.01).

    Precision comes from the tick spacing matplotlib chose for the range —
    not from a magnitude rule — so it holds on either side of 1.0.
    """
    labels = _y_tick_labels([1.0, 1.005, 1.02])
    assert len(set(labels)) == len(labels), f"collapsed ticks: {labels}"


def test_format_axis_date_matches_frontend():
    """formatAxisDate(): bucket keys pass through, datetimes trim to the date."""
    assert _format_axis_date("2026-Q1", False) == "2026-Q1"
    assert _format_axis_date("2026-06", False) == "2026-06"
    assert _format_axis_date("2026-06-05", False) == "2026-06-05"
    assert _format_axis_date("2026-06-05T10:30:00", False) == "2026-06-05"
    assert _format_axis_date("2026-06-05T10:30:00", True) == "2026-06-05 10:30"
    assert _format_axis_date("not-a-date", False) == "not-a-date"
    assert _format_axis_date("", False) == ""


# ── X-axis tick thinning ──────────────────────────────────────────────


def test_thin_ticks_caps_labels_and_keeps_ends():
    assert _thin_ticks(5) == [0, 1, 2, 3, 4]
    idx = _thin_ticks(30)
    assert len(idx) <= 8
    assert idx[0] == 0 and idx[-1] == 29
    assert idx == sorted(set(idx))


def test_set_x_ticks_thins_long_date_axes():
    """A 60-point date axis shows a handful of ticks, not all 60 labels."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    try:
        labels = [f"2026-01-{d:02d}" for d in range(1, 31)] * 2
        _set_x_ticks(ax, [float(i) for i in range(len(labels))], labels)
        assert len(ax.get_xticks()) <= 8
        shown = [t.get_text() for t in ax.get_xticklabels()]
        assert shown[0] == labels[0]
        assert shown[-1] == labels[-1]
    finally:
        plt.close(fig)


def test_category_axis_keeps_every_label():
    """Bars map 1:1 to categories, so no category label may be dropped."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    try:
        labels = [f"类别{i}" for i in range(20)]
        _set_category_x_ticks(ax, [float(i) for i in range(20)], labels)
        assert [t.get_text() for t in ax.get_xticklabels()] == labels
        # Crowded axes rotate vertical instead of hiding labels
        assert ax.get_xticklabels()[0].get_rotation() == 90
    finally:
        plt.close(fig)


def test_category_axis_uses_angled_labels_when_sparse():
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    try:
        labels = ["华东", "华南", "华北"]
        _set_category_x_ticks(ax, [0.0, 1.0, 2.0], labels)
        tick_labels = ax.get_xticklabels()
        assert [t.get_text() for t in tick_labels] == labels
        assert tick_labels[0].get_rotation() == 30
    finally:
        plt.close(fig)


def test_long_date_line_chart_renders(tmp_path):
    """A dense daily series renders without crowding every date onto the axis."""
    rows = [{"日期": f"2026-{m:02d}-{d:02d}", "金额": float(m * d % 7)} for m in (1, 2) for d in range(1, 29)]
    path = tmp_path / "line.png"
    render_chart(
        "密集日期",
        _data("line", {"x_column": "日期", "y_columns": ["金额"]}, rows),
        path,
    )
    _assert_png(path)


# ── Titles & axis captions from config ────────────────────────────────


def test_apply_labels_uses_config_captions():
    """x_label/y_label/title come from config_json, like the in-app captions."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    try:
        _apply_labels(ax, {"title": "月度趋势", "x_label": "月份", "y_label": "金额（元）"}, "图表名")
        assert ax.get_title() == "月度趋势"
        assert ax.get_xlabel() == "月份"
        assert ax.get_ylabel() == "金额（元）"
    finally:
        plt.close(fig)


def test_apply_labels_falls_back_to_name_and_no_captions():
    """Without config captions the title is the visualization name; axes stay bare."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    try:
        _apply_labels(ax, {}, "销售额对比")
        assert ax.get_title() == "销售额对比"
        assert ax.get_xlabel() == ""
        assert ax.get_ylabel() == ""
    finally:
        plt.close(fig)


def test_small_scale_bar_chart_renders(tmp_path):
    """Sub-1.0 values (e.g. 收益率) render with distinguishable Y ticks."""
    rows = [{"月份": f"2026-0{i}", "收益率": 0.005 * i} for i in range(1, 6)]
    path = tmp_path / "small.png"
    render_chart("小数值", _data("bar", {"x_column": "月份", "y_columns": ["收益率"]}, rows), path)
    _assert_png(path)


def test_format_kpi_value_keeps_small_values_readable():
    """KPI values: thousands separators, but rates keep significant digits."""
    assert _format_kpi_value(1234) == "1,234"
    assert _format_kpi_value(1234567.5) == "1,234,567.50"
    assert _format_kpi_value(12.5) == "12.50"
    assert _format_kpi_value(0.0042) == "0.0042"  # was "0.00"
    assert _format_kpi_value(0.1) == "0.1"
    assert _format_kpi_value(0) == "0"
