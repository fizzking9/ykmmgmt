"""Business-source table profiles and the profile registry.

Each module defines a canonical HEADER (the standard column superset for
that table) and a clean_file() that re-parses one raw export file into a
canonical-header DataFrame. The registry exposes the profiles so the
dispatcher can match an uploaded file to its profile by header.
"""

from . import (
    ai_acc_cs_record,
    device_package,
    device_tag,
    refund_export,
    refund_info,
    service_order,
    withdraw_record,
)

# Canonical table name → profile module
_TABLES = {
    ai_acc_cs_record.TABLE: ai_acc_cs_record,
    refund_info.TABLE: refund_info,
    withdraw_record.TABLE: withdraw_record,
    device_package.TABLE: device_package,
    device_tag.TABLE: device_tag,
    service_order.TABLE: service_order,
    refund_export.TABLE: refund_export,
}

# Short aliases → canonical table name
_ALIASES = {
    "ai_acc_cs_record": ai_acc_cs_record.TABLE,
    "客服记录": ai_acc_cs_record.TABLE,
    "acc_record": ai_acc_cs_record.TABLE,
    "refund_info": refund_info.TABLE,
    "退款单": refund_info.TABLE,
    "withdraw_record": withdraw_record.TABLE,
    "提现": withdraw_record.TABLE,
    "device_package": device_package.TABLE,
    "套餐": device_package.TABLE,
    "device_tag": device_tag.TABLE,
    "标签": device_tag.TABLE,
    "service_order": service_order.TABLE,
    "工单": service_order.TABLE,
    "服务工单": service_order.TABLE,
    "refund_export": refund_export.TABLE,
    "退费单": refund_export.TABLE,
    "退费": refund_export.TABLE,
}

# Distinctive column names per profile for header-based matching. A short
# signature set (≥2 columns unique to that table) keeps matching decisive
# even when an export carries a subset of the canonical columns.
_MATCH_KEYS = {
    ai_acc_cs_record.TABLE: {"问题大类", "问题类型", "设备号", "方案", "发送内容", "执行结果说明"},
    refund_info.TABLE: {"手机号码", "申请退款金额", "退款状态", "审核人名称", "申请备注"},
    withdraw_record.TABLE: {"账户ID", "钱包余额", "操作金额", "操作人员"},
    device_package.TABLE: {"套餐类型", "流量类型", "套餐有效天数", "充值订单号", "可用流量", "已用流量", "剩余流量"},
    device_tag.TABLE: {"标签名", "设备所属商户", "设备当前套餐"},
    service_order.TABLE: {"工单号", "服务类别", "处理时长", "登记人", "录入渠道", "处理节点", "是否申诉", "提交参数"},
    refund_export.TABLE: {"平台订单号", "三方订单号", "实退金额", "退款方式", "套餐价格"},
}


def available_tables() -> list[str]:
    """All canonical table names."""
    return sorted(_TABLES.keys())


def get_profile(table_name: str):
    """Resolve a table name (canonical or alias) → profile module, or None."""
    key = _ALIASES.get(table_name, table_name)
    return _TABLES.get(key)


def match_profile(headers: list[str]):
    """Match a raw file's headers to a business table profile.

    Strategy (first decisive hit wins):
      1. exact header-set match against a profile's canonical HEADER;
      2. best signature overlap: the profile whose distinctive columns
         cover the highest fraction of the file's headers, provided at
         least MIN_MATCH distinct signature columns are present.
    Returns the profile module, or None when no profile fits.
    """
    norm = {(h or "").strip() for h in headers if (h or "").strip()}

    # 1) Exact set match (covers cleansed re-uploads and full exports)
    for profile in _TABLES.values():
        if norm == set(profile.HEADER):
            return profile

    # 2) Signature overlap
    min_match = 2
    best = None
    best_score = 0.0
    for table, keys in _MATCH_KEYS.items():
        hits = norm & keys
        if len(hits) < min_match:
            continue
        score = len(hits) / len(keys)
        if score > best_score:
            best_score = score
            best = _TABLES[table]
    return best
