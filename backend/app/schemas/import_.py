"""Pydantic schemas for Excel product import."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ImportStrategy(str, Enum):
    error = "error"
    skip = "skip"
    overwrite = "overwrite"


class ImportError(BaseModel):
    row: int
    sku: Optional[str] = None
    message: str


class ImportSummaryResponse(BaseModel):
    total_rows: int
    imported: int
    skipped: int = 0
    skipped_no_barcode: int = 0
    skipped_barcode_conflicts: int = 0
    barcode_conflicts: list[ImportError] = Field(default_factory=list)
    overwritten: int = 0
    errors: list[ImportError] = Field(default_factory=list)
