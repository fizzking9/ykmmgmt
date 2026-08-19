"""drop legacy business tables and their dependent objects

Phase 11 — Legacy Business Table Removal & System Reset.

Drops the three hardcoded business tables (refund_orders,
service_refund_work_orders, wallet_withdrawals) and hard-deletes every
dependent object that references them: saved views/visualizations/
dashboards, import history (datasources + import_jobs), and orphaned
column_meta/table_meta rows.

Revision ID: b7d3e9a14f25
Revises: 9b719a1765ae
Create Date: 2026-08-19 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7d3e9a14f25"
down_revision: str | Sequence[str] | None = "9b719a1765ae"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # ── Saved views / visualizations / dashboards referencing the tables ──
    # Views matched by generated_sql or config_json are removed; their
    # visualizations go with them. Dashboards embedding a removed
    # visualization id (or a table name) are removed too, so no tile can
    # dangle.
    op.execute(
        sa.text(
            r"""
            DO $$
            DECLARE
                table_re text := '\y(refund_orders|service_refund_work_orders|wallet_withdrawals)\y';
            BEGIN
                CREATE TEMP TABLE _legacy_views AS
                    SELECT id FROM views
                    WHERE COALESCE(generated_sql, '') ~ table_re
                       OR config_json::text ~ table_re;

                CREATE TEMP TABLE _legacy_viz AS
                    SELECT id FROM visualizations
                    WHERE config_json::text ~ table_re
                       OR view_id IN (SELECT id FROM _legacy_views);

                DELETE FROM dashboards
                WHERE layout_json::text ~ table_re
                   OR EXISTS (
                       SELECT 1 FROM _legacy_viz v
                       WHERE dashboards.layout_json::text LIKE '%' || v.id || '%'
                   );

                DELETE FROM visualizations WHERE id IN (SELECT id FROM _legacy_viz);
                DELETE FROM views WHERE id IN (SELECT id FROM _legacy_views);
            END $$;
            """
        )
    )

    # ── Import history tied to the legacy tables ──
    # Seed datasources were named 退费单/服务退款工单/钱包提现操作; UI uploads
    # append 导入. Remove their jobs first (FK has no CASCADE).
    op.execute(
        sa.text(
            r"""
            DELETE FROM import_jobs
            WHERE source_id IN (
                SELECT id FROM datasources
                WHERE name ~ '^(退费单|服务退款工单|钱包提现操作)(导入)?$'
            )
            """
        )
    )
    op.execute(sa.text(r"DELETE FROM datasources WHERE name ~ '^(退费单|服务退款工单|钱包提现操作)(导入)?$'"))

    # ── Orphaned metadata rows ──
    # column_meta/table_meta are created lazily at runtime and may not
    # exist on every database, so guard both deletes.
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF to_regclass('column_meta') IS NOT NULL THEN
                    DELETE FROM column_meta
                    WHERE table_name IN ('refund_orders', 'service_refund_work_orders', 'wallet_withdrawals');
                END IF;
                IF to_regclass('table_meta') IS NOT NULL THEN
                    DELETE FROM table_meta
                    WHERE table_name IN ('refund_orders', 'service_refund_work_orders', 'wallet_withdrawals');
                END IF;
            END $$;
            """
        )
    )

    # ── Drop the tables themselves ──
    op.drop_table("wallet_withdrawals")
    op.drop_table("service_refund_work_orders")
    op.drop_table("refund_orders")


