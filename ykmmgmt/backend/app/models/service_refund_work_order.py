import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ServiceRefundWorkOrder(Base):
    __tablename__ = "service_refund_work_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    work_order_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, comment="工单号")
    sn: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="SN")
    device_type: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="设备类型")
    device_type_remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="设备类型备注")
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="手机号")
    service_category: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="服务类别")
    service_item: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="服务项")
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="优先级")
    status: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="状态")
    customer_remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注（用户）")
    registered_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True, comment="登记时间")
    activated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True, comment="激活时间")
    dispatched_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True, comment="分发时间")
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True, comment="完成时间")
    processing_duration: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="处理时长")
    registrar: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="登记人")
    channel: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="录入渠道")
    processing_node: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="处理节点")
    processor: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="处理人")
    processing_opinion: Mapped[str | None] = mapped_column(Text, nullable=True, comment="处理意见")
    is_appeal: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="是否申诉")
    order_no: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="订单编号")
    bank_name: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="收款开户行")
    bank_card_no: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="银行卡号")
    recipient: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="收件人")
    internal_remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注（内部）")
    refund_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True, comment="退款金额")
    estimated_refundable_amount: Mapped[float | None] = mapped_column(
        Numeric(12, 2), nullable=True, comment="预估可退金额"
    )
    imported_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), comment="导入时间")
