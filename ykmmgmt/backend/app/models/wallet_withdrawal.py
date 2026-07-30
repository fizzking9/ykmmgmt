import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WalletWithdrawal(Base):
    __tablename__ = "wallet_withdrawals"
    __upsert_key__: list[str] = []

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    account_id: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="账户ID")
    wallet_balance: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True, comment="钱包余额")
    sn: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="SN")
    operation_type: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="操作类型")
    operation_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True, comment="操作金额")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")
    operated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True, comment="操作时间")
    operator: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="操作人员")
    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="SHA-256 hash of business columns for dedup"
    )
    imported_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), comment="导入时间")

    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_wallet_withdrawal_content_hash"),
    )
