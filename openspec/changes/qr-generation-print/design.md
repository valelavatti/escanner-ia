# Design: QR Generation and Printing

**Change**: `qr-generation-print`  
**Artifact store mode**: `openspec`  
**Execution mode**: `interactive`  
**Delivery strategy**: `ask-on-risk`

## 1. QR Service Architecture

New service: `backend/app/services/qr.py`.

- `get_or_create_qr_path(qr_valor: str, size: int) -> Path`  
  Returns the cached PNG path. If missing, delegates to `_generate_qr_image` and persists atomically.
- `_generate_qr_image(qr_valor: str, size: int) -> Image`  
  Calls `qrcode.make(qr_valor)`, converts to RGB, resizes to `(size, size)` with `Image.Resampling.NEAREST`, and returns the PIL image.
- Cache path: `{settings.qr_cache_dir}/{sanitized_qr_valor}_{size}.png`  
  Sanitization replaces spaces with `_` and strips path separators so `Pasillo 3-F1-C1` becomes `Pasillo_3-F1-C1_200.png`.
- All blocking PIL / `qrcode` / file writes run inside `asyncio.to_thread()`.
- Cache directory `Path(settings.qr_cache_dir)` is created on startup in `main.py` lifespan.
- Batch generation uses `asyncio.gather(...)` over per-QR `to_thread` calls.

## 2. A4 Sheet Layout Math

A4 page at 300 DPI: **2480 × 3508 px**.

Constants:

```text
PAGE_W, PAGE_H = 2480, 3508
MARGIN = 120 px
GAP = 80 px
LABEL_H = 80 px
CONTENT_W = PAGE_W - 2 * MARGIN
CONTENT_H = PAGE_H - 2 * MARGIN
```

`per_page` → grid `(cols, rows)`:

| per_page | cols | rows |
|----------|------|------|
| 1 | 1 | 1 |
| 2 | 1 | 2 |
| 4 | 2 | 2 |
| 6 | 2 | 3 |
| 8 | 2 | 4 |
| 9 | 3 | 3 |

Cell size and placement:

```text
cell_w = (CONTENT_W - (cols - 1) * GAP) / cols
cell_h = (CONTENT_H - (rows - 1) * GAP) / rows
qr_draw_size = min(size, cell_w, cell_h - LABEL_H)

x = MARGIN + col * (cell_w + GAP) + (cell_w - qr_draw_size) / 2
y = MARGIN + row * (cell_h + GAP) + (cell_h - LABEL_H - qr_draw_size) / 2
```

Each QR is drawn at `qr_draw_size`, then the `qr_valor` label is centered in the remaining `LABEL_H` space below it. If the estante has more ubicaciones than `per_page`, pages are stacked vertically into a single tall PNG (`PAGE_W × PAGE_H * n_pages`).

## 3. API Endpoint Design

`ubicaciones.py` adds:

- `GET /api/v1/ubicaciones/{ubicacion_id}/qr.png?size=200`
  - `Depends(get_current_user)`
  - `size`: `int`, 50–1000, default from `settings.qr_default_size`
  - 404 if ubicacion not found
  - Returns `Response(content=png_bytes, media_type="image/png")`

`estantes.py` adds:

- `GET /api/v1/estantes/{estante_id}/qrs`
  - `Depends(get_current_user)`
  - Lists ubicaciones for the estante; 404 if estante missing/soft-deleted
  - Generates each QR concurrently, writes a ZIP in a worker thread, returns `StreamingResponse(..., media_type="application/zip")`
  - ZIP entries: `{sanitized_qr_valor}.png`

- `GET /api/v1/estantes/{estante_id}/qrs/print?per_page=4&size=200`
  - `Depends(get_current_user)`
  - `per_page`: enum `[1, 2, 4, 6, 8, 9]`, default 4
  - `size`: 50–1000, default from settings
  - 404 if estante missing/soft-deleted
  - Builds the A4 PNG in a worker thread and returns `Response(content=png_bytes, media_type="image/png")`

## 4. Frontend Print UI Design

New component: `frontend/src/lib/components/QrPrintModal.svelte`.

Props: `estante: Estante`, `ubicaciones: Ubicacion[]`, `open: boolean`, `onClose: () => void`.

Controls:

