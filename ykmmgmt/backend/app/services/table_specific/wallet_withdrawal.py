"""Table-specific cleaning rules for 钱包提现操作 (wallet_withdrawals).

Issue: Extra trailing column(s) caused by commas in text fields (备注).
Data rows have 9 cols (vs 8 header), some have 10 cols (Row 6918).
The extra column(s) contain 备注 overflow text.
"""

import pandas as pd

from app.services.cleaning import CleaningReport, CleaningStepReport
from app.services.table_specific import register

# 钱包提现操作 header has 8 columns
_EXPECTED_COLS = 8


@register("wallet_withdrawals")
def fix_extra_trailing_column(df: pd.DataFrame, report: CleaningReport) -> tuple[pd.DataFrame, CleaningReport]:
    """Merge all extra trailing columns into preceding columns.

    Data rows typically have 9 cols (vs 8 header), sometimes 10.
    Extra columns come from commas in 备注 splitting the field.
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
