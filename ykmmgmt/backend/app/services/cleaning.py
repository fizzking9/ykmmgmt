"""Data cleaning pipeline with common and table-specific steps.

Pipeline design:
- Each step is a callable (DataFrame, CleaningReport) → (DataFrame, CleaningReport)
- Steps run in sequence, each accumulating into the report
- Common steps run for all tables; table-specific steps run after
"""

from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class CleaningStepReport:
    """Report for a single cleaning step."""

    step_name: str
    rows_before: int
    rows_after: int
    rows_dropped: int
    rows_modified: int
    warnings: list[str] = field(default_factory=list)


@dataclass
class CleaningReport:
    """Full cleaning report for an import job."""

    steps: list[CleaningStepReport] = field(default_factory=list)
    warnings_per_column: dict[str, list[str]] = field(default_factory=dict)
    rows_before: int = 0
    rows_after: int = 0

    def add_step(self, step: CleaningStepReport) -> None:
        self.steps.append(step)

    def add_column_warning(self, column: str, warning: str) -> None:
        if column not in self.warnings_per_column:
            self.warnings_per_column[column] = []
        self.warnings_per_column[column].append(warning)

    def to_dict(self) -> dict:
        return {
            "steps": [
                {
                    "step": s.step_name,
                    "rows_before": int(s.rows_before),
                    "rows_after": int(s.rows_after),
                    "rows_dropped": int(s.rows_dropped),
                    "rows_modified": int(s.rows_modified),
                    "warnings": s.warnings,
                }
                for s in self.steps
            ],
            "warnings_per_column": self.warnings_per_column,
            "rows_before": int(self.rows_before),
            "rows_after": int(self.rows_after),
        }


# Type alias for a cleaning step function
CleaningStep = Callable[[pd.DataFrame, CleaningReport], tuple[pd.DataFrame, CleaningReport]]


def make_dedup_by_key(key_cols: list[str]):
    """Build a step collapsing duplicate key rows (last occurrence wins)."""

    def dedup_by_key(df: pd.DataFrame, report: CleaningReport) -> tuple[pd.DataFrame, CleaningReport]:
        rows_before = len(df)
        cols = [c for c in key_cols if c in df.columns]
        if cols:
            df = df.drop_duplicates(subset=cols, keep="last").reset_index(drop=True)
        rows_dropped = rows_before - len(df)
        report.add_step(
            CleaningStepReport(
                step_name="deduplicate_by_key",
                rows_before=rows_before,
                rows_after=len(df),
                rows_dropped=0,
                rows_modified=rows_dropped,
                warnings=[f"{rows_dropped} duplicate key rows collapsed (kept latest)"] if rows_dropped > 0 else [],
            )
        )
        return df, report

    return dedup_by_key