- Title: `Imprimir QRs de {estante.nombre}`
- Dropdown "QRs por hoja": 1, 2, 4, 6, 8, 9 (default 4)
- Dropdown "Tamaño": Pequeño (150), Mediano (200), Grande (300) (default Mediano)
- Live SVG/HTML grid preview matching the selected `(cols, rows)`
- "Generar e imprimir" → calls `getEstanteQRPrintSheet` → opens blob URL in new window → triggers `window.print()`
- "Descargar ZIP" → calls `downloadEstanteQRsZip` → creates temporary anchor to download
- "Cerrar" → closes modal

Integration in `frontend/src/routes/admin/estantes/+page.svelte`:

- Add `import QrPrintModal from '$lib/components/QrPrintModal.svelte'`
- Add `qrPrintOpen = $state(false)`
- Add an "Imprimir QRs" button in the detail header (only when `activeUbicaciones.length > 0`)

API additions in `frontend/src/lib/api/client.ts`:

```ts
export async function getUbicacionQR(ubicacionId: number, size: number): Promise<Blob>
export async function downloadEstanteQRsZip(estanteId: number): Promise<Blob>
export async function getEstanteQRPrintSheet(estanteId: number, perPage: number, size: number): Promise<Blob>
```

Each helper performs an authenticated `fetch` and returns `response.blob()`, similar to `exportMovimientosCSV`.

Mobile: modal uses a bottom-sheet layout on narrow viewports (`@media (max-width: 640px)`), full-width, rounded top corners, and all buttons/selects meet the 48 px touch target minimum.

## 5. Configuration Changes

- `backend/app/core/config.py`: add
  ```python
  qr_cache_dir: str = "./qr_cache/"
  qr_default_size: int = 200
  ```
- `backend/app/main.py` lifespan: add
  ```python
  Path(settings.qr_cache_dir).mkdir(parents=True, exist_ok=True)
  ```
- `backend/requirements.txt`: add `qrcode[pil]==8.0`
- `.gitignore`: add `qr_cache/`

## 6. Sequence Diagrams

### Single QR

```text
Client → GET /ubicaciones/{id}/qr.png
  → Endpoint: get ubicacion, validate size
  → qr_service.get_or_create_qr_path(qr_valor, size)
    → cache path exists? return path
    → else _generate_qr_image in to_thread
      → qrcode.make → resize → save atomically
  → Endpoint reads bytes → Response(image/png)
```

### A4 Print Sheet

```text
Client → GET /estantes/{id}/qrs/print?per_page=4&size=200
  → Endpoint: get estante, 404 if missing/deleted
  → list_ubicaciones_by_estante
  → asyncio.gather(get_or_create_qr_path(u.qr_valor, size))
  → to_thread(build_a4_sheet)
    → for each page: Image.new(RGB, white)
    → paste QRs + draw labels
    → concatenate pages vertically
  → Response(image/png)
```

### Frontend Print Flow

```text
User clicks "Generar e imprimir"
  → getEstanteQRPrintSheet → Blob
  → window.open(URL.createObjectURL(blob))
  → new window renders <img> with print CSS
  → window.print()
```

## 7. ADRs

### ADR-001: PNG over PDF for print sheets

- **Choice**: Return printable PNG images instead of PDF.
- **Alternatives considered**: `fpdf2`, `reportlab`.
- **Rationale**: No extra dependency; browser print dialog handles PNG natively; keeps the backend stack smaller. Multi-page sheets are concatenated vertically and paginated by the browser.

### ADR-002: Disk cache over in-memory cache

- **Choice**: Cache QR PNGs on disk using deterministic filenames.
- **Alternatives considered**: In-memory dict, Redis.
- **Rationale**: QRs are deterministic and static; disk cache survives restarts, avoids memory pressure, and requires no additional infrastructure.

### ADR-003: Lazy generation over eager generation

- **Choice**: Generate QR PNGs only when first requested.
- **Alternatives considered**: Generate all QRs when an estante is created.
- **Rationale**: Estante creation stays fast; unused ubicaciones never consume CPU or disk; cache amortizes cost across repeated print requests.

## 8. Risk Forecast for sdd-tasks

Estimated changed lines:

| Component | Lines |
|-----------|-------|
| QR service | 80–120 |
| QR endpoints (3) | 80–120 |
| Frontend print modal | 150–250 |
| Config / main / requirements / gitignore | 10–20 |
| API client additions | 30–50 |
| **Total** | **~350–560** |

The total is near the 400-line PR threshold. With `ask-on-risk` delivery strategy, sdd-tasks should flag whether the modal or endpoint set should be split into a follow-up task. Risks are low to medium: cache concurrency is handled by atomic temp-file writes, and first-print latency for large estantes is mitigated by concurrent batch generation.

## Open Questions

- None blocking.
