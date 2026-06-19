"""Pydantic schemas for product endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ProductOut(BaseModel):
    sku: str
    descripcion: str
    codigo_de_barra: str
    created_at: Optional[datetime] = None


class ProductSearchResponse(BaseModel):
    items: list[ProductOut]
    total: int
