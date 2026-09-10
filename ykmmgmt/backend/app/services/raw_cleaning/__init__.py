"""Raw business-source cleansing pipeline (stage 0 of data import).

The business operation system exports raw data as "non-standard CSV"
(bare-LF field newlines, unescaped JSON, trailing tabs, a trailing extra
comma, commas inside free-text fields, whole-file column shifts, column
evolution). A standard parser misreads those files, so this module
re-parses them with the correct, deterministic rules before the generic
import pipeline takes over.

Layering (mirrors the source-analysis design):

  common cleansing (common.py — shared by all tables)
      CRLF/LF physical-line split · hand CSV parse · strip ·
      trailing-empty drop · unified xlsx/csv reading · by-name alignment
        │
  table profile cleansing (tables/*.py — per-table rules)
      服务工单列表: brace-matched JSON extraction + 22/23 column evolution
      退费单导出列表: comma repair (enum split) + whole-file shift detection
      others: by-name alignment only
        │
  output: pandas DataFrame with the table's canonical (Chinese) headers —
  ready for the generic pipeline's header-validation / mapping / upsert.

Dispatch is header-based: the uploaded file's header row is matched
against the registered profiles (exact set match, then signature
overlap). Files that match no profile are returned untouched so
non-business and already-standard files flow through unchanged.

All operations are idempotent: re-cleansing an already-cleansed file
(standard CSV, canonical headers) yields the identical result.
"""

from pathlib import Path

from app.services.parsers import parse_file

from . import tables
from .common import iter_xlsx_rows, parse_csv_line, read_physical_lines


class RawCleanError(ValueError):
    """Raised when a raw file matches a profile but cannot be cleansed
    (e.g. a corrupt export that is actually an API error body)."""


def _read_header_row(filepath: Path) -> list[str]:
    """Read just the header row of a csv/xlsx file for profile matching."""
    if filepath.suffix.lower() in (".xlsx", ".xlsm"):
        for row in iter_xlsx_rows(filepath):
            return row
        return []
    lines = read_physical_lines(filepath)
    if not lines:
        return []
    return [x.strip() for x in parse_csv_line(lines[0])]


def parse_with_profile(filepath: Path | str):
    """Parse a data file, applying the business-source cleanse when the
    file's headers match a known profile.

    Returns (df, raw_headers, profile_name):
      df           — cleansed DataFrame (canonical Chinese headers when a
                     profile matched; standard parse output otherwise)
      raw_headers  — the canonical headers when a profile matched, else
                     the file's own headers
      profile_name — the matched table name, or None

    Raises RawCleanError when a matched file cannot be cleansed.
    """
    filepath = Path(filepath)

    try:
        headers = _read_header_row(filepath)
    except RawCleanError:
        raise
    except Exception as e:  # unreadable/corrupt file — let the caller report it
        raise RawCleanError(f"文件无法读取，可能已损坏: {e}") from e

    profile = tables.match_profile(headers) if headers else None
    if profile is None:
        df, raw_headers = parse_file(filepath)
        return df, raw_headers, None

    try:
        df = profile.clean_file(filepath)
    except RawCleanError:
        raise
    except Exception as e:
        raise RawCleanError(f"原始文件清洗失败（{profile.TABLE}）: {e}") from e
    return df, list(profile.HEADER), profile.TABLE


__all__ = ["RawCleanError", "parse_with_profile", "tables"]
