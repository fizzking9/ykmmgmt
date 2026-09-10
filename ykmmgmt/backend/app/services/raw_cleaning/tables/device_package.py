"""Profile: 设备套餐列表 (device_package, csv source).

No special structure — common CSV cleanse (13 fields carry trailing tabs,
all removed by strip) + align by column name.
"""

import pandas as pd

from ..common import align_by_name, read_csv_rows

TABLE = "设备套餐列表"
HEADER = [
    "设备SN", "套餐名称", "套餐类型", "流量类型", "商户名称", "实际支付金额", "开始日期",
    "结束日期", "更新时间", "创建时间", "套餐有效天数", "创建人", "充值订单号",
    "可用流量", "已用流量", "剩余流量", "当前状态",
]


def clean_file(file) -> pd.DataFrame:
    """Cleanse one file → canonical-header DataFrame."""
    header, rows = read_csv_rows(file)
    clean = [align_by_name(header, r, HEADER) for r in rows]
    return pd.DataFrame(clean, columns=HEADER)
