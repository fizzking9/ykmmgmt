"""Tests for the import endpoint and related services.

The system ships with no built-in business tables, so every DB-backed test
runs against a dynamically created fixture table (Schema Manager API).
"""

import pandas as pd
import pytest

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


# ── Schema validation against a dynamically created table ──────────────────

pytestmark_db = pytest.mark.usefixtures("_dispose_engine_after_test")


@pytestmark_db
@pytest.mark.asyncio
async def test_resolve_target_table_by_english_and_chinese(shared_dynamic_table):
    """resolve_target_table accepts both the English name and the display name."""
    from httpx import ASGITransport, AsyncClient

    from app.services.schema_validator import resolve_target_table
    from main import app
    from tests.conftest import ensure_shared_table

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        table = await ensure_shared_table(client, shared_dynamic_table)

        assert resolve_target_table(table) == table
        assert resolve_target_table("测试业务表") == table


@pytestmark_db
@pytest.mark.asyncio
async def test_resolve_target_table_unknown():
    """Unknown target table names resolve to None."""
    from app.services.schema_validator import resolve_target_table

    assert resolve_target_table("nonexistent") is None


@pytestmark_db
@pytest.mark.asyncio
async def test_registry_starts_without_builtin_tables(shared_dynamic_table):
    """The model registry holds only dynamically created tables."""
    from httpx import ASGITransport, AsyncClient

    from app.services.schema_validator import get_registered_tables
    from main import app
    from tests.conftest import ensure_shared_table

    legacy = {"refund_orders", "service_refund_work_orders", "wallet_withdrawals"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        table = await ensure_shared_table(client, shared_dynamic_table)
        tables = set(get_registered_tables())
        assert table in tables
        assert not legacy & tables


# ── Import service integration (dynamic fixture table) ─────────────────────


@pytest.mark.usefixtures("_dispose_engine_after_test")
@pytest.mark.asyncio(loop_scope="class")
class TestImportServiceIntegration:
    """Integration tests for ImportService — requires running database."""

    async def test_csv_import_inserts_rows_and_records_job(self, shared_dynamic_table):
        """A CSV upload inserts rows and records matching job statistics."""
        import tempfile
        import uuid
        from pathlib import Path

        from httpx import ASGITransport, AsyncClient
        from sqlalchemy import select as sa_select

        from app.core.database import async_session_factory
        from app.models import ImportJob
        from app.services.import_service import ImportService
        from main import app
        from tests.conftest import ensure_shared_table

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            table = await ensure_shared_table(client, shared_dynamic_table)

        unique_id = f"IMP-{uuid.uuid4().hex[:8]}"
        csv_content = f"订单号,金额,状态,记录时间\n{unique_id},123.45,已完成,2026-06-10 09:00:00\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8-sig") as f:
            f.write(csv_content)
            tmp_path = Path(f.name)

        try:
            async with async_session_factory() as db:
                service = ImportService(db)
                result = await service.run_import(tmp_path, table)
                await db.commit()

                assert result["status"] == "completed"
                assert result["rows_inserted"] == 1
                assert result["rows_updated"] == 0
                assert result["total_rows"] == 1
                assert "cleaning_report" in result

                stmt = sa_select(ImportJob).where(ImportJob.id == result["import_job_id"])
                job = (await db.execute(stmt)).scalar_one()
                assert job.rows_inserted == result["rows_inserted"]
                assert job.rows_updated == result["rows_updated"]
                assert job.rows_skipped == result["rows_skipped"]
        finally:
            tmp_path.unlink(missing_ok=True)

    async def test_excel_import_inserts_rows(self, shared_dynamic_table):
        """Excel (.xlsx) import works same as CSV."""
        import tempfile
        import uuid
        from pathlib import Path

        import openpyxl
        from httpx import ASGITransport, AsyncClient

        from app.core.database import async_session_factory
        from app.services.import_service import ImportService
        from main import app
        from tests.conftest import ensure_shared_table

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            table = await ensure_shared_table(client, shared_dynamic_table)

        unique_id = f"XL-{uuid.uuid4().hex[:8]}"
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["订单号", "金额", "状态", "记录时间"])
        ws.append([unique_id, "234.56", "已完成", "2026-06-11 10:00:00"])

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            tmp_path = Path(f.name)
        wb.save(str(tmp_path))

        try:
            async with async_session_factory() as db:
                service = ImportService(db)
                result = await service.run_import(tmp_path, table)
                await db.commit()

                assert result["status"] == "completed"
                assert result["rows_inserted"] == 1
                assert result["rows_updated"] == 0
                assert result["total_rows"] == 1
                assert "cleaning_report" in result
        finally:
            tmp_path.unlink(missing_ok=True)


@pytest.mark.usefixtures("_dispose_engine_after_test")
async def test_coercion_equal_duplicates_within_batch_count_correctly(tmp_path):
    """Rows identical only after type coercion (e.g. "10.50" vs "10.5") share
    one content_hash; within one batch they must collapse and count as
    skipped — rows_inserted must not credit both (else
    inserted+skipped exceeds total_rows)."""
    import uuid

    from httpx import ASGITransport, AsyncClient

    from main import app
    from tests.schema_cleanup import purge_dynamic_table

    name = f"cmdup_{uuid.uuid4().hex[:6]}"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": name,
                    "columns": [
                        {"name": "order_no", "type": "String", "length": 50, "label": "订单号"},
                        {"name": "amount", "type": "Numeric", "label": "金额"},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text

            csv_file = tmp_path / "cmdup.csv"
            csv_file.write_text("订单号,金额\nK1,10.50\nK1,10.5\nK2,20.00\n", encoding="utf-8")
            resp = await client.post(
                "/api/imports",
                files={"file": ("cmdup.csv", csv_file.read_bytes(), "text/csv")},
                data={"target_table": name},
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()

            # Counter invariant: 新增+更新+跳过+拒绝 == 文件行数
            assert (
                body["rows_inserted"] + body["rows_updated"] + body["rows_skipped"] + body["rows_rejected"]
                == body["total_rows"]
            )
            assert body["rows_inserted"] == 2
            assert body["rows_skipped"] == 1
            assert body["rows_rejected"] == 0

            rows = (await client.get(f"/api/schema/tables/{name}")).json()["sample_rows"]
            assert len([r for r in rows if r["order_no"] == "K1"]) == 1
        finally:
            await purge_dynamic_table(name)
