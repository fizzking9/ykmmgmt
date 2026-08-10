from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Import table-specific cleaning rules (triggers @register decorators)
import app.services.table_specific.refund_order  # noqa: F401
import app.services.table_specific.service_refund  # noqa: F401
import app.services.table_specific.wallet_withdrawal  # noqa: F401
from app.core.database import get_db
from app.models import RefundOrder, ServiceRefundWorkOrder, WalletWithdrawal
from app.routers.imports import router as imports_router
from app.routers.tables import router as tables_router
from app.routers.views import router as views_router
from app.routers.visualizations import router as visualizations_router
from app.services.schema_validator import register_model

# Register models for schema validation (English name → model class)
register_model("refund_orders", RefundOrder)
register_model("service_refund_work_orders", ServiceRefundWorkOrder)
register_model("wallet_withdrawals", WalletWithdrawal)

app = FastAPI(title="YKMMgmt", version="0.1.0")

# Include routers
app.include_router(imports_router)
app.include_router(tables_router)
app.include_router(views_router)
app.include_router(visualizations_router)

# CORS — allow frontend dev server and localhost origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/health/db")
async def health_db(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
