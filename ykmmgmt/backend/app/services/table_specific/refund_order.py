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
- Malformed rows: detect and drop (do NOT attempt merge — it corrupts
  parent rows). Counted as rejected.
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
def drop_malformed_rows(df: pd.DataFrame, report: CleaningReport) -> tuple[pd.DataFrame, CleaningReport]:
    """Detect and drop malformed/split rows caused by newlines in 备注.

    Split/overflow rows appear as:
    - Rows with significantly fewer non-null columns (< 60% of expected)
    - Rows with corrupted refund_order_no (col 0) values like field labels,
      empty strings, or unexpected prefixes (WX).

    These rows cannot be reliably merged — merging corrupts the parent
    row's data (e.g. overwrites 退费金额 with garbage).  We simply detect
    and drop them, counting them as rejected.
    """
    if len(df) <= 1:
        return df, report

    rows_before = len(df)
    short_threshold = max(2, int(len(df.columns) * 0.6))

    col_counts = df.apply(lambda row: row.notna().sum(), axis=1)
    is_short = col_counts <= short_threshold
    is_invalid_ro = df.apply(_has_invalid_ro, axis=1)
    is_malformed = is_short | is_invalid_ro

    drop_count = int(is_malformed.sum())

    if drop_count > 0:
        df = df[~is_malformed]
        df = df.reset_index(drop=True)

    report.add_step(
        CleaningStepReport(
            step_name="drop_malformed_rows",
            rows_before=rows_before,
            rows_after=len(df),
            rows_dropped=drop_count,
            rows_modified=0,
            warnings=[f"Dropped {drop_count} malformed/split rows"] if drop_count > 0 else [],
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
