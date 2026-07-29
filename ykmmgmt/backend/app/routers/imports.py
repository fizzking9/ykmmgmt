"""Import endpoint — POST /api/imports."""

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
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
        result = await service.run_import(tmp_path, target_table)
        await db.commit()
        return result
    except ImportError as e:
        await db.rollback()
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=e.status_code,
            content={"detail": e.message, **e.details},
        )
    except Exception as e:
        await db.rollback()
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


@router.get("/imports/tables")
async def list_tables():
    """List available target tables for import."""
    return {"tables": [{"name": t, "chinese_name": get_chinese_table_name(t)} for t in get_registered_tables()]}