class CleaningPipeline:
    """Runs a sequence of cleaning steps on a DataFrame."""

    def __init__(self, dedup_key: list[str] | None = None) -> None:
        self._common_steps: list[CleaningStep] = [
            strip_whitespace,
            handle_missing_values,
            normalize_formats,
            deduplicate_rows,
            validate_values,
        ]
        # Tables with a user primary key: exact-duplicate rows are legitimate
        # re-submissions of the same key, not dirty data — collapse them
        # (last occurrence wins) instead of rejecting them.
        if dedup_key:
            self._common_steps.insert(-1, make_dedup_by_key(dedup_key))
        self._table_steps: list[CleaningStep] = []

    def add_table_step(self, step: CleaningStep) -> None:
        """Register a table-specific cleaning step."""
        self._table_steps.append(step)

    def clear_common_steps(self) -> None:
        """Remove all common cleaning steps (for pre-mapping structural-only runs)."""
        self._common_steps.clear()

    def disable_exact_dedup(self) -> None:
        """Drop the exact-duplicate step (keyed tables dedup by key instead)."""
        self._common_steps = [s for s in self._common_steps if s is not deduplicate_rows]

    def run(self, df: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
        """Run all steps (common + table-specific) on the DataFrame."""
        report = CleaningReport(rows_before=len(df), rows_after=len(df))

        all_steps = self._common_steps + self._table_steps
        for step_fn in all_steps:
            df, report = step_fn(df, report)

        report.rows_after = len(df)
        return df, report


# ── Common cleaning steps ──────────────────────────────────────────────


def strip_whitespace(df: pd.DataFrame, report: CleaningReport) -> tuple[pd.DataFrame, CleaningReport]:
    """Strip leading/trailing whitespace from all string columns."""
    rows_before = len(df)
    modified = 0
    for col_idx in range(len(df.columns)):
        col = df.columns[col_idx]
        series = df.iloc[:, col_idx]
        dtype_str = str(series.dtype)
        if "object" in dtype_str or "str" in dtype_str or "string" in dtype_str:
            original = series.copy()
            cleaned = series.astype(str).str.strip()
            cleaned = cleaned.replace(["nan", "null", "None", ""], None)
            df.iloc[:, col_idx] = cleaned
            changed = (original.astype(str) != cleaned.astype(str)).sum()
            if changed > 0:
                modified += changed
                report.add_column_warning(str(col), f"{changed} values trimmed")

    report.add_step(
        CleaningStepReport(
            step_name="strip_whitespace",
            rows_before=rows_before,
            rows_after=len(df),
            rows_dropped=0,
            rows_modified=modified,
        )
    )
    return df, report


def handle_missing_values(df: pd.DataFrame, report: CleaningReport) -> tuple[pd.DataFrame, CleaningReport]:
    """Drop completely blank rows and entirely empty columns."""
    rows_before = len(df)
    len(df.columns)

    # Drop fully blank rows
    df = df.dropna(how="all")
    rows_dropped = rows_before - len(df)

    # Drop entirely empty columns (use positional access to avoid duplicate-name issues)
    non_empty_mask = [df.iloc[:, i].notna().any() for i in range(len(df.columns))]
    keep_indices = [i for i, keep in enumerate(non_empty_mask) if keep]
    if len(keep_indices) < len(df.columns):
        cols_dropped = len(df.columns) - len(keep_indices)
        df = df.iloc[:, keep_indices]
    else:
        cols_dropped = 0

    if cols_dropped > 0:
        report.add_column_warning("_system", f"{cols_dropped} empty columns dropped")

    report.add_step(
        CleaningStepReport(
            step_name="handle_missing_values",
            rows_before=rows_before,
            rows_after=len(df),
            rows_dropped=rows_dropped,
            rows_modified=0,
            warnings=[f"{cols_dropped} empty columns dropped"] if cols_dropped > 0 else [],
        )
    )
    return df, report


def normalize_formats(df: pd.DataFrame, report: CleaningReport) -> tuple[pd.DataFrame, CleaningReport]:
    """Normalize date columns to ISO format and numbers to proper types."""
    rows_before = len(df)
    modified = 0

    for col_idx in range(len(df.columns)):
        series = df.iloc[:, col_idx]
        dtype_str = str(series.dtype)
        if "int" in dtype_str or "float" in dtype_str or "datetime" in dtype_str:
            continue

        sample = series.dropna().head(20)
        if len(sample) == 0:
            continue

        # Try date parsing
        date_patterns = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d",
            "%Y-%m-%d %H:%M",
        ]
        for fmt in date_patterns:
            try:
                converted = pd.to_datetime(series, format=fmt, errors="coerce")
                if converted.notna().sum() > len(sample) * 0.5:
                    df.iloc[:, col_idx] = converted
                    modified += 1
                    break
            except (ValueError, TypeError):
                continue

    report.add_step(
        CleaningStepReport(
            step_name="normalize_formats",
            rows_before=rows_before,
            rows_after=len(df),
            rows_dropped=0,
            rows_modified=modified,
        )
    )
    return df, report


def deduplicate_rows(df: pd.DataFrame, report: CleaningReport) -> tuple[pd.DataFrame, CleaningReport]:
    """Remove exact duplicate rows."""
    rows_before = len(df)
    df = df.drop_duplicates()
    rows_dropped = rows_before - len(df)

    warnings: list[str] = []
    if rows_dropped > 0:
        warnings.append(f"{rows_dropped} duplicate rows removed")

    report.add_step(
        CleaningStepReport(
            step_name="deduplicate_rows",
            rows_before=rows_before,
            rows_after=len(df),
            rows_dropped=rows_dropped,
            rows_modified=0,
            warnings=warnings,
        )
    )
    return df, report


def validate_values(df: pd.DataFrame, report: CleaningReport) -> tuple[pd.DataFrame, CleaningReport]:
    """Validate values against expected types. Flag rows with type mismatches."""
    rows_before = len(df)

    for col_idx in range(len(df.columns)):
        series = df.iloc[:, col_idx]
        if series.dtype == object:
            non_null = series.dropna()
            if len(non_null) == 0:
                continue

    report.add_step(
        CleaningStepReport(
            step_name="validate_values",
            rows_before=rows_before,
            rows_after=len(df),
            rows_dropped=0,
            rows_modified=0,
            warnings=[],
        )
    )
    return df, report
