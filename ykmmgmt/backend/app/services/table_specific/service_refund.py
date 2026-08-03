"""Table-specific cleaning rules for 服务退款工单 (service_refund_work_orders).

Issues found in sample data:
1. Extra trailing column(s) — data rows have 29 cols (vs 28 header), some have 30.
   The 备注 field contains commas, creating extra columns.
2. Split rows — customer_remark (col[9]) contains embedded newlines, causing
   csv.reader to split one logical row into multiple physical rows.
   Example: row 7314's 客户备注 overflows into ghost rows 7315-7317.
   These overflow rows may have corrupted work_order_no (col 0) values like
   field labels ("问题描述："), numeric-only strings, or WS/WN prefixes.
   Only GD, GDC, and TS prefixes are valid for work_order_no.
"""

import re

import pandas as pd

from app.services.cleaning import CleaningReport, CleaningStepReport
from app.services.table_specific import register

# 服务退款工单 header has 28 columns
_EXPECTED_COLS = 28

# Valid work_order_no prefixes (col 0 before column mapping)
_VALID_WO_PATTERN = re.compile(r"^(GD|GDC|TS)\d+$")


def _has_invalid_wo(row) -> bool:
    """Check if a row's col 0 has an invalid (overflow) work_order_no."""
    val = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
    if val == "" or val.lower() in ("nan", "null", "none"):
        return True
    return not bool(_VALID_WO_PATTERN.match(val))


@register("service_refund_work_orders")
def fix_split_rows(df: pd.DataFrame, report: CleaningReport) -> tuple[pd.DataFrame, CleaningReport]:
    """Detect and merge rows split by newlines in text fields.

    Split/overflow rows appear as:
    - Rows with significantly fewer non-null columns (< 60% of expected)
    - Rows with corrupted work_order_no (col 0) values like field labels,
      numeric-only strings, or unexpected prefixes (WS, WN, WX).

    Algorithm: for each valid row, merge ALL consecutive overflow rows
    into it. Overflow rows without a preceding valid row are merged together
    (edge case — should not occur in practice).
    """
    if len(df) <= 1:
        return df, report

    rows_before = len(df)
    short_threshold = max(2, int(len(df.columns) * 0.6))

    # Mark rows as "overflow" based on column count OR invalid work_order_no
    col_counts = df.apply(lambda row: row.notna().sum(), axis=1)
    is_short = col_counts <= short_threshold
    is_invalid_wo = df.apply(_has_invalid_wo, axis=1)
    is_overflow = is_short | is_invalid_wo

    merged_count = 0
    drop_indices: list[int] = []
    i = 0

    while i < len(df):
        if not is_overflow.iloc[i]:
            # Valid row — merge ALL following consecutive overflow rows into it
            j = i + 1
            while j < len(df) and is_overflow.iloc[j]:
                j += 1
            overflow_count = j - (i + 1)

            if overflow_count > 0:
                parent = df.iloc[i].copy()
                for k in range(i + 1, j):
                    ov_row = df.iloc[k]
                    for col_idx in range(1, len(df.columns)):  # Skip col 0 (work_order_no)
                        pv = parent.iloc[col_idx]
                        ov = ov_row.iloc[col_idx]
                        if pd.isna(pv) or str(pv).strip() == "":
                            if not pd.isna(ov) and str(ov).strip() != "":
                                parent.iloc[col_idx] = ov
                        elif not pd.isna(ov) and str(ov).strip() != "":
                            parent.iloc[col_idx] = str(pv) + " " + str(ov)
                    drop_indices.append(k)
                df.iloc[i] = parent
                merged_count += overflow_count
                i = j
            else:
                i += 1
        else:
            # Overflow row without preceding valid row (edge case — rare)
            # Merge consecutive overflows together
            j = i + 1
            while j < len(df) and is_overflow.iloc[j]:
                j += 1
            overflow_count = j - i

            if overflow_count >= 2:
                merged_row = df.iloc[i].copy()
                for k in range(i + 1, j):
                    next_row = df.iloc[k]
                    for col_idx in range(len(df.columns)):
                        mv = merged_row.iloc[col_idx]
                        nv = next_row.iloc[col_idx]
                        if pd.isna(mv) or str(mv).strip() == "":
                            if not pd.isna(nv) and str(nv).strip() != "":
                                merged_row.iloc[col_idx] = nv
                        elif not pd.isna(nv) and str(nv).strip() != "":
                            merged_row.iloc[col_idx] = str(mv) + " " + str(nv)
                    drop_indices.append(k)
                df.iloc[i] = merged_row
                merged_count += overflow_count - 1
            i = j

    if drop_indices:
        df = df.drop(df.index[drop_indices])
        df = df.reset_index(drop=True)

    report.add_step(
        CleaningStepReport(
            step_name="fix_split_rows",
            rows_before=rows_before,
            rows_after=len(df),
            rows_dropped=len(drop_indices),
            rows_modified=merged_count,
            warnings=[f"Merged {merged_count} split/overflow rows from newlines"] if merged_count > 0 else [],
        )
    )
    return df, report


@register("service_refund_work_orders")
def validate_work_order_no(df: pd.DataFrame, report: CleaningReport) -> tuple[pd.DataFrame, CleaningReport]:
    """Drop rows whose work_order_no (col 0) still fails the valid-prefix check.

    Runs AFTER fix_split_rows as a safety net. Any surviving invalid rows
    represent edge cases the merge logic could not handle. We drop them
    rather than letting corrupt data into the database.
    """
    rows_before = len(df)
    is_invalid = df.apply(_has_invalid_wo, axis=1)
    drop_count = int(is_invalid.sum())

    if drop_count > 0:
        df = df[~is_invalid]
        df = df.reset_index(drop=True)

    report.add_step(
        CleaningStepReport(
            step_name="validate_work_order_no",
            rows_before=rows_before,
            rows_after=len(df),
            rows_dropped=drop_count,
            rows_modified=0,
            warnings=[f"Dropped {drop_count} rows with invalid work_order_no (unmergeable overflow)"] if drop_count > 0 else [],
        )
    )
    return df, report


@register("service_refund_work_orders")
def fix_extra_trailing_column(df: pd.DataFrame, report: CleaningReport) -> tuple[pd.DataFrame, CleaningReport]:
    """Merge all extra trailing columns into preceding columns.

    Data rows typically have 29 cols (vs 28 header), sometimes 30.
    Extra columns come from commas in 备注/内部备注 splitting the field.
    Merge them back iteratively until we reach the expected column count.
    Runs AFTER fix_split_rows so column counts are normalized.
    """
    if len(df.columns) <= _EXPECTED_COLS:
        return df, report

    rows_before = len(df)
    modified = 0

    while len(df.columns) > _EXPECTED_COLS:
        last_col = df.columns[-1]
        prev_col = df.columns[-2]

        mask = df[last_col].notna() & (df[last_col].astype(str).str.strip() != "")
        if mask.any():
            df.loc[mask, prev_col] = df.loc[mask, prev_col].astype(str) + "," + df.loc[mask, last_col].astype(str)
            modified += int(mask.sum())

        df = df.drop(columns=[last_col])

    report.add_step(
        CleaningStepReport(
            step_name="fix_extra_trailing_column",
            rows_before=rows_before,
            rows_after=len(df),
            rows_dropped=0,
            rows_modified=modified,
            warnings=[f"Merged extra columns from comma-split 备注 ({modified} rows affected)"] if modified > 0 else [],
        )
    )
    return df, report
