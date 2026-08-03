"""Seed script — loads first 20 rows from each CSV into the database.

Usage:
  python seed.py              Seed the database with sample data
  python seed.py --cleanup    Truncate all data (preserves table schema)

Requires: PostgreSQL running via docker compose, DATABASE_URL set in .env
"""

import asyncio
import csv
import io
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.database import async_session_factory
from app.models import (
    DataSource,
    RefundOrder,
    ServiceRefundWorkOrder,
    WalletWithdrawal,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SEED_ROWS = 20

CSV_FILES = [
    {
        "path": PROJECT_ROOT / "服务退款工单0601~0721.csv",
        "source_name": "服务退款工单",
        "source_type": "csv",
        "model": ServiceRefundWorkOrder,
        "column_map": {
            0: "work_order_no",
            1: "sn",
            2: "device_type",
            3: "device_type_remark",
            4: "phone",
            5: "service_category",
            6: "service_item",
            7: "priority",
            8: "status",
            9: "customer_remark",
            10: "registered_at",
            11: "activated_at",
            12: "dispatched_at",
            13: "completed_at",
            14: "processing_duration",
            15: "registrar",
            16: "channel",
            17: "processing_node",
            18: "processor",
            19: "processing_opinion",
            20: "is_appeal",
            21: "order_no",
            22: "bank_name",
            23: "bank_card_no",
            24: "recipient",
            25: "internal_remark",
            26: "refund_amount",
            27: "estimated_refundable_amount",
        },
    },
    {
        "path": PROJECT_ROOT / "退费单0601~0721.csv",
        "source_name": "退费单",
        "source_type": "csv",
        "model": RefundOrder,
        "column_map": {
            0: "refund_order_no",
            1: "platform_order_no",
            2: "third_party_order_no",
            3: "device_sn",
            4: "refund_reason",
            5: "plan_name",
            6: "merchant_name",
            7: "refund_amount",
            8: "actual_refund_amount",
            9: "remark",
            10: "status",
            11: "refund_method",
            12: "audit_remark",
            13: "auditor",
            14: "record_created_at",
            15: "record_updated_at",
            16: "operator",
            17: "plan_price",
        },
    },
    {
        "path": PROJECT_ROOT / "钱包提现操作0601~0721.csv",
        "source_name": "钱包提现操作",
        "source_type": "csv",
        "model": WalletWithdrawal,
        "column_map": {
            0: "account_id",
            1: "wallet_balance",
            2: "sn",
            3: "operation_type",
            4: "operation_amount",
            5: "remark",
            6: "operated_at",
            7: "operator",
        },
    },
]


def read_csv_rows(filepath: Path, max_rows: int) -> list[dict]:
    """Read a CSV file, strip tab characters, return list of dicts mapped via column_map."""
    if not filepath.exists():
        raise FileNotFoundError(f"CSV file not found: {filepath}")

    with open(filepath, encoding="utf-8-sig") as f:
        content = f.read().replace("\t", "")

    reader = csv.reader(io.StringIO(content))
    next(reader)  # skip header

    # Find the matching config
    cfg = next(c for c in CSV_FILES if c["path"] == filepath)
    column_map = cfg["column_map"]

    rows = []
    for i, raw_row in enumerate(reader):
        if i >= max_rows:
            break
        if not any(raw_row):  # skip fully empty rows
            continue

        row_data = {}
        for col_idx, field_name in column_map.items():
            value = raw_row[col_idx] if col_idx < len(raw_row) else ""
            value = value.strip()
            # Convert common null representations
            if value.lower() in ("null", "nan", ""):
                value = None
            row_data[field_name] = value
        rows.append(row_data)

    return rows


def coerce_value(value, column_type):
    """Coerce a string value to the expected Python type for the model column."""
    if value is None:
        return None
    try:
        if "int" in str(column_type).lower():
            return int(float(value))
        if "numeric" in str(column_type).lower() or "float" in str(column_type).lower():
            return float(value)
        if "datetime" in str(column_type).lower():
            from datetime import datetime

            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S"):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
            return None
    except (ValueError, TypeError):
        return None
    return value


async def seed():
    """Seed each CSV into its table, skipping rows that fail to insert."""
    async with async_session_factory() as session:
        # Check if data already seeded
        result = await session.execute(select(DataSource).limit(1))
        if result.scalars().first():
            print("Data already seeded — skipping.")
            return

        # Inspect column types once per model
        from sqlalchemy import inspect as sa_inspect

        for cfg in CSV_FILES:
            filepath = cfg["path"]
            model = cfg["model"]
            print(f"Seeding {cfg['source_name']} from {filepath.name}...")

            # Create DataSource record
            source = DataSource(
                name=cfg["source_name"],
                source_type=cfg["source_type"],
                config={
                    "file_path": str(filepath.relative_to(PROJECT_ROOT)),
                    "encoding": "utf-8-sig",
                },
            )
            session.add(source)
            await session.flush()

            rows = read_csv_rows(filepath, SEED_ROWS)
            mapper = sa_inspect(model)
            col_types = {c.name: c.type for c in mapper.columns}

            inserted = 0
            skipped = 0
            for row_data in rows:
                coerced = {}
                for k, v in row_data.items():
                    if k in col_types:
                        coerced[k] = coerce_value(v, col_types[k])
                    else:
                        coerced[k] = v

                stmt = insert(model).values(**coerced).on_conflict_do_nothing()
                try:
                    await session.execute(stmt)
                    inserted += 1
                except Exception as exc:
                    skipped += 1
                    print(f"  ⚠ Skipped row (key={coerced.get(list(coerced.keys())[0], '?')[:30]}): {exc}")

            print(f"  → {inserted} inserted, {skipped} skipped")

        await session.commit()
        print("Seed complete.")


async def sanity_check():
    """Print row counts and a sample row from each table for verification."""
    async with async_session_factory() as session:
        tables = [
            ("datasources", DataSource),
            ("service_refund_work_orders", ServiceRefundWorkOrder),
            ("refund_orders", RefundOrder),
            ("wallet_withdrawals", WalletWithdrawal),
        ]
        print("\n=== Sanity Check ===")
        for name, model in tables:
            result = await session.execute(select(model))
            rows = result.scalars().all()
            print(f"\n{name}: {len(rows)} rows")
            if rows:
                sample = rows[0]
                cols = [c.name for c in model.__table__.columns if c.name != "id"][:5]
                for col in cols:
                    val = getattr(sample, col, None)
                    if isinstance(val, str) and len(val) > 50:
                        val = val[:50] + "..."
                    print(f"  {col}: {val}")
        print("\n=== Sanity Check Complete ===")


async def cleanup():
    """Truncate all data from all tables — preserves schema and resets sequences."""
    from sqlalchemy import text

    async with async_session_factory() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE import_jobs, datasources, "
                "service_refund_work_orders, refund_orders, "
                "wallet_withdrawals RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()
    print("All tables truncated — data removed, schema preserved.")


async def main():
    await seed()
    await sanity_check()


if __name__ == "__main__":
    if "--cleanup" in sys.argv:
        asyncio.run(cleanup())
    else:
        asyncio.run(main())
