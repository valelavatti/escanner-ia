"""QR generation, caching, and A4 print-sheet composition service."""

import asyncio
import os
import re
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import qrcode
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont

from app.core.config import get_settings

PAGE_W = 2480
PAGE_H = 3508
MARGIN = 120
GAP = 80
LABEL_H = 80

_CONTENT_W = PAGE_W - 2 * MARGIN
_CONTENT_H = PAGE_H - 2 * MARGIN

_VALID_PER_PAGE = {1, 2, 4, 6, 8, 9}

# Minimum QR image resolution used when generating cached PNGs for print sheets.
# The actual display size on the A4 page is calculated from per_page.
_MIN_QR_RESOLUTION = 300


def _sanitize_qr_valor(qr_valor: str) -> str:
    """Make a QR value safe to use in a filename.

    Replaces spaces with underscores and removes characters that could be
    interpreted as path separators or traversal sequences.
    """
    sanitized = qr_valor.replace(" ", "_")
    sanitized = re.sub(r"[\\/:*?\"<>|]+", "", sanitized)
    return sanitized or "qr"


def _cache_path(qr_valor: str, size: int) -> Path:
    """Return the deterministic cache path for a QR value and size."""
    settings = get_settings()
    sanitized = _sanitize_qr_valor(qr_valor)
    return Path(settings.qr_cache_dir) / f"{sanitized}_{size}.png"


def _generate_qr_image(qr_valor: str, size: int) -> Image:
    """Generate a square QR image resized to ``size`` pixels."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_valor)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((size, size), Image.Resampling.NEAREST)
    return img


def _save_image_atomic(img: Image, target: Path) -> None:
    """Save a PIL image to ``target`` using a temp file + rename.

    This keeps concurrent readers from seeing a partially-written file.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target.with_suffix(f".tmp{os.getpid()}.png")
    try:
        img.save(temp_path, format="PNG")
        os.replace(temp_path, target)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


async def get_or_create_qr_path(qr_valor: str, size: int) -> Path:
    """Return the cached PNG path for ``qr_valor``, generating it if needed."""
    target = _cache_path(qr_valor, size)

    if target.exists():
        return target

    def _generate_and_save() -> Path:
        # Idempotency: if another task created the file while we were waiting
        # for the worker thread, return it without overwriting.
        if target.exists():
            return target
        img = _generate_qr_image(qr_valor, size)
        _save_image_atomic(img, target)
        return target

    return await asyncio.to_thread(_generate_and_save)


