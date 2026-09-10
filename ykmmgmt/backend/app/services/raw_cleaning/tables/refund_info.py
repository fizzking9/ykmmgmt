"""Profile: 退款单信息 (refund_info).

Native exports are xlsx (clean: no tab/newline/misalignment issues) —
the common layer's value normalization is all that is needed. Uploads
may also arrive as .csv (standard or non-standard): read_table_rows
dispatches on the file extension, and the hand CSV parser handles both
correctly, so the same profile works for either format. Note:
实际支付金额 is entirely empty in the source (never collected) — kept
as empty values. Occasionally an export file is actually an API-500
JSON body (corrupt); those fail parsing and are reported by the caller.
"""

import pandas as pd

from ..common import align_by_name, read_table_rows

TABLE = "退款单信息"
HEADER = [
    "退费单号", "订单号", "手机号码", "套餐名称", "实际支付金额", "申请退款金额", "退款金额",
    "退款原因", "退款状态", "退款方式", "审核人名称", "审核时间", "审核备注", "申请备注",
]


def clean_file(file) -> pd.DataFrame:
    """Cleanse one file → canonical-header DataFrame. Idempotent on
    already-cleansed standard CSV re-import."""
    header, rows = read_table_rows(file)
    clean = [align_by_name(header, r, HEADER) for r in rows]
    return pd.DataFrame(clean, columns=HEADER)
