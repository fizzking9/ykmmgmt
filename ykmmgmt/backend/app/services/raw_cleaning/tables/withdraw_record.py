"""Profile: 提现操作记录 (withdraw_record, csv source).

No special structure — common CSV cleanse (line split, hand parse, strip
trailing tabs, drop trailing empty field) + align by column name.
"""

import pandas as pd

from ..common import align_by_name, read_csv_rows

TABLE = "提现操作记录"
HEADER = ["账户ID", "钱包余额", "SN", "操作类型", "操作金额", "备注", "操作时间", "操作人员"]


def clean_file(file) -> pd.DataFrame:
    """Cleanse one file → canonical-header DataFrame."""
    header, rows = read_csv_rows(file)
    clean = [align_by_name(header, r, HEADER) for r in rows]
    return pd.DataFrame(clean, columns=HEADER)
