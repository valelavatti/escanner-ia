"""Excel product import service with vectorized pandas validation."""

from io import BytesIO
from typing import Optional

import aiosqlite
import pandas as pd

from app.repositories import producto_repository
from app.schemas.import_ import ImportError, ImportStrategy, ImportSummaryResponse

REQUIRED_COLUMNS = ["sku", "descripcion", "codigo_de_barra"]

# Accesaniga real Excel: "DATOS GENERALES" sheet, header at row 10 (0-indexed: 9)
EXCEL_SHEET = "DATOS GENERALES"
EXCEL_HEADER_ROW = 9

# Map Spanish/variant column names from the real Excel to the internal model
COLUMN_ALIASES = {
    "sku": "sku",
    "codigo": "sku",
    "código": "sku",
    "cod": "sku",
    "descripcion": "descripcion",
    "descripción": "descripcion",
    "desc": "descripcion",
    "codigo_de_barra": "codigo_de_barra",
    "codigo de barra": "codigo_de_barra",
    "código de barra": "codigo_de_barra",
    "código barra": "codigo_de_barra",
    "codigo barra": "codigo_de_barra",
    "codigo_barra": "codigo_de_barra",
    "código_barra": "codigo_de_barra",
}


class ImportValidationError(Exception):
    """Raised when the Excel file fails pre-transaction validation."""

    def __init__(
        self,
        *,
        missing_columns: Optional[list[str]] = None,
        duplicate_skus: Optional[list[str]] = None,
        barcode_conflicts: Optional[list[dict]] = None,
        row_errors: Optional[list[ImportError]] = None,
    ):
        self.missing_columns = missing_columns or []
        self.duplicate_skus = duplicate_skus or []
        self.barcode_conflicts = barcode_conflicts or []
        self.row_errors = row_errors or []
        super().__init__("Excel validation failed")


async def parse_excel(file_bytes: bytes) -> pd.DataFrame:
    """Parse Excel bytes into a clean DataFrame.

    Supports two formats:
    1. Accesaniga real file: 'DATOS GENERALES' sheet with header at row 10.
       Columns 'Código', 'Descripción', 'Código Barra' are mapped to the internal model.
       Extra columns (Marca, Activo?, Discontinuado) are dropped.
    2. Standard format: first sheet with header at row 1 (columns sku/descripcion/codigo_de_barra).
    """
    xls = pd.ExcelFile(BytesIO(file_bytes), engine="openpyxl")

    if EXCEL_SHEET in xls.sheet_names:
        # Accesaniga format: 'DATOS GENERALES' sheet, header at row 10 (0-indexed: 9)
        df = pd.read_excel(xls, sheet_name=EXCEL_SHEET, header=EXCEL_HEADER_ROW)
        header_row = EXCEL_HEADER_ROW
    else:
        # Standard format: first sheet, header at row 1 (0-indexed: 0)
        df = pd.read_excel(xls, sheet_name=0, header=0)
        header_row = 0

    # Drop fully-empty rows silently per spec scenario 3.
    df = df.dropna(how="all")
    # Normalize column names: strip whitespace and lowercase.
    df.columns = df.columns.str.strip().str.lower()
    # Map aliased column names (e.g. 'código' → 'sku') to the internal model.
    df = df.rename(columns=lambda c: COLUMN_ALIASES.get(c, c))
    # Keep only the required columns; drop extras (Marca, Activo?, Discontinuado).
    available = [col for col in REQUIRED_COLUMNS if col in df.columns]
    df = df[available].copy()
    # Convert numeric barcodes/SKUs (read as float64) to clean string values.
    for col in REQUIRED_COLUMNS:
        if col in df.columns:
            df[col] = df[col].apply(_normalize_str)
    # Store the header row offset for accurate Excel row reporting in errors.
    df.attrs["header_row"] = header_row
    return df


def validate_columns(df: pd.DataFrame) -> list[str]:
    """Return the list of required columns missing from the DataFrame."""
    return [col for col in REQUIRED_COLUMNS if col not in df.columns]


def _excel_row(pandas_index: int, header_row: int = 0) -> int:
    """Map a 0-based pandas index to a 1-based Excel row number.

    The header is at (header_row + 1) in Excel, so the first data row is
    at (header_row + 2). pandas index 0 maps to that first data row.
    """
    return int(pandas_index) + header_row + 2


