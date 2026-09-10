"""runtime baseline (Schema Manager dynamic tables)

Revision ID: 06a8dafc5163
Revises: 4b48ee92a6c5
Create Date: 2026-09-10 18:31:41.174304

Squash of 2 Schema Manager runtime migration(s) — see
scripts/squash_runtime_migrations.py. Regenerated, do not edit by hand.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "06a8dafc5163"
down_revision: Union[str, Sequence[str], None] = "4b48ee92a6c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- 6a53c7333e97: 6a53c7333e97_create_business_tables.py ----
    op.execute('DROP TABLE IF EXISTS public."service_order" CASCADE')

    op.execute('DROP TABLE IF EXISTS public."refund_export" CASCADE')

    op.execute('DROP TABLE IF EXISTS public."ai_acc_cs_record" CASCADE')

    op.execute('DROP TABLE IF EXISTS public."device_package" CASCADE')

    op.execute('DROP TABLE IF EXISTS public."device_tag" CASCADE')

    op.execute('DROP TABLE IF EXISTS public."withdraw_record" CASCADE')

    op.execute('DROP TABLE IF EXISTS public."refund_info" CASCADE')

    op.execute('CREATE TABLE public.service_order (\n    id SERIAL NOT NULL,\n    order_no VARCHAR(50) NOT NULL,\n    device_sn VARCHAR(50),\n    device_type VARCHAR(50),\n    device_type_remark TEXT,\n    phone VARCHAR(50),\n    service_category VARCHAR(50),\n    service_item VARCHAR(50),\n    priority INTEGER,\n    status VARCHAR(50),\n    remark TEXT,\n    register_time TIMESTAMP WITHOUT TIME ZONE,\n    activate_time TIMESTAMP WITHOUT TIME ZONE,\n    dispatch_time TIMESTAMP WITHOUT TIME ZONE,\n    finish_time TIMESTAMP WITHOUT TIME ZONE,\n    duration INTEGER,\n    registrar VARCHAR(50),\n    service_staff VARCHAR(50),\n    entry_channel VARCHAR(50),\n    handle_node VARCHAR(50),\n    handler VARCHAR(50),\n    handle_opinion TEXT,\n    is_appealed VARCHAR(50),\n    submit_params JSON,\n    content_hash VARCHAR(64),\n    imported_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),\n    CONSTRAINT service_order_pkey PRIMARY KEY (id),\n    CONSTRAINT uq_service_order_content_hash UNIQUE (content_hash)\n)')

    op.execute("COMMENT ON COLUMN public.service_order.id IS '主键ID'")

    op.execute("COMMENT ON COLUMN public.service_order.order_no IS '工单号'")

    op.execute("COMMENT ON COLUMN public.service_order.device_sn IS 'SN'")

    op.execute("COMMENT ON COLUMN public.service_order.device_type IS '设备类型'")

    op.execute("COMMENT ON COLUMN public.service_order.device_type_remark IS '设备类型备注'")

    op.execute("COMMENT ON COLUMN public.service_order.phone IS '手机号'")

    op.execute("COMMENT ON COLUMN public.service_order.service_category IS '服务类别'")

    op.execute("COMMENT ON COLUMN public.service_order.service_item IS '服务项'")

    op.execute("COMMENT ON COLUMN public.service_order.priority IS '优先级'")

    op.execute("COMMENT ON COLUMN public.service_order.status IS '状态'")

    op.execute("COMMENT ON COLUMN public.service_order.remark IS '备注'")

    op.execute("COMMENT ON COLUMN public.service_order.register_time IS '登记时间'")

    op.execute("COMMENT ON COLUMN public.service_order.activate_time IS '激活时间'")

    op.execute("COMMENT ON COLUMN public.service_order.dispatch_time IS '分发时间'")

    op.execute("COMMENT ON COLUMN public.service_order.finish_time IS '完成时间'")

    op.execute("COMMENT ON COLUMN public.service_order.duration IS '处理时长'")

    op.execute("COMMENT ON COLUMN public.service_order.registrar IS '登记人'")

    op.execute("COMMENT ON COLUMN public.service_order.service_staff IS '服务人员'")

    op.execute("COMMENT ON COLUMN public.service_order.entry_channel IS '录入渠道'")

    op.execute("COMMENT ON COLUMN public.service_order.handle_node IS '处理节点'")

    op.execute("COMMENT ON COLUMN public.service_order.handler IS '处理人'")

    op.execute("COMMENT ON COLUMN public.service_order.handle_opinion IS '处理意见'")

    op.execute("COMMENT ON COLUMN public.service_order.is_appealed IS '是否申诉'")

    op.execute("COMMENT ON COLUMN public.service_order.submit_params IS '提交参数'")

    op.execute("COMMENT ON COLUMN public.service_order.content_hash IS '内容哈希'")

    op.execute("COMMENT ON COLUMN public.service_order.imported_at IS '导入时间'")

    op.execute("COMMENT ON TABLE public.service_order IS '服务工单列表'")

    op.execute('CREATE TABLE public.refund_export (\n    id SERIAL NOT NULL,\n    refund_no VARCHAR(50),\n    platform_order_no VARCHAR(50),\n    third_party_order_no VARCHAR(50),\n    device_sn VARCHAR(50),\n    refund_reason VARCHAR(50),\n    package_name TEXT,\n    merchant_name TEXT,\n    refund_amount NUMERIC(12, 2),\n    actual_refund_amount NUMERIC(12, 2),\n    remark TEXT,\n    status VARCHAR(50),\n    refund_method VARCHAR(50),\n    audit_remark TEXT,\n    auditor VARCHAR(50),\n    create_time TIMESTAMP WITHOUT TIME ZONE,\n    update_time TIMESTAMP WITHOUT TIME ZONE,\n    operator VARCHAR(50),\n    package_price NUMERIC(12, 2),\n    content_hash VARCHAR(64),\n    imported_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),\n    CONSTRAINT refund_export_pkey PRIMARY KEY (id),\n    CONSTRAINT uq_refund_export_content_hash UNIQUE (content_hash)\n)')

    op.execute("COMMENT ON COLUMN public.refund_export.id IS '主键ID'")

    op.execute("COMMENT ON COLUMN public.refund_export.refund_no IS '退费单号'")

    op.execute("COMMENT ON COLUMN public.refund_export.platform_order_no IS '平台订单号'")

    op.execute("COMMENT ON COLUMN public.refund_export.third_party_order_no IS '三方订单号'")

    op.execute("COMMENT ON COLUMN public.refund_export.device_sn IS '设备SN'")

    op.execute("COMMENT ON COLUMN public.refund_export.refund_reason IS '退费原因'")

    op.execute("COMMENT ON COLUMN public.refund_export.package_name IS '套餐名称'")

    op.execute("COMMENT ON COLUMN public.refund_export.merchant_name IS '商户名称'")

    op.execute("COMMENT ON COLUMN public.refund_export.refund_amount IS '退费金额'")

    op.execute("COMMENT ON COLUMN public.refund_export.actual_refund_amount IS '实退金额'")

    op.execute("COMMENT ON COLUMN public.refund_export.remark IS '备注'")

    op.execute("COMMENT ON COLUMN public.refund_export.status IS '状态'")

    op.execute("COMMENT ON COLUMN public.refund_export.refund_method IS '退款方式'")

    op.execute("COMMENT ON COLUMN public.refund_export.audit_remark IS '审核备注'")

    op.execute("COMMENT ON COLUMN public.refund_export.auditor IS '审核人'")

    op.execute("COMMENT ON COLUMN public.refund_export.create_time IS '创建时间'")

    op.execute("COMMENT ON COLUMN public.refund_export.update_time IS '更新时间'")

    op.execute("COMMENT ON COLUMN public.refund_export.operator IS '操作人'")

    op.execute("COMMENT ON COLUMN public.refund_export.package_price IS '套餐价格'")

    op.execute("COMMENT ON COLUMN public.refund_export.content_hash IS '内容哈希'")

    op.execute("COMMENT ON COLUMN public.refund_export.imported_at IS '导入时间'")

    op.execute("COMMENT ON TABLE public.refund_export IS '退费单导出列表'")

    op.execute('CREATE TABLE public.ai_acc_cs_record (\n    id SERIAL NOT NULL,\n    problem_category VARCHAR(50),\n    problem_subcategory VARCHAR(50),\n    device_sn VARCHAR(50),\n    solution VARCHAR(50),\n    operation_time TIMESTAMP WITHOUT TIME ZONE,\n    operator VARCHAR(50),\n    message TEXT,\n    comment TEXT,\n    operation_result VARCHAR(50),\n    whether_accept VARCHAR(50),\n    consultation_time TIMESTAMP WITHOUT TIME ZONE,\n    problem_cat_creation_time TIMESTAMP WITHOUT TIME ZONE,\n    last_consultation_time TIMESTAMP WITHOUT TIME ZONE,\n    content_hash VARCHAR(64),\n    imported_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),\n    CONSTRAINT ai_acc_cs_record_pkey PRIMARY KEY (id),\n    CONSTRAINT uq_ai_acc_cs_record_content_hash UNIQUE (content_hash)\n)')

    op.execute("COMMENT ON COLUMN public.ai_acc_cs_record.id IS '主键ID'")

    op.execute("COMMENT ON COLUMN public.ai_acc_cs_record.problem_category IS '问题大类'")

    op.execute("COMMENT ON COLUMN public.ai_acc_cs_record.problem_subcategory IS '问题类型'")

    op.execute("COMMENT ON COLUMN public.ai_acc_cs_record.device_sn IS '设备号'")

    op.execute("COMMENT ON COLUMN public.ai_acc_cs_record.solution IS '方案'")

    op.execute("COMMENT ON COLUMN public.ai_acc_cs_record.operation_time IS '操作时间'")

    op.execute("COMMENT ON COLUMN public.ai_acc_cs_record.operator IS '操作人'")

    op.execute("COMMENT ON COLUMN public.ai_acc_cs_record.message IS '发送内容'")

    op.execute("COMMENT ON COLUMN public.ai_acc_cs_record.comment IS '说明'")

    op.execute("COMMENT ON COLUMN public.ai_acc_cs_record.operation_result IS '执行结果说明'")

    op.execute("COMMENT ON COLUMN public.ai_acc_cs_record.whether_accept IS '用户是否接受'")

    op.execute("COMMENT ON COLUMN public.ai_acc_cs_record.consultation_time IS '咨询时间'")

    op.execute("COMMENT ON COLUMN public.ai_acc_cs_record.problem_cat_creation_time IS '问题类型创建时间'")

    op.execute("COMMENT ON COLUMN public.ai_acc_cs_record.last_consultation_time IS '最后咨询时间'")

    op.execute("COMMENT ON COLUMN public.ai_acc_cs_record.content_hash IS '内容哈希'")

    op.execute("COMMENT ON COLUMN public.ai_acc_cs_record.imported_at IS '导入时间'")

    op.execute("COMMENT ON TABLE public.ai_acc_cs_record IS 'ai客服记录'")

    op.execute('CREATE TABLE public.device_package (\n    id SERIAL NOT NULL,\n    device_sn VARCHAR(50),\n    package_name VARCHAR(50),\n    package_type VARCHAR(50),\n    data_plan_type VARCHAR(50),\n    merchant_name VARCHAR(50),\n    paid_amount NUMERIC(12, 2),\n    start_date TIMESTAMP WITHOUT TIME ZONE,\n    end_date TIMESTAMP WITHOUT TIME ZONE,\n    update_time TIMESTAMP WITHOUT TIME ZONE,\n    create_time TIMESTAMP WITHOUT TIME ZONE,\n    valid_days INTEGER,\n    creator VARCHAR(50),\n    recharge_order_no VARCHAR(50),\n    available_data BIGINT,\n    used_data BIGINT,\n    remaining_data BIGINT,\n    current_status VARCHAR(50),\n    content_hash VARCHAR(64),\n    imported_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),\n    CONSTRAINT device_package_pkey PRIMARY KEY (id),\n    CONSTRAINT uq_device_package_content_hash UNIQUE (content_hash)\n)')

    op.execute("COMMENT ON COLUMN public.device_package.id IS '主键ID'")

    op.execute("COMMENT ON COLUMN public.device_package.device_sn IS '设备SN'")

    op.execute("COMMENT ON COLUMN public.device_package.package_name IS '套餐名称'")

    op.execute("COMMENT ON COLUMN public.device_package.package_type IS '套餐类型'")

    op.execute("COMMENT ON COLUMN public.device_package.data_plan_type IS '流量类型'")

    op.execute("COMMENT ON COLUMN public.device_package.merchant_name IS '商户名称'")

    op.execute("COMMENT ON COLUMN public.device_package.paid_amount IS '实际支付金额'")

    op.execute("COMMENT ON COLUMN public.device_package.start_date IS '开始日期'")

    op.execute("COMMENT ON COLUMN public.device_package.end_date IS '结束日期'")

    op.execute("COMMENT ON COLUMN public.device_package.update_time IS '更新时间'")

    op.execute("COMMENT ON COLUMN public.device_package.create_time IS '创建时间'")

    op.execute("COMMENT ON COLUMN public.device_package.valid_days IS '套餐有效天数'")

    op.execute("COMMENT ON COLUMN public.device_package.creator IS '创建人'")

    op.execute("COMMENT ON COLUMN public.device_package.recharge_order_no IS '充值订单号'")

    op.execute("COMMENT ON COLUMN public.device_package.available_data IS '可用流量'")

    op.execute("COMMENT ON COLUMN public.device_package.used_data IS '已用流量'")

    op.execute("COMMENT ON COLUMN public.device_package.remaining_data IS '剩余流量'")

    op.execute("COMMENT ON COLUMN public.device_package.current_status IS '当前状态'")

    op.execute("COMMENT ON COLUMN public.device_package.content_hash IS '内容哈希'")

    op.execute("COMMENT ON COLUMN public.device_package.imported_at IS '导入时间'")

    op.execute("COMMENT ON TABLE public.device_package IS '设备套餐列表'")

    op.execute('CREATE TABLE public.device_tag (\n    id SERIAL NOT NULL,\n    device_sn VARCHAR(50),\n    tag_name VARCHAR(50),\n    merchant_name VARCHAR(50),\n    current_package VARCHAR(50),\n    creator VARCHAR(50),\n    update_time TIMESTAMP WITHOUT TIME ZONE,\n    content_hash VARCHAR(64),\n    imported_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),\n    CONSTRAINT device_tag_pkey PRIMARY KEY (id),\n    CONSTRAINT uq_device_tag_content_hash UNIQUE (content_hash)\n)')

    op.execute("COMMENT ON COLUMN public.device_tag.id IS '主键ID'")

    op.execute("COMMENT ON COLUMN public.device_tag.device_sn IS '设备sn'")

    op.execute("COMMENT ON COLUMN public.device_tag.tag_name IS '标签名'")

    op.execute("COMMENT ON COLUMN public.device_tag.merchant_name IS '设备所属商户'")

    op.execute("COMMENT ON COLUMN public.device_tag.current_package IS '设备当前套餐'")

    op.execute("COMMENT ON COLUMN public.device_tag.creator IS '创建人'")

    op.execute("COMMENT ON COLUMN public.device_tag.update_time IS '更新时间'")

    op.execute("COMMENT ON COLUMN public.device_tag.content_hash IS '内容哈希'")

    op.execute("COMMENT ON COLUMN public.device_tag.imported_at IS '导入时间'")

    op.execute("COMMENT ON TABLE public.device_tag IS '设备标签列表'")

    op.execute('CREATE TABLE public.withdraw_record (\n    id SERIAL NOT NULL,\n    account_id VARCHAR(100),\n    wallet_balance NUMERIC(12, 2),\n    device_sn VARCHAR(50),\n    operation_type VARCHAR(50),\n    operation_amount NUMERIC(12, 2),\n    remark TEXT,\n    operation_time TIMESTAMP WITHOUT TIME ZONE,\n    operator VARCHAR(50),\n    content_hash VARCHAR(64),\n    imported_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),\n    CONSTRAINT withdraw_record_pkey PRIMARY KEY (id),\n    CONSTRAINT uq_withdraw_record_content_hash UNIQUE (content_hash)\n)')

    op.execute("COMMENT ON COLUMN public.withdraw_record.id IS '主键ID'")

    op.execute("COMMENT ON COLUMN public.withdraw_record.account_id IS '账户ID'")

    op.execute("COMMENT ON COLUMN public.withdraw_record.wallet_balance IS '钱包余额'")

    op.execute("COMMENT ON COLUMN public.withdraw_record.device_sn IS 'SN'")

    op.execute("COMMENT ON COLUMN public.withdraw_record.operation_type IS '操作类型'")

    op.execute("COMMENT ON COLUMN public.withdraw_record.operation_amount IS '操作金额'")

    op.execute("COMMENT ON COLUMN public.withdraw_record.remark IS '备注'")

    op.execute("COMMENT ON COLUMN public.withdraw_record.operation_time IS '操作时间'")

    op.execute("COMMENT ON COLUMN public.withdraw_record.operator IS '操作人员'")

    op.execute("COMMENT ON COLUMN public.withdraw_record.content_hash IS '内容哈希'")

    op.execute("COMMENT ON COLUMN public.withdraw_record.imported_at IS '导入时间'")

    op.execute("COMMENT ON TABLE public.withdraw_record IS '提现操作记录'")

    # ---- de819e56d36c: de819e56d36c_create_table_refund_info.py ----
    """Upgrade schema."""
    op.create_table('refund_info',
    sa.Column('refund_no', sa.String(length=64), autoincrement=False, nullable=False, comment='退费单号'),
    sa.Column('order_no', sa.String(length=64), nullable=True, comment='订单号'),
    sa.Column('phone', sa.String(length=32), nullable=True, comment='手机号码'),
    sa.Column('package_name', sa.String(length=255), nullable=True, comment='套餐名称'),
    sa.Column('paid_amount', sa.Numeric(precision=12, scale=2), nullable=True, comment='实际支付金额'),
    sa.Column('applied_refund_amount', sa.Numeric(precision=12, scale=2), nullable=True, comment='申请退款金额'),
    sa.Column('refund_amount', sa.Numeric(precision=12, scale=2), nullable=True, comment='退款金额'),
    sa.Column('refund_reason', sa.Text(), nullable=True, comment='退款原因'),
    sa.Column('refund_status', sa.String(length=32), nullable=True, comment='退款状态'),
    sa.Column('refund_method', sa.String(length=32), nullable=True, comment='退款方式'),
    sa.Column('auditor_name', sa.String(length=64), nullable=True, comment='审核人名称'),
    sa.Column('audit_time', sa.DateTime(), nullable=True, comment='审核时间'),
    sa.Column('audit_remark', sa.Text(), nullable=True, comment='审核备注'),
    sa.Column('apply_remark', sa.Text(), nullable=True, comment='申请备注'),
    sa.Column('imported_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True, comment='导入时间'),
    sa.PrimaryKeyConstraint('refund_no'),
    if_not_exists=True,
    )
    op.execute("COMMENT ON TABLE refund_info IS '退款单信息'")


def downgrade() -> None:
    # ---- de819e56d36c: de819e56d36c_create_table_refund_info.py ----
    """Downgrade schema."""
    op.drop_table('refund_info')

    # ---- 6a53c7333e97: 6a53c7333e97_create_business_tables.py ----
    pass
