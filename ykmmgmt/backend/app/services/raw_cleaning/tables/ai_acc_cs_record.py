"""Profile: ai_acc_cs_record (客服记录表).

Native exports are xlsx (clean: no tab/newline/misalignment issues) —
the common layer's value normalization (None→"", str→strip,
datetime→string, integral float→int) is all that is needed. Uploads may
also arrive as .csv (standard or non-standard): read_table_rows
dispatches on the file extension, and the hand CSV parser handles both
correctly, so the same profile works for either format.
"""

import pandas as pd

from ..common import align_by_name, read_table_rows

TABLE = "ai_acc_cs_record"
HEADER = [
    "问题大类", "问题类型", "设备号", "方案", "操作时间", "操作人", "发送内容",
    "说明", "执行结果说明", "用户是否接受", "咨询时间", "问题类型创建时间", "最后咨询时间",
]


def clean_file(file) -> pd.DataFrame:
    """Cleanse one file → canonical-header DataFrame. Idempotent on
    already-cleansed standard CSV re-import."""
    header, rows = read_table_rows(file)
    clean = [align_by_name(header, r, HEADER) for r in rows]
    return pd.DataFrame(clean, columns=HEADER)
