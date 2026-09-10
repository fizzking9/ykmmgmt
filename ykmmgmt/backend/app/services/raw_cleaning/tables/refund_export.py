"""Profile: 退费单导出列表 (refund_export, csv source).

Special handling on top of the common CSV cleanse:

  A1  newlines inside 备注 are bare LF → kept inside the field value by
      the CRLF physical-line split (handled in common.read_csv_rows);
  A5  备注/审核备注 occasionally contain half-width commas (fields inflate
      from 18 to 19/21) → anchor on the 9 fixed leading and 5 fixed
      trailing columns, split the middle by the short enum pair
      (状态 + 退款方式);
  A7  whole-file variant: exports of 「转入提现账户」-type records lack the
      退费单号 column entirely, shifting every column left by one.
      Detected file-wide (套餐价格 non-empty rate < 0.5 AND 设备SN
      pure-numeric rate < 0.5) → prepend an empty first column and shift
      everything back.

Idempotent: a cleansed standard-CSV file no longer satisfies the shift
detection (套餐价格 has values at index 17), so re-cleansing never
re-triggers the repair.
"""

import re

import pandas as pd

from ..common import align_by_name, read_csv_rows

TABLE = "退费单导出列表"
HEADER = [
    "退费单号", "平台订单号", "三方订单号", "设备SN", "退费原因", "套餐名称", "商户名称",
    "退费金额", "实退金额", "备注", "状态", "退款方式", "审核备注", "审核人",
    "创建时间", "更新时间", "操作人", "套餐价格",
]

NCOL = len(HEADER)
_SN = re.compile(r"^\d+$")  # 设备SN: pure digit string

# Short enum domains of 状态 / 退款方式 — used to locate the two columns
# inside a comma-inflated row.
_STATUS = {"已退款", "无需退款", "申请中", "驳回"}
_METHOD = {"线上", "线下", "转入提现账户"}


def _split_middle(mid: list[str]):
    """Split the middle segment: mid = [备注-parts..., 状态, 退款方式, 审核备注-parts...].

    备注 and 审核备注 are free text that may contain commas and thus be
    split into several segments; 状态 and 退款方式 are short enums. Locate
    the adjacent enum pair to find the split point and rejoin the text.
    Returns None when no enum pair is found (caller degrades).
    """
    for i in range(len(mid) - 1):
        if mid[i] in _STATUS and mid[i + 1] in _METHOD:
            remark = ",".join(mid[:i])
            audit = ",".join(mid[i + 2:])
            return remark, mid[i], mid[i + 1], audit
    return None


def _fix_remark(fields: list[str]) -> list[str]:
    """Repair rows where 备注 (index 9) or 审核备注 (index 12) contains
    half-width commas, inflating the field count beyond 18.

    Of the 18 columns only these two are free text; the rest never contain
    commas. So: the first 9 (退费单号~实退金额) and the last 5 (审核人~
    套餐价格) are positionally fixed, and the middle is split via the
    enum pair.
    """
    if len(fields) <= NCOL:
        return fields
    head = fields[:9]
    tail5 = fields[-5:]
    parts = _split_middle(fields[9:-5])
    if parts is not None:
        remark, status, method, audit = parts
        return head + [remark, status, method, audit] + tail5
    # Degrade: no enum pair found (unknown new enum value) — fall back to
    # the remark-only anchor (rejoin everything into 备注).
    return head + [",".join(fields[9:-8])] + fields[-8:]


def _is_shifted_variant(clean: list[list[str]]) -> bool:
    """File-wide detection of the 「missing 退费单号」 (whole-file left-shift)
    variant.

    Signature (after by-name alignment): 套餐价格 (index 17) is almost
    entirely empty and 设备SN (index 3) is almost never pure digits
    (it actually holds 退费原因 text). Normal files score ≈1 on both
    rates, shifted files ≈0 — the separation is clean.
    """
    n = len(clean)
    if n == 0:
        return False
    price_nonempty = sum(1 for row in clean if row[17] != "")
    sn_numeric = sum(1 for row in clean if _SN.match((row[3] or "").strip()))
    return price_nonempty / n < 0.5 and sn_numeric / n < 0.5


def clean_file(file) -> pd.DataFrame:
    header, rows = read_csv_rows(file)
    clean = []
    for r in rows:
        r = _fix_remark(r)
        while len(r) < NCOL:
            r.append("")
        clean.append(align_by_name(header, r[:NCOL], HEADER))

    # Missing-退费单号 variant: prepend an empty first column, shift back.
    if _is_shifted_variant(clean):
        clean = [[""] + row[:17] for row in clean]
    return pd.DataFrame(clean, columns=HEADER)