def _normalize_str(value) -> Optional[str]:
    """Convert a pandas cell value to a stripped string or None.

    Handles numeric barcodes/SKUs that pandas reads as float64 (e.g. 7.796908e+12)
    by converting them to clean integer strings without decimal/scientific notation.
    """
    if pd.isna(value):
        return None
    if isinstance(value, float):
        # Barcodes like 7796908047867.0 → "7796908047867" (not "7.796908e+12")
        if value == int(value):
            return str(int(value))
        return str(value).strip() or None
    text = str(value).strip()
    return text if text else None


def validate_rows(df: pd.DataFrame) -> list[ImportError]:
    """Validate that every row has a non-empty SKU.

    Rows with an empty SKU are hard errors that abort the import (SKU is the primary key).
    Rows with an empty barcode are NOT errors — they are skipped silently during import
    (Option A: import only products that have a scannable barcode).

    Uses vectorized boolean masks instead of iterrows().
    """
    header_row = df.attrs.get("header_row", 0)
    sku_missing = df["sku"].isna() | (df["sku"].astype(str).str.strip() == "")

    errors: list[ImportError] = []
    for idx in df.index[sku_missing]:
        errors.append(
            ImportError(
                row=_excel_row(idx, header_row),
                sku=None,
                message="sku vacio",
            )
        )
    return errors


