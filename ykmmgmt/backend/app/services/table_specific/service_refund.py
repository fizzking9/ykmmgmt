"""Table-specific cleaning rules for 服务退款工单 (service_refund_work_orders).

Issue: Extra trailing column(s) caused by commas in text fields (备注).
Most rows have 29 cols (vs 28 header), some have 30 cols (Row 358).
The extra column(s) contain 备注 overflow text or are empty (trailing comma).
"""

import pandas as pd

from app.services.cleaning import CleaningReport, CleaningStepReport
from app.services.table_specific import register

# 服务退款工单 header has 28 columns
_EXPECTED_COLS = 28


@register("service_refund_work_orders")
def fix_extra_trailing_column(df: pd.DataFrame, report: CleaningReport) -> tuple[pd.DataFrame, CleaningReport]:
    """Merge all extra trailing columns into preceding columns.

    Data rows typically have 29 cols (vs 28 header), sometimes 30.
    Extra columns come from commas in 备注/内部备注 splitting the field.
    Merge them back iteratively until we reach the expected column count.
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
