"""Tests for the import endpoint and related services."""

import pandas as pd
import pytest

# Import main to register models for schema validation tests
import main  # noqa: F401
from app.models import RefundOrder, ServiceRefundWorkOrder, WalletWithdrawal
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
from app.services.import_service import ImportError, get_upsert_key
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


class TestUpsertKey:
    """Tests for upsert key discovery."""

    def test_refund_order_upsert_key(self):
        key = get_upsert_key(RefundOrder)
        assert key == ["refund_order_no"]

    def test_service_refund_upsert_key(self):
        key = get_upsert_key(ServiceRefundWorkOrder)
        assert key == ["work_order_no"]

    def test_wallet_withdrawal_no_upsert_key(self):
        key = get_upsert_key(WalletWithdrawal)
        assert key == []


@pytest.mark.asyncio(loop_scope="class")
class TestUpsertIntegration:
    """Integration tests for upsert behavior — requires running database."""

    async def test_upsert_inserts_new_rows(self):
        """First upload inserts all rows, zero updated."""
        import tempfile
        import uuid
        from pathlib import Path

        from app.core.database import async_session_factory
        from app.services.import_service import ImportService

        unique_id = f"TEST-UP-{uuid.uuid4().hex[:8]}"
        csv_content = f"退费单号,平台订单号,退费金额\n{unique_id},ORDER-001,100.00\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8-sig") as f:
            f.write(csv_content)
            tmp_path = Path(f.name)

        try:
            async with async_session_factory() as db:
                service = ImportService(db)
                result = await service.run_import(tmp_path, "refund_orders")
                await db.commit()

                assert result["rows_inserted"] >= 1
                assert result["rows_updated"] == 0
                assert result["rows_imported"] >= 1
        finally:
            tmp_path.unlink(missing_ok=True)

    async def test_upsert_updates_existing_rows(self):
        """Re-upload updates existing rows, zero inserted."""
        import tempfile
        import uuid
        from pathlib import Path

        from app.core.database import async_session_factory
        from app.services.import_service import ImportService

        unique_id = f"TEST-UP-{uuid.uuid4().hex[:8]}"
        csv_content = f"退费单号,平台订单号,退费金额\n{unique_id},ORDER-002,200.00\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8-sig") as f:
            f.write(csv_content)
            tmp_path = Path(f.name)

        try:
            async with async_session_factory() as db:
                service = ImportService(db)
                result1 = await service.run_import(tmp_path, "refund_orders")
                assert result1["rows_inserted"] >= 1
                assert result1["rows_updated"] == 0

                with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8-sig") as f2:
                    f2.write(csv_content)
                    tmp_path2 = Path(f2.name)
                try:
                    result2 = await service.run_import(tmp_path2, "refund_orders")
                    await db.commit()

                    assert result2["rows_inserted"] == 0
                    assert result2["rows_updated"] >= 1
                finally:
                    tmp_path2.unlink(missing_ok=True)
        finally:
            tmp_path.unlink(missing_ok=True)

    async def test_upsert_preserves_business_key(self):
        """Business key value unchanged after update."""
        import tempfile
        import uuid
        from pathlib import Path

        from sqlalchemy import select as sa_select

        from app.core.database import async_session_factory
        from app.services.import_service import ImportService

        unique_id = f"TEST-UP-{uuid.uuid4().hex[:8]}"
        csv_content = f"退费单号,平台订单号,退费金额\n{unique_id},ORDER-003,300.00\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8-sig") as f:
            f.write(csv_content)
            tmp_path = Path(f.name)

        try:
            async with async_session_factory() as db:
                service = ImportService(db)
                await service.run_import(tmp_path, "refund_orders")

                csv_updated = f"退费单号,平台订单号,退费金额\n{unique_id},ORDER-003-CHANGED,999.99\n"
                with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8-sig") as f2:
                    f2.write(csv_updated)
                    tmp_path2 = Path(f2.name)
                try:
                    await service.run_import(tmp_path2, "refund_orders")
                    await db.commit()

                    stmt = sa_select(RefundOrder).where(RefundOrder.refund_order_no == unique_id)
                    result = await db.execute(stmt)
                    record = result.scalar_one_or_none()
                    assert record is not None
                    assert record.refund_order_no == unique_id
                    assert record.platform_order_no == "ORDER-003-CHANGED"
                    assert float(record.refund_amount) == 999.99
                finally:
                    tmp_path2.unlink(missing_ok=True)
        finally:
            tmp_path.unlink(missing_ok=True)

    async def test_wallet_withdrawal_hash_dedup(self):
        """WalletWithdrawal uses content_hash — re-import same data is skipped."""
        import tempfile
        import uuid
        from pathlib import Path

        from app.core.database import async_session_factory
        from app.services.import_service import ImportService

        unique_sn = f"SN-{uuid.uuid4().hex[:8]}"
        csv_content = (
            f"账户ID,SN,操作类型,操作金额,操作时间\n"
            f"ACC-HASH-001,{unique_sn},提现,99.99,2026-06-15 10:00:00\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8-sig") as f:
            f.write(csv_content)
            tmp_path = Path(f.name)

        try:
            async with async_session_factory() as db:
                service = ImportService(db)

                # First import: all rows should be inserted
                result1 = await service.run_import(tmp_path, "wallet_withdrawals")
                assert result1["rows_inserted"] >= 1
                assert result1["rows_updated"] == 0
                assert result1["rows_skipped"] == 0

                # Second import of the SAME data: all rows should be skipped
                result2 = await service.run_import(tmp_path, "wallet_withdrawals")
                await db.commit()

                assert result2["rows_inserted"] == 0
                assert result2["rows_updated"] == 0
                assert result2["rows_skipped"] >= 1
        finally:
            tmp_path.unlink(missing_ok=True)

    async def test_upsert_stats_in_import_job(self):
        """ImportJob records correct upsert breakdown."""
        import tempfile
        import uuid
        from pathlib import Path

        from sqlalchemy import select as sa_select

        from app.core.database import async_session_factory
        from app.models import ImportJob
        from app.services.import_service import ImportService

        unique_id = f"TEST-UP-{uuid.uuid4().hex[:8]}"
        csv_content = f"退费单号,平台订单号,退费金额\n{unique_id},ORDER-004,400.00\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8-sig") as f:
            f.write(csv_content)
            tmp_path = Path(f.name)

        try:
            async with async_session_factory() as db:
                service = ImportService(db)
                result = await service.run_import(tmp_path, "refund_orders")
                await db.commit()

                stmt = sa_select(ImportJob).where(ImportJob.id == result["import_job_id"])
                job_result = await db.execute(stmt)
                job = job_result.scalar_one()
                assert job.rows_inserted == result["rows_inserted"]
                assert job.rows_updated == result["rows_updated"]
                assert job.rows_skipped == result["rows_skipped"]
        finally:
            tmp_path.unlink(missing_ok=True)

    async def test_excel_import_inserts_rows(self):
        """Excel (.xlsx) import works same as CSV."""
        import tempfile
        import uuid
        from pathlib import Path

        from app.core.database import async_session_factory
        from app.services.import_service import ImportService

        unique_id = f"TEST-XL-{uuid.uuid4().hex[:8]}"

        # Create a .xlsx file with openpyxl
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["退费单号", "平台订单号", "退费金额"])
        ws.append([unique_id, "ORDER-XL-001", "123.45"])

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            tmp_path = Path(f.name)
        wb.save(str(tmp_path))

        try:
            async with async_session_factory() as db:
                service = ImportService(db)
                result = await service.run_import(tmp_path, "refund_orders")
                await db.commit()

                assert result["status"] == "completed"
                assert result["rows_inserted"] >= 1
                assert result["rows_updated"] == 0
                assert result["rows_imported"] >= 1
                assert "cleaning_report" in result
        finally:
            tmp_path.unlink(missing_ok=True)
