# Tasks: QR Generation and Printing

**Change**: `qr-generation-print`  
**Artifact store mode**: `openspec`  
**Execution mode**: `interactive`  
**Delivery strategy**: `ask-on-risk`

## PR Slicing Recommendation

The design forecasts **~350–560 changed lines**, which crosses the 400-line review budget threshold when the frontend modal lands at the upper end. Plan **two chained PRs**:

- **PR 1 — Backend QR service and endpoints** (Phases 1–3)
- **PR 2 — Frontend print UI** (Phase 4)

This keeps each review focused and lets the backend contract stabilize before the SvelteKit layer consumes it.

---

## Phase 1: Config + Dependencies

### 1.1 Add `qrcode[pil]` dependency and ignore cache directory

**Skill to load / Context7 query needed**: `fastapi-templates`

**Depends on**: None

**Files to create/modify**:
- `backend/requirements.txt` (modify)
- `.gitignore` (modify)

**Acceptance criteria**:
- [x] `qrcode[pil]==8.0` is appended to `backend/requirements.txt`.
- [x] `qr_cache/` is appended to `.gitignore`.
- [x] A clean venv installs the backend without conflicts.

**Estimated lines**: 2–4

---

### 1.2 Add QR settings and lifespan cache-dir creation

**Skill to load / Context7 query needed**: `fastapi-templates`

**Depends on**: 1.1

**Files to create/modify**:
- `backend/app/core/config.py` (modify)
- `backend/app/main.py` (modify)

**Acceptance criteria**:
- [x] `Settings` exposes `qr_cache_dir: str = "./qr_cache/"` and `qr_default_size: int = 200`.
- [x] `lifespan` creates `Path(settings.qr_cache_dir).mkdir(parents=True, exist_ok=True)` before yielding.
- [x] The app starts successfully when the cache directory does not exist.
- [x] The app starts successfully when the cache directory already exists.

**Estimated lines**: 8–12

---

## Phase 2: QR Service

### 2.1 Create `qr.py` service with generation and disk cache helpers

**Skill to load / Context7 query needed**:
- `fastapi-templates`
- Context7 `/lincolnloop/python-qrcode`
- Context7 `/python-pillow/pillow`

**Depends on**: 1.2

**Files to create/modify**:
- `backend/app/services/qr.py` (create)

**Acceptance criteria**:
- [x] `get_or_create_qr_path(qr_valor: str, size: int) -> Path` returns the cached PNG path.
- [x] Cache filename sanitizes `qr_valor` by replacing spaces with `_` and stripping path separators.
- [x] Cache path follows `{settings.qr_cache_dir}/{sanitized_qr_valor}_{size}.png`.
- [x] `_generate_qr_image` uses `qrcode.make(qr_valor)`, converts to RGB, and resizes to `(size, size)` with `Image.Resampling.NEAREST`.
- [x] All blocking work (`qrcode.make`, PIL resize, file save) runs in `asyncio.to_thread()`.
- [x] Uncached generation is saved atomically via a temp file + rename to avoid partial reads.
- [x] Repeated calls with the same `(qr_valor, size)` reuse the existing file and do not regenerate.
- [x] Different sizes for the same `qr_valor` produce separate cache files.

**Estimated lines**: 60–90

---

### 2.2 Add A4 sheet composition helpers

**Skill to load / Context7 query needed**:
- `fastapi-templates`
- Context7 `/python-pillow/pillow`

**Depends on**: 2.1

**Files to create/modify**:
- `backend/app/services/qr.py` (modify)

**Acceptance criteria**:
- [x] Constants are defined: `PAGE_W = 2480`, `PAGE_H = 3508`, `MARGIN = 120`, `GAP = 80`, `LABEL_H = 80`.
- [x] `get_grid(per_page: int) -> tuple[int, int]` maps `per_page` to `(cols, rows)`: 1→(1,1), 2→(1,2), 4→(2,2), 6→(2,3), 8→(2,4), 9→(3,3).
- [x] `build_a4_sheet(qr_paths: list[Path], qr_valores: list[str], per_page: int, size: int) -> Image` is implemented.
- [x] Cell math centers each QR inside its cell and places the `qr_valor` label centered below it.
- [x] `qr_draw_size` is clamped to `min(size, cell_w, cell_h - LABEL_H)`.
- [x] If `len(qr_paths) > per_page`, pages are stacked vertically into one tall PNG.
- [x] The returned image is a valid RGB PNG.

**Estimated lines**: 70–100

---

## Phase 3: Backend Endpoints

### 3.1 Add single QR PNG endpoint to `ubicaciones.py`

**Skill to load / Context7 query needed**: `fastapi-templates`

**Depends on**: 2.1

**Files to create/modify**:
- `backend/app/api/v1/endpoints/ubicaciones.py` (modify)

**Acceptance criteria**:
- [x] `GET /api/v1/ubicaciones/{ubicacion_id}/qr.png` is registered.
- [x] Endpoint requires `Depends(get_current_user)`.
- [x] `size` query parameter defaults to `settings.qr_default_size` and is constrained to `50 <= size <= 1000` (422 otherwise).
- [x] 404 is returned if the ubicacion does not exist.
- [x] 200 response has `Content-Type: image/png` and the body is the cached PNG bytes.
- [x] Calling the endpoint twice for the same ubicacion and size hits the disk cache on the second request.

**Estimated lines**: 30–45

---

### 3.2 Add estante ZIP bundle and A4 print endpoints to `estantes.py`

**Skill to load / Context7 query needed**: `fastapi-templates`

**Depends on**: 2.2, 3.1

