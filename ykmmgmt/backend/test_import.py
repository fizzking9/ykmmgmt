import json

import requests

BASE_URL = "http://localhost:8000"

CSV_FILES = {
    "refund_orders": "../../退费单0601~0721.csv",
    "service_refund_work_orders": "../../服务退款工单0601~0721.csv",
    "wallet_withdrawals": "../../钱包提现操作0601~0721.csv",
}


def test_import(target_table: str, filepath: str):
    """Test importing a CSV file into target table."""
    print(f"\n{'=' * 60}")
    print(f"Testing: {target_table} <- {filepath}")
    print(f"{'=' * 60}")

    try:
        with open(filepath, "rb") as f:
            r = requests.post(
                f"{BASE_URL}/api/imports",
                files={"file": ("data.csv", f, "text/csv")},
                data={"target_table": target_table},
                timeout=300,
            )
    except FileNotFoundError:
        print(f"  SKIP: File not found: {filepath}")
        return

    print(f"  HTTP Status: {r.status_code}")

    try:
        data = r.json()
    except Exception:
        print(f"  Raw response: {r.text[:500]}")
        return

    if r.status_code >= 400:
        print(f"  Detail: {data.get('detail', 'N/A')}")
        print(f"  Full: {json.dumps(data, ensure_ascii=False, indent=2)}")
        return

    print(f"  Target: {data.get('target_table')}")
    print(f"  Status: {data.get('status')}")
    print(f"  Rows imported: {data.get('rows_imported')}")
    print(f"  Rows rejected: {data.get('rows_rejected')}")

    report = data.get("cleaning_report", {})
    steps = report.get("steps", [])
    print(f"  Cleaning steps: {len(steps)}")
    for s in steps:
        print(
            f"    {s['step']}: {s['rows_before']}->{s['rows_after']}"
            f" dropped={s['rows_dropped']} modified={s['rows_modified']}"
        )
        for w in s.get("warnings", []):
            print(f"      Warning: {w}")

    errors = data.get("errors", [])
    if errors:
        print(f"  Errors: {len(errors)} items (first 5):")
        for e in errors[:5]:
            print(f"    {e}")

    return data


if __name__ == "__main__":
    total_success = 0
    total_fail = 0

    for table, filepath in CSV_FILES.items():
        result = test_import(table, filepath)
        if result and result.get("status") == "completed":
            total_success += 1
        else:
            total_fail += 1

    print(f"\n{'=' * 60}")
    print(f"Summary: {total_success} succeeded, {total_fail} failed")
    print(f"{'=' * 60}")
