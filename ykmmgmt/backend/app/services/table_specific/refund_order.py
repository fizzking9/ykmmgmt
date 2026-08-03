"""Table-specific cleaning rules for 退费单 (refund_orders).

Issues found in sample data:
1. Extra trailing column — data rows have 19 cols vs 18 header cols.
   The 备注 field contains commas, creating an extra column. In most rows
   the extra is empty (trailing comma artifact); in ~47 rows it contains
   real 备注 overflow text.
2. Split rows — 备注 contains embedded newlines, causing csv.reader to
   split one logical row into multiple physical rows. The overflow rows
   may have corrupted refund_order_no (col 0) values like field labels,
   empty strings, or unexpected prefixes (WX).
   Only RB, RE, and RF prefixes are valid for refund_order_no.

Fix strategy:
- Extra columns: merge all trailing extras into the second-to-last column
- Split rows: merge ALL consecutive overflow rows (short columns OR invalid
  refund_order_no) into the preceding valid row
- Validate: drop any remaining rows with invalid refund_order_no (edge cases)
"""

import re

import pandas as pd

from app.services.cleaning import CleaningReport, CleaningStepReport
from app.services.table_specific import register

# 退费单 header has 18 columns; data rows typically have 19
_EXPECTED_COLS = 18

# Valid refund_order_no prefixes (col 0 before column mapping)
_VALID_RO_PATTERN = re.compile(r"^(RB|RE|RF)\d+$")


def _has_invalid_ro(row) -> bool:
    """Check if a row's col 0 has an invalid (overflow) refund_order_no."""
    val = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
    if val == "" or val.lower() in ("nan", "null", "none"):
        return True
    return not bool(_VALID_RO_PATTERN.match(val))


@register("refund_orders")
def validate_refund_order_no(df: pd.DataFrame, report: CleaningReport) -> tuple[pd.DataFrame, CleaningReport]:
    """Drop rows whose refund_order_no (col 0) still fails the valid-prefix check.

    Runs AFTER fix_split_rows as a safety net. Any surviving invalid rows
    represent edge cases the merge logic could not handle. We drop them
    rather than letting corrupt data into the database.
    """
    rows_before = len(df)
    is_invalid = df.apply(_has_invalid_ro, axis=1)
    drop_count = int(is_invalid.sum())

    if drop_count > 0:
        df = df[~is_invalid]
        df = df.reset_index(drop=True)

    report.add_step(
        CleaningStepReport(
            step_name="validate_refund_order_no",
            rows_before=rows_before,
            rows_after=len(df),
            rows_dropped=drop_count,
            rows_modified=0,
            warnings=[f"Dropped {drop_count} rows with invalid refund_order_no (unmergeable overflow)"] if drop_count > 0 else [],
        )
    )
    return df, report


@register("refund_orders")
def fix_extra_trailing_column(df: pd.DataFrame, report: CleaningReport) -> tuple[pd.DataFrame, CleaningReport]:
    """Merge all extra trailing columns into the second-to-last column.

    Data rows have 19 cols (vs 18 header). The 19th col is the tail of
    the 备注 field split by an embedded comma. Merge it back.
    """
    if len(df.columns) <= _EXPECTED_COLS:
        return df, report

    rows_before = len(df)
    modified = 0

    # While we have more columns than expected, merge the last column into the one before it
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


@register("refund_orders")
def fix_split_rows(df: pd.DataFrame, report: CleaningReport) -> tuple[pd.DataFrame, CleaningReport]:
    """Detect and merge rows split by newlines in the 备注 field.

    Split/overflow rows appear as:
    - Rows with significantly fewer non-null columns (< 60% of expected)
    - Rows with corrupted refund_order_no (col 0) values like field labels,
      empty strings, or unexpected prefixes (WX).

    Algorithm: for each valid row, merge ALL consecutive overflow rows
    into it. Overflow rows without a preceding valid row are merged together
    (edge case — should not occur in practice).
    """
    if len(df) <= 1:
        return df, report

    rows_before = len(df)
    short_threshold = max(2, int(len(df.columns) * 0.6))

    # Mark rows as "overflow" based on column count OR invalid refund_order_no
    col_counts = df.apply(lambda row: row.notna().sum(), axis=1)
    is_short = col_counts <= short_threshold
    is_invalid_ro = df.apply(_has_invalid_ro, axis=1)
    is_overflow = is_short | is_invalid_ro

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
                    for col_idx in range(1, len(df.columns)):  # Skip col 0 (refund_order_no)
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
            warnings=[f"Merged {merged_count} split/overflow rows from 备注 newlines"] if merged_count > 0 else [],
        )
    )
    return df, report
