"""Device analysis endpoint — GET /api/device-analysis/profile.

Returns a device profile plus a merged, time-descending incident timeline
for one device SN, assembled across every registered business table that
carries a device-SN column (see :mod:`app.services.device_analysis`).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services import device_analysis

router = APIRouter(prefix="/api", tags=["device-analysis"])


@router.get("/device-analysis/profile")
async def device_profile(
    sn: str = Query(..., description="设备 SN"),
    range: str = Query("all", description="时间范围: day/week/month/quarter/half/year/all"),
    limit: int = Query(100, ge=1, le=1000, description="最多返回记录数"),
    db: AsyncSession = Depends(get_db),
):
    """Device profile + cross-table incident timeline for one SN."""
    sn = sn.strip()
    if not sn:
        raise HTTPException(status_code=422, detail="设备 SN 不能为空。")
    if range not in device_analysis.RANGE_KEYS:
        raise HTTPException(
            status_code=422,
            detail=f"时间范围无效: '{range}'。可选值: {', '.join(device_analysis.RANGE_KEYS)}。",
        )
    return await device_analysis.analyze(db, sn, range, limit)
