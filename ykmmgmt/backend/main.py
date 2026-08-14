import logging

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Import table-specific cleaning rules (triggers @register decorators)
import app.services.table_specific.refund_order  # noqa: F401
import app.services.table_specific.service_refund  # noqa: F401
import app.services.table_specific.wallet_withdrawal  # noqa: F401
from app.core.database import engine, get_db
from app.models import RefundOrder, ServiceRefundWorkOrder, WalletWithdrawal
from app.routers.dashboards import router as dashboards_router
from app.routers.imports import router as imports_router
from app.routers.schema import router as schema_router
from app.routers.tables import router as tables_router
from app.routers.views import router as views_router
from app.routers.visualizations import router as visualizations_router
from app.services.schema_manager import SchemaManagerError
from app.services.schema_validator import register_model

logger = logging.getLogger("ykmmgmt")

# Register models for schema validation (English name → model class)
register_model("refund_orders", RefundOrder)
register_model("service_refund_work_orders", ServiceRefundWorkOrder)
register_model("wallet_withdrawals", WalletWithdrawal)

app = FastAPI(title="YKMMgmt", version="0.1.0")

# Include routers
app.include_router(imports_router)
app.include_router(tables_router)
app.include_router(schema_router)
app.include_router(views_router)
app.include_router(visualizations_router)
app.include_router(dashboards_router)

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


# Ensure every failure returns a JSON body with a readable reason (the
# frontend surfaces `detail` in toasts; bare HTML 500s gave users nothing).
@app.exception_handler(SchemaManagerError)
async def schema_manager_error_handler(request: Request, exc: SchemaManagerError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    reason = str(exc) or type(exc).__name__
    return JSONResponse(
        status_code=500,
        content={"detail": f"服务器内部错误: {reason}"},
    )


@app.on_event("startup")
async def restore_dynamic_tables_on_startup():
    """Re-register Schema-Manager tables after any (re)start.

    Dynamic models live only in memory, so a restart would otherwise make
    user-created tables disappear from the Data Browser / View Builder.
    """
    from app.services import schema_manager as sm

    async with engine.connect() as conn:
        restored = await sm.restore_dynamic_tables(conn)
    if restored:
        logger.info("Restored %d dynamic table(s) from the database", restored)


@app.get("/api/health/db")
async def health_db(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
