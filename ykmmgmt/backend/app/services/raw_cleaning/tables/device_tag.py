"""Profile: 设备标签列表 (device_tag, csv source).

No special structure — common CSV cleanse (the 设备sn column carries
trailing tabs, removed by strip) + align by column name. The source
header is lowercase 「设备sn」 while other tables use 「设备SN」; alignment
is exact-match by name, unifying it is left to the import/table stage.
"""

import pandas as pd

from ..common import align_by_name, read_csv_rows

TABLE = "设备标签列表"
HEADER = ["设备sn", "标签名", "设备所属商户", "设备当前套餐", "创建人", "更新时间"]


def clean_file(file) -> pd.DataFrame:
    """Cleanse one file → canonical-header DataFrame."""
    header, rows = read_csv_rows(file)
    clean = [align_by_name(header, r, HEADER) for r in rows]
    return pd.DataFrame(clean, columns=HEADER)
