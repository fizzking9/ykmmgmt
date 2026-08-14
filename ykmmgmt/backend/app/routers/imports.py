"""Import endpoints — POST /api/imports, GET /api/imports."""

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import DataSource, ImportJob
from app.services.import_service import ImportError, ImportService
from app.services.schema_validator import (
    get_chinese_table_name,
    get_registered_tables,
)

router = APIRouter(prefix="/api", tags=["imports"])


@router.post("/imports")
async def upload_file(
    file: UploadFile = File(...),
    target_table: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a CSV or Excel file for import.

    The file is parsed, validated against the target table's schema
    (using Chinese column comments), cleaned through a standard pipeline
    plus table-specific rules, and inserted into the database.
    """
    # Validate file extension
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".csv", ".xlsx"):
        raise ImportError(
            message=f"不支持的文件格式 '{suffix}'。仅支持 .csv 和 .xlsx",
            status_code=415,
        )

    # Save uploaded file to temp location
    tmp_suffix = suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=tmp_suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        service = ImportService(db)
        result = await service.run_import(tmp_path, target_table, file.filename)
        return result
    except ImportError as e:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=e.status_code,
            content={"detail": e.message, **e.details},
        )
    except Exception as e:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=500,
            content={"detail": f"导入失败: {e}"},
        )
    finally:
        # Clean up temp file
        try:
            tmp_path.unlink()
        except Exception:
            pass


@router.get("/imports")
async def list_imports(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
):
    """List recent import jobs with pagination."""
    # Count total
    count_stmt = select(func.count()).select_from(ImportJob)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Fetch page
    offset = (page - 1) * page_size
    stmt = (
        select(ImportJob, DataSource)
        .join(DataSource, ImportJob.source_id == DataSource.id)
        .order_by(desc(ImportJob.created_at))
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for job, source in rows:
        config = source.config or {}
        items.append(
            {
                "id": job.id,
                "file_name": config.get("file_path", "未知文件"),
                "target_table": get_chinese_table_name(config.get("target_table", "")),
                "status": job.status,
                "total_rows": job.row_count,
                "rows_inserted": job.rows_inserted,
                "rows_updated": job.rows_updated,
                "rows_skipped": job.rows_skipped,
                "rows_rejected": job.error_count,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            }
        )

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/imports/tables")
async def list_tables():
    """List available target tables for import."""
    return {"tables": [{"name": t, "chinese_name": get_chinese_table_name(t)} for t in get_registered_tables()]}
