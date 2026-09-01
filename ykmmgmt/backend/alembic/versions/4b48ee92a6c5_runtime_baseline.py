"""runtime baseline (Schema Manager dynamic tables)

Revision ID: 4b48ee92a6c5
Revises: c2e7a1f84b03
Create Date: 2026-09-01 15:27:25.018725

Squash of 9 Schema Manager runtime migration(s) — see
scripts/squash_runtime_migrations.py. Regenerated, do not edit by hand.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "4b48ee92a6c5"
down_revision: Union[str, Sequence[str], None] = "c2e7a1f84b03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- d5e530a2a4c0: d5e530a2a4c0_create_table_ai_acc_cs_record.py ----
    """Upgrade schema."""
    op.create_table('ai_acc_cs_record',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='主键ID'),
    sa.Column('problem_category', sa.String(length=50), nullable=True, comment='问题大类'),
    sa.Column('problem_subcategory', sa.String(length=50), nullable=True, comment='问题类型'),
    sa.Column('device_sn', sa.String(length=255), nullable=True, comment='设备号'),
    sa.Column('solution', sa.String(length=50), nullable=True, comment='方案'),
    sa.Column('operation_time', sa.DateTime(), nullable=True, comment='操作时间'),
    sa.Column('operator', sa.String(length=50), nullable=True, comment='操作人'),
    sa.Column('message', sa.Text(), nullable=True, comment='发送内容'),
    sa.Column('comment', sa.Text(), nullable=True, comment='说明'),
    sa.Column('operation_result', sa.String(length=50), nullable=True, comment='执行结果说明'),
    sa.Column('whether_accept', sa.String(length=50), nullable=True, comment='用户是否接受'),
    sa.Column('consultation_time', sa.DateTime(), nullable=True, comment='咨询时间'),
    sa.Column('problem_cat_creation_time', sa.DateTime(), nullable=True, comment='问题类型创建时间'),
    sa.Column('last_consultation_time', sa.DateTime(), nullable=True, comment='最后咨询时间'),
    sa.Column('content_hash', sa.String(length=64), nullable=True, comment='内容哈希'),
    sa.Column('imported_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='导入时间'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('content_hash', name='uq_ai_acc_cs_record_content_hash'),
    if_not_exists=True,
    )
    op.execute("COMMENT ON TABLE ai_acc_cs_record IS 'ai客服记录'")

    # ---- 86fd5e76cf2d: 86fd5e76cf2d_create_table_service_order.py ----
    """Upgrade schema."""
    op.create_table('service_order',
    sa.Column('order_no', sa.String(length=50), autoincrement=False, nullable=False, comment='工单号'),
    sa.Column('device_sn', sa.String(length=50), nullable=True, comment='SN'),
    sa.Column('device_type', sa.String(length=50), nullable=True, comment='设备类型'),
    sa.Column('device_type_remark', sa.Text(), nullable=True, comment='设备类型备注'),
    sa.Column('phone', sa.String(length=50), nullable=True, comment='手机号'),
    sa.Column('service_category', sa.String(length=50), nullable=True, comment='服务类别'),
    sa.Column('service_item', sa.String(length=50), nullable=True, comment='服务项'),
    sa.Column('priority', sa.Integer(), nullable=True, comment='优先级'),
    sa.Column('status', sa.String(length=50), nullable=True, comment='状态'),
    sa.Column('remark', sa.Text(), nullable=True, comment='备注'),
    sa.Column('register_time', sa.DateTime(), nullable=True, comment='登记时间'),
    sa.Column('activate_time', sa.DateTime(), nullable=True, comment='激活时间'),
    sa.Column('dispatch_time', sa.DateTime(), nullable=True, comment='分发时间'),
    sa.Column('finish_time', sa.DateTime(), nullable=True, comment='完成时间'),
    sa.Column('duration', sa.Integer(), nullable=True, comment='处理时长'),
    sa.Column('registrar', sa.String(length=50), nullable=True, comment='登记人'),
    sa.Column('service_staff', sa.String(length=50), nullable=True, comment='服务人员'),
    sa.Column('entry_channel', sa.String(length=50), nullable=True, comment='录入渠道'),
    sa.Column('handle_node', sa.String(length=50), nullable=True, comment='处理节点'),
    sa.Column('handler', sa.String(length=50), nullable=True, comment='处理人'),
    sa.Column('handle_opinion', sa.Text(), nullable=True, comment='处理意见'),
    sa.Column('is_appealed', sa.String(length=50), nullable=True, comment='是否申诉'),
    sa.Column('submit_params', postgresql.JSON(), nullable=True, comment='提交参数'),
    sa.Column('imported_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='导入时间'),
    sa.PrimaryKeyConstraint('order_no'),
    if_not_exists=True,
    )
    op.execute("COMMENT ON TABLE service_order IS '服务工单列表'")

    # ---- b8b4594d4bba: b8b4594d4bba_create_table_device_tag.py ----
    """Upgrade schema."""
    op.create_table('device_tag',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='主键ID'),
    sa.Column('device_sn', sa.String(length=50), nullable=True, comment='设备sn'),
    sa.Column('tag_name', sa.String(length=50), nullable=True, comment='标签名'),
    sa.Column('merchant_name', sa.String(length=50), nullable=True, comment='设备所属商户'),
    sa.Column('current_package', sa.String(length=50), nullable=True, comment='设备当前套餐'),
    sa.Column('creator', sa.String(length=50), nullable=True, comment='创建人'),
    sa.Column('update_time', sa.DateTime(), nullable=True, comment='更新时间'),
    sa.Column('content_hash', sa.String(length=64), nullable=True, comment='内容哈希'),
    sa.Column('imported_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='导入时间'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('content_hash', name='uq_device_tag_content_hash'),
    if_not_exists=True,
    )
    op.execute("COMMENT ON TABLE device_tag IS '设备标签列表'")

    # ---- d7a9a9f4ffde: d7a9a9f4ffde_create_table_device_package.py ----
    """Upgrade schema."""
    op.create_table('device_package',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='主键ID'),
    sa.Column('device_sn', sa.String(length=50), nullable=True, comment='设备SN'),
    sa.Column('package_name', sa.String(length=50), nullable=True, comment='套餐名称'),
    sa.Column('package_type', sa.String(length=50), nullable=True, comment='套餐类型'),
    sa.Column('data_plan_type', sa.String(length=50), nullable=True, comment='流量类型'),
    sa.Column('merchant_name', sa.String(length=50), nullable=True, comment='商户名称'),
    sa.Column('paid_amount', sa.Numeric(precision=12, scale=2), nullable=True, comment='实际支付金额'),
    sa.Column('start_date', sa.DateTime(), nullable=True, comment='开始日期'),
    sa.Column('end_date', sa.DateTime(), nullable=True, comment='结束日期'),
    sa.Column('update_time', sa.DateTime(), nullable=True, comment='更新时间'),
    sa.Column('create_time', sa.DateTime(), nullable=True, comment='创建时间'),
    sa.Column('valid_days', sa.Integer(), nullable=True, comment='套餐有效天数'),
    sa.Column('creator', sa.String(length=50), nullable=True, comment='创建人'),
    sa.Column('recharge_order_no', sa.String(length=50), nullable=True, comment='充值订单号'),
    sa.Column('available_data', sa.BigInteger(), nullable=True, comment='可用流量'),
    sa.Column('used_data', sa.BigInteger(), nullable=True, comment='已用流量'),
    sa.Column('remaining_data', sa.BigInteger(), nullable=True, comment='剩余流量'),
    sa.Column('current_status', sa.String(length=50), nullable=True, comment='当前状态'),
    sa.Column('content_hash', sa.String(length=64), nullable=True, comment='内容哈希'),
    sa.Column('imported_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='导入时间'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('content_hash', name='uq_device_package_content_hash'),
    if_not_exists=True,
    )
    op.execute("COMMENT ON TABLE device_package IS '设备套餐列表'")

    # ---- 30cfa77fe178: 30cfa77fe178_create_table_stock_data.py ----
    """Upgrade schema."""
    op.create_table('stock_data',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='主键ID'),
    sa.Column('stock_code', sa.Integer(), nullable=True, comment='股票代码'),
    sa.Column('stock_name', sa.String(length=50), nullable=True, comment='股票名称'),
    sa.Column('industry', sa.String(length=50), nullable=True, comment='所属行业'),
    sa.Column('date', sa.Date(), nullable=True, comment='日期'),
    sa.Column('open', sa.Numeric(precision=12, scale=2), nullable=True, comment='开盘价'),
    sa.Column('high', sa.Numeric(precision=12, scale=2), nullable=True, comment='最高价'),
    sa.Column('low', sa.Numeric(precision=12, scale=2), nullable=True, comment='最低价'),
    sa.Column('close', sa.Numeric(precision=12, scale=2), nullable=True, comment='收盘价'),
    sa.Column('volume_lot', sa.Numeric(precision=12, scale=2), nullable=True, comment='成交量(手)'),
    sa.Column('volumn', sa.BigInteger(), nullable=True, comment='成交额(元)'),
    sa.Column('log_return', sa.Numeric(precision=12, scale=2), nullable=True, comment='收益率'),
    sa.Column('content_hash', sa.String(length=64), nullable=True, comment='内容哈希'),
    sa.Column('imported_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='导入时间'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('content_hash', name='uq_stock_data_content_hash'),
    if_not_exists=True,
    )
    op.execute("COMMENT ON TABLE stock_data IS '股票数据'")

    # ---- b36a75c74778: b36a75c74778_create_table_stock_fundamental.py ----
    """Upgrade schema."""
    op.create_table('stock_fundamental',
    sa.Column('stock_code', sa.Integer(), autoincrement=False, nullable=False, comment='股票代码'),
    sa.Column('stock_name', sa.String(length=50), nullable=True, comment='股票名称'),
    sa.Column('industry', sa.String(length=50), nullable=True, comment='所属行业'),
    sa.Column('pe_ttm', sa.Numeric(precision=12, scale=2), nullable=True, comment='市盈率PE_TTM'),
    sa.Column('pb', sa.Numeric(precision=12, scale=2), nullable=True, comment='市净率PB'),
    sa.Column('roe_pct', sa.Numeric(precision=12, scale=2), nullable=True, comment='净资产收益率ROE(%)'),
    sa.Column('market_cap', sa.Numeric(precision=12, scale=2), nullable=True, comment='总市值(亿元)'),
    sa.Column('net_profit', sa.Numeric(precision=12, scale=2), nullable=True, comment='净利润(亿元)'),
    sa.Column('update_date', sa.Date(), nullable=True, comment='更新日期'),
    sa.Column('imported_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='导入时间'),
    sa.PrimaryKeyConstraint('stock_code'),
    if_not_exists=True,
    )
    op.execute("COMMENT ON TABLE stock_fundamental IS '基本面数据'")

    # ---- e480c050b926: e480c050b926_alter_column_stock_data_stock_code.py ----
    """Upgrade schema."""
    op.alter_column('stock_data', 'stock_code',
        existing_type=sa.Integer(),
        type_=sa.String(length=50),
        nullable=True,
        existing_nullable=True,
        postgresql_using='stock_code::varchar')

    # ---- ed7b19b86219: ed7b19b86219_drop_table_stock_fundamental.py ----
    """Upgrade schema."""
    op.drop_table('stock_fundamental')

    # ---- 6e63b7aa8555: 6e63b7aa8555_create_table_stock_fundamental.py ----
    """Upgrade schema."""
    op.create_table('stock_fundamental',
    sa.Column('stock_code', sa.String(length=50), autoincrement=False, nullable=False, comment='股票代码'),
    sa.Column('stock_name', sa.String(length=50), nullable=True, comment='股票名称'),
    sa.Column('industry', sa.String(length=50), nullable=True, comment='所属行业'),
    sa.Column('pe_ttm', sa.Numeric(precision=12, scale=2), nullable=True, comment='市盈率PE_TTM'),
    sa.Column('pb', sa.Numeric(precision=12, scale=2), nullable=True, comment='市净率PB'),
    sa.Column('roe_pct', sa.Numeric(precision=12, scale=2), nullable=True, comment='净资产收益率ROE(%)'),
    sa.Column('market_cap', sa.Numeric(precision=12, scale=2), nullable=True, comment='总市值(亿元)'),
    sa.Column('net_profit', sa.Numeric(precision=12, scale=2), nullable=True, comment='净利润(亿元)'),
    sa.Column('update_date', sa.Date(), nullable=True, comment='更新日期'),
    sa.Column('imported_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='导入时间'),
    sa.PrimaryKeyConstraint('stock_code'),
    if_not_exists=True,
    )
    op.execute("COMMENT ON TABLE stock_fundamental IS '基本面'")


def downgrade() -> None:
    # ---- 6e63b7aa8555: 6e63b7aa8555_create_table_stock_fundamental.py ----
    """Downgrade schema."""
    op.drop_table('stock_fundamental')

    # ---- ed7b19b86219: ed7b19b86219_drop_table_stock_fundamental.py ----
    """Downgrade schema."""
    op.create_table('stock_fundamental',
    sa.Column('stock_code', sa.Integer(), autoincrement=False, nullable=False, comment='股票代码'),
    sa.Column('stock_name', sa.String(length=50), nullable=True, comment='股票名称'),
    sa.Column('industry', sa.String(length=50), nullable=True, comment='所属行业'),
    sa.Column('pe_ttm', sa.Numeric(precision=12, scale=2), nullable=True, comment='市盈率PE_TTM'),
    sa.Column('pb', sa.Numeric(precision=12, scale=2), nullable=True, comment='市净率PB'),
    sa.Column('roe_pct', sa.Numeric(precision=12, scale=2), nullable=True, comment='净资产收益率ROE(%)'),
    sa.Column('market_cap', sa.Numeric(precision=12, scale=2), nullable=True, comment='总市值(亿元)'),
    sa.Column('net_profit', sa.Numeric(precision=12, scale=2), nullable=True, comment='净利润(亿元)'),
    sa.Column('update_date', sa.Date(), nullable=True, comment='更新日期'),
    sa.Column('imported_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='导入时间'),
    sa.PrimaryKeyConstraint('stock_code'),
    if_not_exists=True,
    )
    op.execute("COMMENT ON TABLE stock_fundamental IS '基本面数据'")

    # ---- e480c050b926: e480c050b926_alter_column_stock_data_stock_code.py ----
    """Downgrade schema."""
    op.alter_column('stock_data', 'stock_code',
        existing_type=sa.String(length=50),
        type_=sa.Integer(),
        nullable=True,
        existing_nullable=True,
        postgresql_using='stock_code::integer')

    # ---- b36a75c74778: b36a75c74778_create_table_stock_fundamental.py ----
    """Downgrade schema."""
    op.drop_table('stock_fundamental')

    # ---- 30cfa77fe178: 30cfa77fe178_create_table_stock_data.py ----
    """Downgrade schema."""
    op.drop_table('stock_data')

    # ---- d7a9a9f4ffde: d7a9a9f4ffde_create_table_device_package.py ----
    """Downgrade schema."""
    op.drop_table('device_package')

    # ---- b8b4594d4bba: b8b4594d4bba_create_table_device_tag.py ----
    """Downgrade schema."""
    op.drop_table('device_tag')

    # ---- 86fd5e76cf2d: 86fd5e76cf2d_create_table_service_order.py ----
    """Downgrade schema."""
    op.drop_table('service_order')

    # ---- d5e530a2a4c0: d5e530a2a4c0_create_table_ai_acc_cs_record.py ----
    """Downgrade schema."""
    op.drop_table('ai_acc_cs_record')
