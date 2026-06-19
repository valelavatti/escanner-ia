"""Excel product import endpoint."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

import aiosqlite

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.schemas.auth import UsuarioResponse
from app.schemas.import_ import ImportStrategy, ImportSummaryResponse
from app.services import excel_import

router = APIRouter()


@router.post("/excel", response_model=ImportSummaryResponse)
async def import_excel(
    file: UploadFile = File(...),
    strategy: ImportStrategy = ImportStrategy.error,
    db: aiosqlite.Connection = Depends(get_db),
    user: UsuarioResponse = Depends(get_current_user),
):
    """Import products from an Excel file (.xlsx or .xls).

    Requires authentication. Use the `strategy` query parameter to choose how
    duplicate SKUs are handled:
    - `error` (default): abort the whole import if a duplicate SKU exists.
    - `skip`: keep the existing product and skip the duplicate.
    - `overwrite`: replace the existing product with the Excel row.
    """
    filename = file.filename or ""
    if not filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos .xlsx o .xls",
        )

    contents = await file.read()

    try:
        df = await excel_import.parse_excel(contents)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo leer el archivo Excel: {exc}",
        )

    try:
        summary = await excel_import.import_products(db, df, strategy)
    except excel_import.ImportValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Validacion fallida",
                "missing_columns": exc.missing_columns,
                "duplicate_skus": exc.duplicate_skus,
                "barcode_conflicts": exc.barcode_conflicts,
                "row_errors": [e.model_dump() for e in exc.row_errors],
            },
        )

    return summary
