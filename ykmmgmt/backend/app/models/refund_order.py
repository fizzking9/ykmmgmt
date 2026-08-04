import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RefundOrder(Base):
    __tablename__ = "refund_orders"
    __upsert_key__ = ["refund_order_no"]

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    refund_order_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, comment="退费单号")
    platform_order_no: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="平台订单号")
    third_party_order_no: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="三方订单号")
    device_sn: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="设备SN")
    refund_reason: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="退费原因")
    plan_name: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="套餐名称")
    merchant_name: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="商户名称")
    refund_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True, comment="退费金额")
    actual_refund_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True, comment="实退金额")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")
    status: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="状态")
    refund_method: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="退款方式")
    audit_remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="审核备注")
    auditor: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="审核人")
    record_created_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True, comment="创建时间"
    )
    record_updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True, comment="更新时间"
    )
    operator: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="操作人")
    plan_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True, comment="套餐价格")
    imported_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), comment="导入时间")