async def get_or_create_qr_bytes(qr_valor: str, size: int) -> bytes:
    """Return the cached PNG bytes for ``qr_valor``, generating it if needed."""
    path = await get_or_create_qr_path(qr_valor, size)

    def _read() -> bytes:
        with open(path, "rb") as f:
            return f.read()

    return await asyncio.to_thread(_read)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a reasonable TrueType font, falling back to the default bitmap font."""
    candidates = [
        "arial.ttf",
        "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _get_grid_layout(per_page: int) -> tuple[int, int]:
    """Return (cols, rows) for the supported A4 page densities."""
    mapping = {
        1: (1, 1),
        2: (1, 2),
        4: (2, 2),
        6: (2, 3),
        8: (2, 4),
        9: (3, 3),
    }
    if per_page not in mapping:
        raise ValueError(f"per_page must be one of {sorted(_VALID_PER_PAGE)}")
    return mapping[per_page]


def _calculate_qr_display_size(per_page: int) -> tuple[int, int]:
    """Return the (width, height) in pixels that the QR should fill on A4.

    The size is derived from the available cell space so the QR fills the
    page area, regardless of the original ``size`` resolution parameter.
    """
    cols, rows = _get_grid_layout(per_page)
    cell_w = (_CONTENT_W - (cols - 1) * GAP) / cols
    cell_h = (_CONTENT_H - (rows - 1) * GAP) / rows
    qr_size = int(min(cell_w, cell_h - LABEL_H))
    return (qr_size, qr_size)


def _build_single_a4_page(
    qr_items: list[tuple[str, bytes]],
    per_page: int,
) -> Image:
    """Compose one A4 page from the first ``per_page`` QR items."""
    page = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    draw = ImageDraw.Draw(page)
    font = _load_font(max(24, LABEL_H - 16))

    cols, rows = _get_grid_layout(per_page)
    cell_w = (_CONTENT_W - (cols - 1) * GAP) / cols
    cell_h = (_CONTENT_H - (rows - 1) * GAP) / rows
    qr_draw_size = _calculate_qr_display_size(per_page)[0]

    for idx, (qr_valor, png_bytes) in enumerate(qr_items[:per_page]):
        col = idx % cols
        row = idx // cols

        qr_img = Image.open(BytesIO(png_bytes)).convert("RGB")
        qr_img = qr_img.resize((qr_draw_size, qr_draw_size), Image.Resampling.NEAREST)

        cell_left = MARGIN + col * (cell_w + GAP)
        cell_top = MARGIN + row * (cell_h + GAP)
        x = int(cell_left + (cell_w - qr_draw_size) / 2)
        y = int(cell_top + (cell_h - LABEL_H - qr_draw_size) / 2)

        page.paste(qr_img, (x, y))

        # Center the label in the reserved LABEL_H strip below the QR.
        label_y = y + qr_draw_size + 8
        bbox = draw.textbbox((0, 0), qr_valor, font=font)
        text_w = bbox[2] - bbox[0]
        text_x = int(cell_left + (cell_w - text_w) / 2)
        draw.text((text_x, label_y), qr_valor, fill="black", font=font)

    return page


def _build_a4_sheet(
    qr_items: list[tuple[str, bytes]],
    per_page: int,
) -> Image:
    """Stack A4 pages vertically until all QR items are laid out."""
    if not qr_items:
        return Image.new("RGB", (PAGE_W, PAGE_H), "white")

    pages: list[Image] = []
    for start in range(0, len(qr_items), per_page):
        chunk = qr_items[start : start + per_page]
        pages.append(_build_single_a4_page(chunk, per_page))

    if len(pages) == 1:
        return pages[0]

    total_height = sum(page.height for page in pages)
    sheet = Image.new("RGB", (PAGE_W, total_height), "white")
    y_offset = 0
    for page in pages:
        sheet.paste(page, (0, y_offset))
        y_offset += page.height

    return sheet


# A4 dimensions in millimeters, used for PDF output.
_A4_W_MM = 210.0
_A4_H_MM = 297.0


def _pdf_cell_layout(per_page: int) -> tuple[int, int, float, float, float, float]:
    """Return PDF layout values: (cols, rows, cell_w_mm, cell_h_mm, gap_mm, margin_mm)."""
    cols, rows = _get_grid_layout(per_page)
    margin_mm = MARGIN / PAGE_W * _A4_W_MM
    gap_mm = GAP / PAGE_W * _A4_W_MM
    content_w = _A4_W_MM - 2 * margin_mm
    content_h = _A4_H_MM - 2 * margin_mm
    cell_w = (content_w - (cols - 1) * gap_mm) / cols
    cell_h = (content_h - (rows - 1) * gap_mm) / rows
    return cols, rows, cell_w, cell_h, gap_mm, margin_mm


def _build_pdf(qr_items: list[tuple[str, bytes]], per_page: int) -> bytes:
    """Compose a multi-page A4 PDF with QRs and return it as bytes."""
    cols, rows, cell_w, cell_h, gap, margin = _pdf_cell_layout(per_page)
    qr_size_mm = min(cell_w, cell_h - (LABEL_H / PAGE_W * _A4_W_MM))
    label_h_mm = LABEL_H / PAGE_W * _A4_W_MM

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(False)
    pdf.set_fill_color(255, 255, 255)

    font_size = max(8, int(label_h_mm * 1.5))
    pdf.set_font("Arial", size=font_size)

    for start in range(0, len(qr_items), per_page):
        pdf.add_page()
        chunk = qr_items[start : start + per_page]

        for idx, (qr_valor, png_bytes) in enumerate(chunk):
            col = idx % cols
            row = idx // cols

            cell_left = margin + col * (cell_w + gap)
            cell_top = margin + row * (cell_h + gap)
            x = cell_left + (cell_w - qr_size_mm) / 2
            y = cell_top + (cell_h - label_h_mm - qr_size_mm) / 2

            pdf.image(BytesIO(png_bytes), x=x, y=y, w=qr_size_mm, h=qr_size_mm)

            # Center the label below the QR.
            label_y = y + qr_size_mm + 1.0
            text_width = pdf.get_string_width(qr_valor)
            text_x = cell_left + (cell_w - text_width) / 2
            pdf.set_xy(text_x, label_y)
            pdf.cell(text_width, label_h_mm, qr_valor, align="C")

    buffer: BinaryIO = BytesIO()
    pdf.output(buffer)
    return buffer.getvalue()


async def generate_estante_qrs(
    estante_id: int,
    db,
    size: int,
) -> list[tuple[str, bytes]]:
    """Generate PNG bytes for every ubicacion in ``estante_id`` concurrently."""
    from app.repositories import ubicacion_repository

    ubicaciones = await ubicacion_repository.list_ubicaciones_by_estante(db, estante_id)

    async def _qr_for(u: dict) -> tuple[str, bytes]:
        qr_valor = u["qr_valor"]
        png_bytes = await get_or_create_qr_bytes(qr_valor, size)
        return (qr_valor, png_bytes)

    return await asyncio.gather(*[_qr_for(u) for u in ubicaciones])


async def generate_a4_print_sheet(
    qr_items: list[tuple[str, bytes]],
    per_page: int,
) -> bytes:
    """Return a printable A4 PNG (possibly multi-page) as bytes."""
    if per_page not in _VALID_PER_PAGE:
        raise ValueError(f"per_page must be one of {sorted(_VALID_PER_PAGE)}")

    def _compose() -> bytes:
        sheet = _build_a4_sheet(qr_items, per_page)
        buffer: BinaryIO = BytesIO()
        sheet.save(buffer, format="PNG")
        return buffer.getvalue()

    return await asyncio.to_thread(_compose)


async def generate_pdf_print_sheet(
    qr_items: list[tuple[str, bytes]],
    per_page: int,
) -> bytes:
    """Return a multi-page A4 PDF with all QRs as bytes."""
    if per_page not in _VALID_PER_PAGE:
        raise ValueError(f"per_page must be one of {sorted(_VALID_PER_PAGE)}")

    return await asyncio.to_thread(_build_pdf, qr_items, per_page)