def downgrade() -> None:
    """Downgrade schema.

    Recreates the three tables in their final pre-removal shape. Deleted
    data and dependent saved objects are not restored.
    """
    op.create_table(
        "wallet_withdrawals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("account_id", sa.String(length=100), nullable=True, comment="账户ID"),
        sa.Column("wallet_balance", sa.Numeric(precision=12, scale=2), nullable=True, comment="钱包余额"),
        sa.Column("sn", sa.String(length=100), nullable=True, comment="SN"),
        sa.Column("operation_type", sa.String(length=100), nullable=True, comment="操作类型"),
        sa.Column("operation_amount", sa.Numeric(precision=12, scale=2), nullable=True, comment="操作金额"),
        sa.Column("remark", sa.Text(), nullable=True, comment="备注"),
        sa.Column("operated_at", sa.DateTime(), nullable=True, comment="操作时间"),
        sa.Column("operator", sa.String(length=100), nullable=True, comment="操作人员"),
        sa.Column("imported_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False, comment="导入时间"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "service_refund_work_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("work_order_no", sa.String(length=100), nullable=False, comment="工单号"),
        sa.Column("sn", sa.String(length=100), nullable=True, comment="SN"),
        sa.Column("device_type", sa.String(length=100), nullable=True, comment="设备类型"),
        sa.Column("device_type_remark", sa.Text(), nullable=True, comment="设备类型备注"),
        sa.Column("phone", sa.String(length=50), nullable=True, comment="手机号"),
        sa.Column("service_category", sa.String(length=100), nullable=True, comment="服务类别"),
        sa.Column("service_item", sa.String(length=200), nullable=True, comment="服务项"),
        sa.Column("priority", sa.Integer(), nullable=True, comment="优先级"),
        sa.Column("status", sa.String(length=50), nullable=True, comment="状态"),
        sa.Column("customer_remark", sa.Text(), nullable=True, comment="备注（用户）"),
        sa.Column("registered_at", sa.DateTime(), nullable=True, comment="登记时间"),
        sa.Column("activated_at", sa.DateTime(), nullable=True, comment="激活时间"),
        sa.Column("dispatched_at", sa.DateTime(), nullable=True, comment="分发时间"),
        sa.Column("completed_at", sa.DateTime(), nullable=True, comment="完成时间"),
        sa.Column("processing_duration", sa.Integer(), nullable=True, comment="处理时长"),
        sa.Column("registrar", sa.String(length=100), nullable=True, comment="登记人"),
        sa.Column("channel", sa.String(length=100), nullable=True, comment="录入渠道"),
        sa.Column("processing_node", sa.String(length=100), nullable=True, comment="处理节点"),
        sa.Column("processor", sa.String(length=100), nullable=True, comment="处理人"),
        sa.Column("processing_opinion", sa.Text(), nullable=True, comment="处理意见"),
        sa.Column("is_appeal", sa.String(length=50), nullable=True, comment="是否申诉"),
        sa.Column("order_no", sa.String(length=100), nullable=True, comment="订单编号"),
        sa.Column("bank_name", sa.String(length=200), nullable=True, comment="收款开户行"),
        sa.Column("bank_card_no", sa.String(length=100), nullable=True, comment="银行卡号"),
        sa.Column("recipient", sa.String(length=100), nullable=True, comment="收件人"),
        sa.Column("internal_remark", sa.Text(), nullable=True, comment="备注（内部）"),
        sa.Column("refund_amount", sa.Numeric(precision=12, scale=2), nullable=True, comment="退款金额"),
        sa.Column(
            "estimated_refundable_amount", sa.Numeric(precision=12, scale=2), nullable=True, comment="预估可退金额"
        ),
        sa.Column("imported_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False, comment="导入时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_order_no"),
    )
    op.create_table(
        "refund_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False, comment="主键ID"),
        sa.Column("refund_order_no", sa.String(length=100), nullable=False, comment="退费单号"),
        sa.Column("platform_order_no", sa.String(length=100), nullable=True, comment="平台订单号"),
        sa.Column("third_party_order_no", sa.String(length=100), nullable=True, comment="三方订单号"),
        sa.Column("device_sn", sa.String(length=100), nullable=True, comment="设备SN"),
        sa.Column("refund_reason", sa.String(length=200), nullable=True, comment="退费原因"),
        sa.Column("plan_name", sa.String(length=200), nullable=True, comment="套餐名称"),
        sa.Column("merchant_name", sa.String(length=200), nullable=True, comment="商户名称"),
        sa.Column("refund_amount", sa.Numeric(precision=12, scale=2), nullable=True, comment="退费金额"),
        sa.Column("actual_refund_amount", sa.Numeric(precision=12, scale=2), nullable=True, comment="实退金额"),
        sa.Column("remark", sa.Text(), nullable=True, comment="备注"),
        sa.Column("status", sa.String(length=50), nullable=True, comment="状态"),
        sa.Column("refund_method", sa.String(length=100), nullable=True, comment="退款方式"),
        sa.Column("audit_remark", sa.Text(), nullable=True, comment="审核备注"),
        sa.Column("auditor", sa.String(length=100), nullable=True, comment="审核人"),
        sa.Column("record_created_at", sa.DateTime(), nullable=True, comment="创建时间（原始记录）"),
        sa.Column("record_updated_at", sa.DateTime(), nullable=True, comment="更新时间（原始记录）"),
        sa.Column("operator", sa.String(length=100), nullable=True, comment="操作人"),
        sa.Column("plan_price", sa.Numeric(precision=12, scale=2), nullable=True, comment="套餐价格"),
        sa.Column("imported_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False, comment="导入时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refund_order_no"),
    )
