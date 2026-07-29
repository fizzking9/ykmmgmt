"""CSV and Excel file parsers.

Both parsers produce a pandas DataFrame. CSV parsing includes encoding
detection and handling of embedded delimiters in text fields.
"""

import csv
import io
from pathlib import Path

import pandas as pd


def detect_encoding(filepath: Path | str, sample_bytes: int = 4096) -> str:
    """Detect file encoding. Tries common Chinese encodings first."""
    encodings = ["utf-8-sig", "utf-8", "gbk", "gb2312", "gb18030", "latin-1"]

    for enc in encodings:
        try:
            with open(filepath, encoding=enc) as f:
                f.read(sample_bytes)
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue

    return "utf-8-sig"  # fallback


def parse_csv(filepath: Path | str) -> tuple[pd.DataFrame, list[str]]:
    """Parse a CSV file into a DataFrame.

    Returns (dataframe, raw_headers).

    Handles:
    - Tab characters in fields (stripped before parsing)
    - Encoding auto-detection
    """
    filepath = Path(filepath)
    encoding = detect_encoding(filepath)

    with open(filepath, encoding=encoding) as f:
        content = f.read().replace("\t", "")

    reader = csv.reader(io.StringIO(content))
    raw_headers = next(reader)
    raw_headers = [h.strip() for h in raw_headers]

    rows = [row for row in reader if any(cell.strip() for cell in row)]

    # Use the header length as the expected column count
    expected_cols = len(raw_headers)
    max_cols = max(expected_cols, max((len(r) for r in rows), default=0))

    # Pad column names if data has more columns than header
    all_headers = list(raw_headers)
    for i in range(expected_cols, max_cols):
        all_headers.append(f"_extra_{i}")

    df = pd.DataFrame(rows, columns=all_headers)

    return df, raw_headers


def parse_excel(filepath: Path | str, sheet_name: str | int = 0) -> tuple[pd.DataFrame, list[str]]:
    """Parse an Excel file into a DataFrame.

    Returns (dataframe, raw_headers).
    """
    filepath = Path(filepath)
    df = pd.read_excel(filepath, sheet_name=sheet_name, dtype=str)
    raw_headers = [str(h).strip() for h in df.columns.tolist()]
    df.columns = raw_headers
    return df, raw_headers


def parse_file(filepath: Path | str) -> tuple[pd.DataFrame, list[str]]:
    """Auto-detect file type and parse into a DataFrame.

    Returns (dataframe, raw_headers).
    """
    filepath = Path(filepath)
    suffix = filepath.suffix.lower()

    if suffix == ".csv":
        return parse_csv(filepath)
    elif suffix in (".xlsx", ".xls"):
        return parse_excel(filepath)
    else:
        raise ValueError(f"Unsupported file format: {suffix}. Supported: .csv, .xlsx")
