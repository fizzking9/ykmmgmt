"""Tests for the import endpoint and related services."""

import pandas as pd

# Import main to register models for schema validation tests
import main  # noqa: F401
from app.services.cleaning import (
    CleaningPipeline,
    CleaningReport,
    CleaningStepReport,
    deduplicate_rows,
    handle_missing_values,
    normalize_formats,
    strip_whitespace,
    validate_values,
)
from app.services.import_service import ImportError
from app.services.parsers import detect_encoding, parse_file
from app.services.schema_validator import (
    get_registered_tables,
    resolve_target_table,
)


class TestCleaningPipeline:
    """Unit tests for individual cleaning steps."""

    def test_strip_whitespace_removes_leading_trailing(self):
        df = pd.DataFrame({"col1": ["  hello  ", " world", "test\t"]})
        report = CleaningReport(rows_before=len(df))
        result, report = strip_whitespace(df, report)
        assert result.iloc[0, 0] == "hello"
        assert result.iloc[1, 0] == "world"
        assert result.iloc[2, 0] == "test"

    def test_handle_missing_values_drops_blank_rows(self):
        df = pd.DataFrame(
            {
                "a": ["keep", None, None],
                "b": [1.0, None, None],
            }
        )
        report = CleaningReport(rows_before=len(df))
        result, report = handle_missing_values(df, report)
        assert len(result) == 1
        assert result.iloc[0, 0] == "keep"

    def test_handle_missing_values_drops_empty_columns(self):
        df = pd.DataFrame(
            {
                "a": ["val1", "val2"],
                "b": [None, None],
            }
        )
        report = CleaningReport(rows_before=len(df))
        result, report = handle_missing_values(df, report)
        assert len(result.columns) == 1
        assert result.columns[0] == "a"

    def test_deduplicate_rows_removes_exact_duplicates(self):
        df = pd.DataFrame(
            {
                "x": [1, 2, 1, 2],
                "y": ["a", "b", "a", "b"],
            }
        )
        report = CleaningReport(rows_before=len(df))
        result, report = deduplicate_rows(df, report)
        assert len(result) == 2
        assert "duplicate rows removed" in report.steps[0].warnings[0]

    def test_normalize_formats_detects_dates(self):
        df = pd.DataFrame(
            {
                "date_col": ["2026-07-28 15:43:08", "2026-01-01"],
            }
        )
        report = CleaningReport(rows_before=len(df))
        result, report = normalize_formats(df, report)
        # Date column should still exist (conversion happens in-place)
        assert len(result) == 2

    def test_validate_values_step_runs(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        report = CleaningReport(rows_before=len(df))
        result, report = validate_values(df, report)
        assert len(result) == 3
        assert len(report.steps) == 1
        assert report.steps[0].step_name == "validate_values"

    def test_pipeline_runs_all_steps_in_order(self):
        df = pd.DataFrame(
            {
                "col": ["  a  ", "  b  ", None],
            }
        )
        pipeline = CleaningPipeline()
        result, report = pipeline.run(df)
        step_names = [s.step_name for s in report.steps]
        assert "strip_whitespace" in step_names
        assert "handle_missing_values" in step_names
        assert "normalize_formats" in step_names
        assert "deduplicate_rows" in step_names
        assert "validate_values" in step_names

    def test_pipeline_clears_common_steps(self):
        pipeline = CleaningPipeline()
        pipeline.clear_common_steps()
        df = pd.DataFrame({"col": ["a", "b"]})
        result, report = pipeline.run(df)
        assert len(report.steps) == 0

    def test_pipeline_report_to_dict(self):
        report = CleaningReport(rows_before=10, rows_after=8)
        report.add_step(
            CleaningStepReport(
                step_name="test_step",
                rows_before=10,
                rows_after=8,
                rows_dropped=2,
                rows_modified=1,
                warnings=["test warning"],
            )
        )
        d = report.to_dict()
        assert d["rows_before"] == 10
        assert d["rows_after"] == 8
        assert len(d["steps"]) == 1
        assert d["steps"][0]["step"] == "test_step"


class TestParsers:
    """Tests for CSV and Excel parsers."""

    def test_detect_encoding_utf8(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("col1,col2\nval1,val2\n", encoding="utf-8")
        enc = detect_encoding(str(csv_file))
        assert enc in ("utf-8", "utf-8-sig")

    def test_parse_csv_basic(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("工单号,SN,状态\nGDC001,SN123,待处理\n", encoding="utf-8-sig")
        df, headers = parse_file(str(csv_file))
        assert len(df) == 1
        assert headers == ["工单号", "SN", "状态"]

    def test_parse_csv_with_extra_columns(self, tmp_path):
        """CSV with more data columns than headers."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("col1,col2\nval1,val2,val3\n", encoding="utf-8-sig")
        df, headers = parse_file(str(csv_file))
        assert len(df.columns) >= 3  # Should pad extra columns

    def test_parse_csv_drops_empty_rows(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("col1,col2\nval1,val2\n,,\n", encoding="utf-8-sig")
        df, headers = parse_file(str(csv_file))
        assert len(df) == 1  # Empty row dropped


class TestSchemaValidator:
    """Tests for schema validation utilities."""

    def test_resolve_target_table_english(self):
        result = resolve_target_table("refund_orders")
        assert result == "refund_orders"

    def test_resolve_target_table_chinese(self):
        result = resolve_target_table("退费单")
        assert result == "refund_orders"

    def test_resolve_target_table_unknown(self):
        result = resolve_target_table("nonexistent")
        assert result is None

    def test_get_registered_tables(self):
        tables = get_registered_tables()
        assert "refund_orders" in tables
        assert "service_refund_work_orders" in tables
        assert "wallet_withdrawals" in tables
        assert len(tables) == 3


class TestImportError:
    """Tests for ImportError exception class."""

    def test_import_error_basic(self):
        exc = ImportError("test message")
        assert exc.message == "test message"
        assert exc.status_code == 400
        assert exc.details == {}

    def test_import_error_with_details(self):
        exc = ImportError("error", status_code=422, details={"key": "val"})
        assert exc.status_code == 422
        assert exc.details == {"key": "val"}