def filter_rows_without_barcode(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Separate rows that have a barcode from those that don't.

    Returns (df_with_barcode, count_without_barcode).
    Rows without a barcode are excluded from import but NOT treated as errors.
    """
    barcode_missing = df["codigo_de_barra"].isna() | (
        df["codigo_de_barra"].astype(str).str.strip() == ""
    )
    df_with = df[~barcode_missing].copy()
    df_with.attrs["header_row"] = df.attrs.get("header_row", 0)
    return df_with, int(barcode_missing.sum())


def detect_intra_excel_duplicates(df: pd.DataFrame) -> list[str]:
    """Return SKUs that appear more than once inside the Excel file."""
    dup_mask = df.duplicated(subset=["sku"], keep=False)
    dup_skus = (
        df.loc[dup_mask, "sku"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )
    return dup_skus


def detect_intra_excel_barcode_conflicts(df: pd.DataFrame) -> list[dict]:
    """Return barcodes inside the Excel that are mapped to more than one SKU."""
    # Count unique SKUs per barcode using vectorized groupby.
    sku_counts = df.groupby("codigo_de_barra")["sku"].nunique(dropna=True)
    conflicting = sku_counts[sku_counts > 1]

    conflicts: list[dict] = []
    for barcode in conflicting.index:
        skus = (
            df.loc[df["codigo_de_barra"].astype(str).str.strip() == str(barcode).strip(), "sku"]
            .dropna()
            .astype(str)
            .str.strip()
            .unique()
            .tolist()
        )
        conflicts.append(
            {
                "sku": ", ".join(skus),
                "barcode": str(barcode),
                "existing_sku": "conflicto dentro del Excel",
            }
        )
    return conflicts


def filter_intra_excel_barcode_conflicts(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, int, list[dict]]:
    """Keep the first occurrence of each barcode; skip rows where the barcode
    is shared with a different SKU.

    Returns (df_clean, skipped_count, conflict_details).
    Barcodes that appear with only one SKU are kept as-is.
    """
    conflicts = detect_intra_excel_barcode_conflicts(df)
    if not conflicts:
        df.attrs["header_row"] = df.attrs.get("header_row", 0)
        return df, 0, []

    conflicting_barcodes = {c["barcode"] for c in conflicts}
    # For each conflicting barcode, keep only the first row (by pandas index order).
    conflict_mask = df["codigo_de_barra"].astype(str).str.strip().isin(conflicting_barcodes)
    conflict_df = df[conflict_mask].copy()
    # Keep first row per barcode within the conflicting subset.
    keep_indices = conflict_df.drop_duplicates(subset=["codigo_de_barra"], keep="first").index
    skip_indices = conflict_df.index.difference(keep_indices)
    # Final df: non-conflicting rows + first occurrence of each conflicting barcode.
    df_clean = df.drop(index=skip_indices).copy()
    df_clean.attrs["header_row"] = df.attrs.get("header_row", 0)
    return df_clean, len(skip_indices), conflicts


async def _get_existing_skus(
    db: aiosqlite.Connection,
    skus: list[str],
) -> set[str]:
    """Return the subset of SKUs that already exist in the database."""
    clean_skus = [s for s in skus if s]
    if not clean_skus:
        return set()

    placeholders = ",".join("?" * len(clean_skus))
    async with db.execute(
        f"SELECT sku FROM productos WHERE sku IN ({placeholders})",
        tuple(clean_skus),
    ) as cursor:
        rows = await cursor.fetchall()

    return {row["sku"] for row in rows}


async def _check_db_barcode_conflicts(
    db: aiosqlite.Connection,
    df: pd.DataFrame,
) -> list[dict]:
    """Return barcodes in the Excel already assigned to a different SKU in the DB."""
    barcodes = (
        df["codigo_de_barra"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )
    if not barcodes:
        return []

    placeholders = ",".join("?" * len(barcodes))
    async with db.execute(
        f"SELECT sku, codigo_de_barra FROM productos WHERE codigo_de_barra IN ({placeholders})",
        tuple(barcodes),
    ) as cursor:
        rows = await cursor.fetchall()

    existing = {row["codigo_de_barra"]: row["sku"] for row in rows}
    if not existing:
        return []

    existing_df = pd.DataFrame(
        [{"sku": sku, "codigo_de_barra": barcode} for barcode, sku in existing.items()]
    )
    merged = df.merge(
        existing_df,
        on="codigo_de_barra",
        how="inner",
        suffixes=("", "_existing"),
    )
    conflict_mask = (
        merged["sku"].astype(str).str.strip()
        != merged["sku_existing"].astype(str).str.strip()
    )
    conflicts_df = merged[conflict_mask]

    return conflicts_df.rename(
        columns={"codigo_de_barra": "barcode", "sku_existing": "existing_sku"}
    )[["sku", "barcode", "existing_sku"]].to_dict("records")


async def _filter_db_barcode_conflicts(
    db: aiosqlite.Connection,
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, int, list[dict]]:
    """Skip rows whose barcode is already assigned to a different SKU in the DB.

    Returns (df_clean, skipped_count, conflict_details).
    """
    conflicts = await _check_db_barcode_conflicts(db, df)
    if not conflicts:
        df.attrs["header_row"] = df.attrs.get("header_row", 0)
        return df, 0, []

    conflicting_barcodes = {str(c["barcode"]).strip() for c in conflicts}
    conflict_mask = df["codigo_de_barra"].astype(str).str.strip().isin(conflicting_barcodes)
    df_clean = df[~conflict_mask].copy()
    df_clean.attrs["header_row"] = df.attrs.get("header_row", 0)
    return df_clean, int(conflict_mask.sum()), conflicts


async def import_products(
    db: aiosqlite.Connection,
    df: pd.DataFrame,
    strategy: ImportStrategy,
) -> ImportSummaryResponse:
    """Import validated products into the DB using the selected duplicate strategy.

    Rows without a barcode are skipped silently (not imported, not errors) per Option A.
    """
    # 1. Missing required columns -> abort immediately.
    missing = validate_columns(df)
    if missing:
        raise ImportValidationError(missing_columns=missing)

    # 2. Row-level validation (empty SKU = hard error, empty barcode = skip).
    row_errors = validate_rows(df)
    if row_errors:
        raise ImportValidationError(row_errors=row_errors)

    # 3. Filter out rows without a barcode (Option A: skip, don't error).
    df, skipped_no_barcode = filter_rows_without_barcode(df)

    # 4. Intra-Excel duplicate SKUs -> error only for strategy=error.
    duplicate_skus: list[str] = []
    if strategy == ImportStrategy.error:
        duplicate_skus = detect_intra_excel_duplicates(df)

    if duplicate_skus:
        raise ImportValidationError(duplicate_skus=duplicate_skus)

    # 5. Intra-Excel barcode conflicts -> skip conflicting rows (keep first occurrence).
    df, skipped_intra_conflicts, intra_conflicts = filter_intra_excel_barcode_conflicts(df)

    # Total rows is the count after dropping empty rows but before filtering.
    total_rows = len(df) + skipped_no_barcode + skipped_intra_conflicts

    # 6. For skip/overwrite, keep the last occurrence of each SKU.
    if strategy in (ImportStrategy.skip, ImportStrategy.overwrite):
        df = df.drop_duplicates(subset=["sku"], keep="last")

    # 7. DB barcode conflicts -> skip conflicting rows (don't abort).
    df, skipped_db_conflicts, db_conflicts = await _filter_db_barcode_conflicts(db, df)

    skipped_barcode_conflicts = skipped_intra_conflicts + skipped_db_conflicts
    all_conflicts = intra_conflicts + db_conflicts

    # 8. Execute the import inside a single SQLite transaction.
    await db.execute("BEGIN")
    try:
        if strategy == ImportStrategy.error:
            imported = await _import_error_strategy(db, df)
            return ImportSummaryResponse(
                total_rows=total_rows,
                imported=imported,
                skipped_no_barcode=skipped_no_barcode,
                skipped_barcode_conflicts=skipped_barcode_conflicts,
                barcode_conflicts=[
                    ImportError(row=0, sku=c.get("sku", ""), message=f"barcode {c.get('barcode', '')} en conflicto ({c.get('existing_sku', '')})")
                    for c in all_conflicts
                ],
            )

        if strategy == ImportStrategy.skip:
            imported, skipped = await _import_skip_strategy(db, df)
            return ImportSummaryResponse(
                total_rows=total_rows,
                imported=imported,
                skipped=skipped,
                skipped_no_barcode=skipped_no_barcode,
                skipped_barcode_conflicts=skipped_barcode_conflicts,
                barcode_conflicts=[
                    ImportError(row=0, sku=c.get("sku", ""), message=f"barcode {c.get('barcode', '')} en conflicto ({c.get('existing_sku', '')})")
                    for c in all_conflicts
                ],
            )

        # strategy == ImportStrategy.overwrite
        imported, overwritten = await _import_overwrite_strategy(db, df)
        return ImportSummaryResponse(
            total_rows=total_rows,
            imported=imported,
            overwritten=overwritten,
            skipped_no_barcode=skipped_no_barcode,
            skipped_barcode_conflicts=skipped_barcode_conflicts,
            barcode_conflicts=[
                ImportError(row=0, sku=c.get("sku", ""), message=f"barcode {c.get('barcode', '')} en conflicto ({c.get('existing_sku', '')})")
                for c in all_conflicts
            ],
        )
    except Exception:
        await db.execute("ROLLBACK")
        raise


async def _import_error_strategy(
    db: aiosqlite.Connection,
    df: pd.DataFrame,
) -> int:
    """Insert every row. Duplicates and conflicts were already checked."""
    records = [
        (
            _normalize_str(row["sku"]),
            _normalize_str(row["descripcion"]) or "",
            _normalize_str(row["codigo_de_barra"]),
        )
        for _, row in df.iterrows()
    ]
    if records:
        await db.executemany(
            "INSERT INTO productos (sku, descripcion, codigo_de_barra) VALUES (?, ?, ?)",
            records,
        )
    await db.commit()
    return len(records)


async def _import_skip_strategy(
    db: aiosqlite.Connection,
    df: pd.DataFrame,
) -> tuple[int, int]:
    """Insert rows whose SKU does not exist; skip the rest."""
    existing_skus = await _get_existing_skus(db, df["sku"].astype(str).str.strip().tolist())
    records = [
        (
            _normalize_str(row["sku"]),
            _normalize_str(row["descripcion"]) or "",
            _normalize_str(row["codigo_de_barra"]),
        )
        for _, row in df.iterrows()
        if _normalize_str(row["sku"]) not in existing_skus
    ]
    if records:
        await db.executemany(
            "INSERT OR IGNORE INTO productos (sku, descripcion, codigo_de_barra) VALUES (?, ?, ?)",
            records,
        )
    await db.commit()
    return len(records), len(existing_skus)


async def _import_overwrite_strategy(
    db: aiosqlite.Connection,
    df: pd.DataFrame,
) -> tuple[int, int]:
    """Upsert rows: insert new SKUs, overwrite existing ones."""
    existing_skus = await _get_existing_skus(db, df["sku"].astype(str).str.strip().tolist())
    records = [
        (
            _normalize_str(row["sku"]),
            _normalize_str(row["descripcion"]) or "",
            _normalize_str(row["codigo_de_barra"]),
        )
        for _, row in df.iterrows()
    ]
    if records:
        await db.executemany(
            """
            INSERT INTO productos (sku, descripcion, codigo_de_barra)
            VALUES (?, ?, ?)
            ON CONFLICT(sku) DO UPDATE SET
                descripcion = excluded.descripcion,
                codigo_de_barra = excluded.codigo_de_barra,
                updated_at = CURRENT_TIMESTAMP
            """,
            records,
        )
    await db.commit()
    overwritten = len(existing_skus)
    imported = len(records) - overwritten
    return imported, overwritten
