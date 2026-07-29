"""Table-specific cleaning rules for 退费单 (refund_orders).

Issues found in sample data:
1. Extra trailing column — data rows have 19 cols vs 18 header cols.
   The 备注 field contains commas, creating an extra column. In most rows
   the extra is empty (trailing comma artifact); in ~47 rows it contains
   real 备注 overflow text.
2. Split rows — 备注 contains embedded newlines, causing csv.reader to
   split one logical row into two physical rows (~10 cols each).
   Example: rows 3722-3726 — row 3722 is a full row whose 备注 overflows
   into row 3723 (10 cols), then rows 3724+3726 are a true split pair.

Fix strategy:
- Extra columns: merge all trailing extras into the second-to-last column
- Split rows: detect consecutive short rows and merge them; also merge
  short rows that follow a normal row (overflow case)
"""

import pandas as pd

from app.services.cleaning import CleaningReport, CleaningStepReport
from app.services.table_specific import register

# 退费单 header has 18 columns; data rows typically have 19
_EXPECTED_COLS = 18


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

    Split rows appear as consecutive rows with significantly fewer
    non-null columns (< 60% of expected). Three patterns:
    A) Normal row (N+ cols) → short row (overflow) → merge short into normal
    B) Short row → short row (true split pair) → merge both into one
    C) Short row → short row → short row → ... → merge all consecutive shorts
    """
    if len(df) <= 1:
        return df, report

    rows_before = len(df)
    short_threshold = max(2, int(len(df.columns) * 0.6))

    # Mark rows as "short" if they have fewer than threshold non-null columns
    col_counts = df.apply(lambda row: row.notna().sum(), axis=1)
    is_short = col_counts <= short_threshold

    merged_count = 0
    drop_indices: list[int] = []
    i = 0

    while i < len(df) - 1:
        if not is_short.iloc[i]:
            # Normal row — check if next row is short (Pattern A: overflow)
            if is_short.iloc[i + 1]:
                # Merge next row's content into current row
                current_row = df.iloc[i].copy()
                next_row = df.iloc[i + 1]
                for col_idx in range(len(df.columns)):
                    cv = current_row.iloc[col_idx]
                    nv = next_row.iloc[col_idx]
                    if pd.isna(cv) or str(cv).strip() == "":
                        if not pd.isna(nv) and str(nv).strip() != "":
                            current_row.iloc[col_idx] = nv
                df.iloc[i] = current_row
                drop_indices.append(i + 1)
                merged_count += 1
                i += 2
            else:
                i += 1
        else:
            # Short row — check for consecutive short rows (Pattern B/C)
            j = i + 1
            while j < len(df) and is_short.iloc[j]:
                j += 1
            short_count = j - i

            if short_count >= 2:
                # Merge all consecutive short rows into the first one
                merged_row = df.iloc[i].copy()
                for k in range(1, short_count):
                    next_row = df.iloc[i + k]
                    for col_idx in range(len(df.columns)):
                        mv = merged_row.iloc[col_idx]
                        nv = next_row.iloc[col_idx]
                        if pd.isna(mv) or str(mv).strip() == "":
                            if not pd.isna(nv) and str(nv).strip() != "":
                                merged_row.iloc[col_idx] = nv
                        elif not pd.isna(nv) and str(nv).strip() != "":
                            merged_row.iloc[col_idx] = str(mv) + " " + str(nv)
                df.iloc[i] = merged_row
                for k in range(1, short_count):
                    drop_indices.append(i + k)
                merged_count += short_count - 1
                i = j
            else:
                i += 1

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