**Files to create/modify**:
- `backend/app/api/v1/endpoints/estantes.py` (modify)

**Acceptance criteria**:
- [x] `GET /api/v1/estantes/{estante_id}/qrs` returns a ZIP archive (`Content-Type: application/zip`).
- [x] ZIP endpoint requires `Depends(get_current_user)` and returns 404 if the estante is missing or soft-deleted.
- [x] ZIP entries are named `{sanitized_qr_valor}.png` and contain the default-size QR image.
- [x] QR generation for the ZIP runs concurrently via `asyncio.gather` + `to_thread`.
- [x] `GET /api/v1/estantes/{estante_id}/qrs/print` returns an A4 PNG sheet.
- [x] `per_page` query parameter accepts only `[1, 2, 4, 6, 8, 9]`, defaulting to 4 (422 otherwise).
- [x] `size` query parameter follows the same 50–1000 range as the single-QR endpoint.
- [x] Print endpoint returns 404 if the estante is missing or soft-deleted.
- [x] Print endpoint composes the sheet in a worker thread and returns `Content-Type: image/png`.
- [x] A 35-ubicacion estante with `per_page=4` produces a tall PNG with all QRs laid out across multiple A4 pages.

**Estimated lines**: 80–120

---

## Phase 4: Frontend Print UI

### 4.1 Add QR API helpers to `client.ts`

**Skill to load / Context7 query needed**: `sveltekit-structure`

**Depends on**: 3.2

**Files to create/modify**:
- `frontend/src/lib/api/client.ts` (modify)

**Acceptance criteria**:
- [ ] `getUbicacionQR(ubicacionId: number, size: number): Promise<Blob>` is exported.
- [ ] `downloadEstanteQRsZip(estanteId: number): Promise<Blob>` is exported.
- [ ] `getEstanteQRPrintSheet(estanteId: number, perPage: number, size: number): Promise<Blob>` is exported.
- [ ] Each helper performs an authenticated `fetch`, handles 401 by clearing the session and redirecting, and returns `response.blob()` on success.
- [ ] Non-OK responses throw `ApiError` with a readable message (reusing existing error extraction logic).

**Estimated lines**: 30–50

---

### 4.2 Create `QrPrintModal` component

**Skill to load / Context7 query needed**:
- `sveltekit-structure`
- `Frontend Responsive Design Standards`

**Depends on**: 4.1

**Files to create/modify**:
- `frontend/src/lib/components/QrPrintModal.svelte` (create)

**Acceptance criteria**:
- [ ] Component props match `estante: Estante`, `ubicaciones: Ubicacion[]`, `open: boolean`, `onClose: () => void`.
- [ ] Modal title reads `Imprimir QRs de {estante.nombre}`.
- [ ] Dropdown "QRs por hoja" offers 1, 2, 4, 6, 8, 9 and defaults to 4.
- [ ] Dropdown "Tamaño" offers Pequeño (150), Mediano (200), Grande (300) and defaults to Mediano.
- [ ] Live SVG/HTML grid preview updates when either dropdown changes, matching the `(cols, rows)` layout.
- [ ] "Generar e imprimir" button fetches the A4 PNG, opens it in a new tab via `window.open(URL.createObjectURL(blob))`, and triggers `window.print()` after load.
- [ ] "Descargar ZIP" button fetches the ZIP and initiates a browser download via a temporary anchor.
- [ ] "Cerrar" button calls `onClose`.
- [ ] Buttons show a loading state and are disabled while a request is in flight.
- [ ] Errors (network, 404, 401) display a clear message in the modal.
- [ ] On viewports narrower than 640 px the modal renders as a bottom sheet (anchored bottom, rounded top corners, full width).
- [ ] All interactive targets meet the 48×48 px minimum.

**Estimated lines**: 150–250

---

### 4.3 Wire modal to estante detail page

**Skill to load / Context7 query needed**:
- `sveltekit-structure`
- `Frontend Responsive Design Standards`

**Depends on**: 4.2

**Files to create/modify**:
- `frontend/src/routes/admin/estantes/+page.svelte` (modify)

**Acceptance criteria**:
- [ ] `QrPrintModal` is imported from `$lib/components/QrPrintModal.svelte`.
- [ ] `qrPrintOpen = $state(false)` is added.
- [ ] An "Imprimir QRs" button is shown in the detail header only when `activeUbicaciones.length > 0`.
- [ ] The button uses the existing `button button--primary` style and is disabled while loading.
- [ ] Clicking the button opens `QrPrintModal` with the current estante and active ubicaciones.
- [ ] Closing the modal resets `qrPrintOpen` to `false`.

**Estimated lines**: 20–35

---

## Review Workload Forecast

| Component | Lines |
|-----------|-------|
| QR service | 80–120 |
| QR endpoints (3) | 80–120 |
| Frontend print modal | 150–250 |
| Config / main / requirements / gitignore | 10–20 |
| API client additions | 30–50 |
| **Total** | **~350–560** |

- **Total estimated lines**: ~350–560
- **Chained PRs recommended**: **Yes** — split into PR 1 (Phases 1–3, backend) and PR 2 (Phase 4, frontend)
- **400-line budget risk**: **Medium–High** — the frontend modal is the dominant variable and can push the combined change above 400 lines
- **Decision needed before apply**: **Yes** — confirm whether to proceed as two chained PRs or accept a single larger PR given the interactive `ask-on-risk` gate

---

## Task Execution Order

1. 1.1 → 1.2 → 2.1 → 2.2 → 3.1 → 3.2 (PR 1)
2. 4.1 → 4.2 → 4.3 (PR 2)
