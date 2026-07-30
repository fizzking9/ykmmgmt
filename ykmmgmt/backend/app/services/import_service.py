"""Import service — orchestrates parsing, validation, cleaning, and DB insertion."""

import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import and_, or_, select
from sqlalchemy import func as sa_func
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DataSource, ImportJob
from app.services.cleaning import CleaningPipeline
from app.services.parsers import parse_file
from app.services.schema_validator import (
    get_chinese_table_name,
    get_registered_model,
    get_registered_tables,
    resolve_target_table,
    validate_headers,
)
from app.services.table_specific import get_rules


def get_upsert_key(model_class: Any) -> list[str]:
    """Return the business unique key column names for a model.

    Uses the __upsert_key__ class attribute if defined, otherwise falls back
    to introspecting columns with unique=True.
    """
    if hasattr(model_class, "__upsert_key__"):
        return list(model_class.__upsert_key__)
    # Fallback: introspect columns with unique=True
    mapper = sa_inspect(model_class)
    return [c.name for c in mapper.columns if c.unique and not c.primary_key]


_METADATA_COLS = {"id", "imported_at", "created_at", "content_hash"}


def _compute_content_hash(row_data: dict[str, Any], business_cols: list[str]) -> str:
    """Compute SHA-256 hash of business columns for dedup.

    Uses JSON serialization with sorted keys for deterministic output.
    """
    business_data = {k: row_data.get(k) for k in sorted(business_cols)}
    serializable: dict[str, Any] = {}
    for k, v in business_data.items():
        if v is None:
            serializable[k] = None
        elif isinstance(v, datetime.datetime):
            serializable[k] = v.isoformat()
        elif isinstance(v, datetime.date):
            serializable[k] = v.isoformat()
        else:
            serializable[k] = v
    json_str = json.dumps(serializable, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()


class ImportError(Exception):
    """Import-related error with structured details."""

    def __init__(self, message: str, status_code: int = 400, details: dict | None = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class ImportService:
    """Handles the full import flow: parse → validate → clean → insert."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_import(
        self,
        filepath: Path,
        target_table: str,
    ) -> dict[str, Any]:
        """Run a complete import job.

        Returns a dict with the import result.
        """
        # Resolve and validate target table
        english_name = resolve_target_table(target_table)
        if english_name is None:
            valid_names = [get_chinese_table_name(t) for t in get_registered_tables()]
            raise ImportError(
                message=f"未知的目标表 '{target_table}'。可选：{'、'.join(valid_names)}",
                status_code=400,
            )

        model_class = get_registered_model(english_name)
        if model_class is None:
            raise ImportError(
                message=f"目标表 '{target_table}' 未注册模型。",
                status_code=500,
            )

        chinese_name = get_chinese_table_name(english_name)

        # Step 1: Parse file
        try:
            df, raw_headers = parse_file(filepath)
        except ValueError as e:
            raise ImportError(message=str(e), status_code=415) from e
        except Exception as e:
            raise ImportError(message=f"文件解析失败: {e}", status_code=400) from e

        if df.empty:
            # Create DataSource and ImportJob even for empty files
            source = await self._get_or_create_source(english_name, filepath)
            job = await self._create_import_job(source.id)
            await self._finish_import_job(job, "completed", 0, 0, 0, 0, 0)
            return {
                "import_job_id": job.id,
                "target_table": chinese_name,
                "status": "completed",
                "rows_imported": 0,
                "rows_rejected": 0,
                "rows_inserted": 0,
                "rows_updated": 0,
                "rows_skipped": 0,
                "cleaning_report": {"steps": [], "warnings_per_column": {}, "rows_before": 0, "rows_after": 0},
                "errors": [],
            }

        # Step 2: Schema validation gate
        validation = validate_headers(raw_headers, target_table)
        if not validation.valid:
            if validation.missing:
                raise ImportError(
                    message="文件列与目标表不匹配",
                    status_code=422,
                    details={
                        "target_table": validation.target_table,
                        "missing": validation.missing,
                        "unexpected": validation.unexpected,
                        "expected": validation.expected,
                    },
                )
            # If no missing columns but unexpected → warn but proceed
            # (extra columns in file are allowed)

        # Step 3: Run table-specific structural cleaning BEFORE column mapping
        # (fixes extra trailing columns, split rows etc. on raw column structure)
        pre_pipeline = CleaningPipeline()
        pre_pipeline.clear_common_steps()  # Only table-specific structural rules
        for rule_fn in get_rules(english_name):
            pre_pipeline.add_table_step(rule_fn)
        df, pre_report = pre_pipeline.run(df)

        # Step 4: Rename columns from Chinese to English using mapping
        df = self._apply_column_mapping(df, validation.column_mapping, raw_headers)

        # Step 5: Run common cleaning pipeline (content cleanup)
        pipeline = CleaningPipeline()
        df, cleaning_report = pipeline.run(df)

        # Merge pre-pipeline report steps into the cleaning report
        pre_report.steps.extend(cleaning_report.steps)
        pre_report.rows_after = cleaning_report.rows_after
        cleaning_report = pre_report

        # Step 6: Create DataSource and ImportJob
        source = await self._get_or_create_source(english_name, filepath)
        job = await self._create_import_job(source.id)

        # Step 7: Insert/upsert cleaned rows
        rows_inserted = 0
        rows_updated = 0
        rows_skipped = 0
        rows_rejected = 0
        errors: list[dict] = []

        if not df.empty:
            rows_inserted, rows_updated, rows_skipped, errors = await self._insert_rows(model_class, df, job.id)

        rows_imported_total = rows_inserted + rows_updated
        await self._finish_import_job(
            job,
            "completed",
            rows_imported_total,
            rows_rejected,
            rows_inserted,
            rows_updated,
            rows_skipped,
            errors,
        )

        return {
            "import_job_id": job.id,
            "target_table": chinese_name,
            "status": "completed",
            "rows_imported": rows_imported_total,
            "rows_rejected": rows_rejected,
            "rows_inserted": rows_inserted,
            "rows_updated": rows_updated,
            "rows_skipped": rows_skipped,
            "cleaning_report": cleaning_report.to_dict(),
            "errors": errors,
        }

    def _apply_column_mapping(self, df: pd.DataFrame, mapping: dict[str, str], raw_headers: list[str]) -> pd.DataFrame:
        """Apply Chinese→English column name mapping to the DataFrame."""
        rename_map: dict[str, str] = {}
        used_english: set[str] = set()

        for header in raw_headers:
            header = header.strip()
            if header in mapping:
                english = mapping[header]
                # Find which DataFrame column matches this header (by position)
                for _col_idx, col in enumerate(df.columns):
                    if col.strip() == header and english not in used_english:
                        rename_map[col] = english
                        used_english.add(english)
                        break

        if rename_map:
            df = df.rename(columns=rename_map)

        # Keep only mapped columns (drop unexpected ones)
        keep_cols = [c for c in df.columns if c in rename_map.values()]
        if keep_cols:
            df = df[keep_cols]

        return df

    async def _get_or_create_source(self, table_name: str, filepath: Path) -> DataSource:
        """Get or create a DataSource record for this import."""
        chinese_name = get_chinese_table_name(table_name)
        # For simplicity, create a new source for each import type
        source = DataSource(
            name=f"{chinese_name}导入",
            source_type=filepath.suffix.lstrip("."),
            config={
                "file_path": str(filepath.name),
                "target_table": table_name,
            },
        )
        self.db.add(source)
        await self.db.flush()
        return source

    async def _create_import_job(self, source_id: int) -> ImportJob:
        """Create an ImportJob in pending status."""
        job = ImportJob(
            source_id=source_id,
            status="pending",
            row_count=0,
            error_count=0,
            rows_inserted=0,
            rows_updated=0,
            rows_skipped=0,
        )
        self.db.add(job)
        await self.db.flush()
        return job

    async def _insert_rows(
        self,
        model_class: Any,
        df: pd.DataFrame,
        job_id: int,
    ) -> tuple[int, int, int, list[dict]]:
        """Insert/upsert cleaned rows into the target table in batches.

        Uses ON CONFLICT DO UPDATE for upsert semantics. Returns
        (rows_inserted, rows_updated, rows_skipped, errors).
        """
        inserted = 0
        updated = 0
        skipped = 0
        job_errors: list[dict] = []

        mapper = sa_inspect(model_class)
        upsert_key = get_upsert_key(model_class)
        use_upsert = len(upsert_key) > 0

        # Build column metadata: name → (type, nullable, max_length)
        col_meta: dict[str, dict] = {}
        has_content_hash = False
        business_cols: list[str] = []
        for c in mapper.columns:
            if c.name in ("id", "imported_at", "created_at", "content_hash"):
                if c.name == "content_hash":
                    has_content_hash = True
                continue
            business_cols.append(c.name)
            max_len = None
            if hasattr(c.type, "length") and c.type.length:
                max_len = c.type.length
            col_meta[c.name] = {
                "type": str(c.type).lower(),
                "nullable": c.nullable,
                "max_len": max_len,
            }

        # Filter to only valid columns present in the DataFrame
        insert_cols = [c for c in df.columns if c in col_meta]
        if not insert_cols:
            return 0, 0, 0, []

        # Determine which columns to update on conflict
        # Exclude: primary key, upsert key columns, and timestamp columns
        exclude_from_update = {"id"} | set(upsert_key) | {"imported_at", "record_created_at", "record_updated_at"}
        update_cols = [c.name for c in mapper.columns if c.name not in exclude_from_update]

        # Pre-validate all rows and build clean data list
        clean_rows: list[dict] = []
        for _row_idx, (_, row) in enumerate(df[insert_cols].iterrows()):
            row_data = {}
            skip = False
            for col in insert_cols:
                val = row[col]
                meta = col_meta[col]
                if pd.isna(val) or str(val).strip().lower() in ("nan", "null", "none", ""):
                    val = None
                else:
                    val = self._coerce_value(val, col_meta, col)

                # Reject rows missing required non-nullable values
                if val is None and not meta["nullable"]:
                    skip = True
                    break

                # Truncate strings that exceed column max length
                if val is not None and isinstance(val, str) and meta["max_len"]:
                    val = val[: meta["max_len"]]

                row_data[col] = val

            if skip:
                skipped += 1
                continue

            # Compute content hash for hash-based dedup (insert-only tables)
            if has_content_hash:
                row_data["content_hash"] = _compute_content_hash(row_data, business_cols)

            # Skip rows with null business keys (only when upsert is active)
            if use_upsert and any(row_data.get(k) is None for k in upsert_key):
                skipped += 1
                continue

            clean_rows.append(row_data)

        # Batch insert/upsert in groups of 500
        batch_size = 500
        for batch_start in range(0, len(clean_rows), batch_size):
            batch = clean_rows[batch_start : batch_start + batch_size]

            if use_upsert:
                # Count existing keys in this batch
                batch_existing = await self._count_existing_keys(model_class, upsert_key, batch)

                try:
                    async with self.db.begin_nested():
                        stmt = insert(model_class).values(batch)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=upsert_key,
                            set_={col: getattr(stmt.excluded, col) for col in update_cols}
                            | {"imported_at": sa_func.now()},
                        )
                        await self.db.execute(stmt)
                    inserted += len(batch) - batch_existing
                    updated += batch_existing
                except Exception:
                    # Batch failed — fall back to individual rows for this batch
                    for i, row_data in enumerate(batch):
                        try:
                            row_existing = await self._count_existing_keys(model_class, upsert_key, [row_data])
                            async with self.db.begin_nested():
                                stmt = insert(model_class).values(**row_data)
                                stmt = stmt.on_conflict_do_update(
                                    index_elements=upsert_key,
                                    set_={col: getattr(stmt.excluded, col) for col in update_cols}
                                    | {"imported_at": sa_func.now()},
                                )
                                await self.db.execute(stmt)
                            if row_existing:
                                updated += 1
                            else:
                                inserted += 1
                        except Exception as row_exc:
                            skipped += 1
                            if len(job_errors) < 200:
                                job_errors.append(
                                    {
                                        "row": batch_start + i + 1,
                                        "error": str(row_exc)[:300],
                                    }
                                )
            else:
                # No upsert key — insert-only mode
                if has_content_hash:
                    # Pre-count existing hashes so stats are accurate
                    batch_existing = await self._count_existing_hashes(model_class, batch)
                else:
                    batch_existing = 0

                try:
                    async with self.db.begin_nested():
                        stmt = insert(model_class).values(batch)
                        if has_content_hash:
                            stmt = stmt.on_conflict_do_nothing(
                                constraint="uq_wallet_withdrawal_content_hash"
                            )
                        else:
                            stmt = stmt.on_conflict_do_nothing()
                        await self.db.execute(stmt)
                    inserted += len(batch) - batch_existing
                    skipped += batch_existing
                except Exception:
                    # Batch failed — fall back to individual rows
                    for i, row_data in enumerate(batch):
                        try:
                            async with self.db.begin_nested():
                                stmt = insert(model_class).values(**row_data)
                                if has_content_hash:
                                    stmt = stmt.on_conflict_do_nothing(
                                        constraint="uq_wallet_withdrawal_content_hash"
                                    )
                                else:
                                    stmt = stmt.on_conflict_do_nothing()
                                await self.db.execute(stmt)
                            inserted += 1
                        except Exception as row_exc:
                            skipped += 1
                            if len(job_errors) < 200:
                                job_errors.append(
                                    {
                                        "row": batch_start + i + 1,
                                        "error": str(row_exc)[:300],
                                    }
                                )

        return inserted, updated, skipped, job_errors

    async def _count_existing_keys(
        self,
        model_class: Any,
        key_cols: list[str],
        batch: list[dict],
    ) -> int:
        """Count how many rows in the batch already exist in the database."""
        if not batch or not key_cols:
            return 0

        if len(key_cols) == 1:
            key_col = key_cols[0]
            key_values = [row[key_col] for row in batch if row.get(key_col) is not None]
            if not key_values:
                return 0
            stmt = select(sa_func.count()).select_from(model_class).where(getattr(model_class, key_col).in_(key_values))
        else:
            conditions = []
            for row in batch:
                if all(row.get(col) is not None for col in key_cols):
                    conditions.append(and_(*[getattr(model_class, col) == row[col] for col in key_cols]))
            if not conditions:
                return 0
            stmt = select(sa_func.count()).select_from(model_class).where(or_(*conditions))

        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def _count_existing_hashes(
        self,
        model_class: Any,
        batch: list[dict],
    ) -> int:
        """Count how many rows in the batch have content hashes that already exist in the DB."""
        if not batch:
            return 0
        hashes = [row["content_hash"] for row in batch if row.get("content_hash")]
        if not hashes:
            return 0
        stmt = (
            select(sa_func.count())
            .select_from(model_class)
            .where(model_class.content_hash.in_(hashes))
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    def _coerce_value(self, value: Any, col_meta: dict, col_name: str) -> Any:
        """Coerce a value to the expected column type."""
        meta = col_meta.get(col_name, {})
        type_str = meta.get("type", "")

        try:
            if "int" in type_str or "integer" in type_str:
                return int(float(str(value)))
            if "numeric" in type_str or "float" in type_str:
                return float(str(value))
            if "datetime" in type_str or "date" in type_str:
                val_str = str(value).strip()
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
                    try:
                        return datetime.datetime.strptime(val_str, fmt)
                    except ValueError:
                        continue
                return None
        except (ValueError, TypeError):
            return None

        if isinstance(value, str):
            value = value.strip()

        return value

    async def _finish_import_job(
        self,
        job: ImportJob,
        status: str,
        row_count: int,
        error_count: int,
        rows_inserted: int = 0,
        rows_updated: int = 0,
        rows_skipped: int = 0,
        errors: list[dict] | None = None,
    ) -> None:
        """Update ImportJob with final results."""
        job.status = status
        job.row_count = row_count
        job.error_count = error_count
        job.rows_inserted = rows_inserted
        job.rows_updated = rows_updated
        job.rows_skipped = rows_skipped
        job.finished_at = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        if errors:
            job.errors = {"items": errors}
        await self.db.flush()
