"""Home dashboard endpoint — GET /api/home/overview.

Returns the fixed set of business KPIs and the hourly trend series for a
single selected date. The payload is declarative (see
:mod:`app.services.home_metrics`) so the frontend can render new indicators
without code changes.
"""

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services import home_metrics

router = APIRouter(prefix="/api", tags=["home"])


@router.get("/home/overview")
async def home_overview(
    date: str | None = Query(None, description="查询日期 (YYYY-MM-DD)，默认今天"),
    db: AsyncSession = Depends(get_db),
):
    """KPI cards and hourly trend for the selected day."""
    return await home_metrics.compute_overview(db, _parse_day(date))


@router.get("/home/complaints")
async def home_complaints(
    date: str | None = Query(None, description="查询日期 (YYYY-MM-DD)，默认今天"),
    limit: int = Query(home_metrics.COMPLAINT_DETAIL_LIMIT, ge=1, le=1000, description="最多返回条数"),
    db: AsyncSession = Depends(get_db),
):
    """Complaint work-order detail rows (投诉明细) for the selected day."""
    return await home_metrics.compute_complaints(db, _parse_day(date), limit)


def _parse_day(date: str | None) -> dt.date:
    """Resolve the query date, defaulting to today; reject bad formats."""
    if date:
        try:
            return dt.date.fromisoformat(date)
        except ValueError as err:
            raise HTTPException(
                status_code=422,
                detail=f"日期格式无效: '{date}'。请使用 YYYY-MM-DD 格式。",
            ) from err
    return dt.date.today()
