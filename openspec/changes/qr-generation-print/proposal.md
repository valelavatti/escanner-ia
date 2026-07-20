# Proposal: QR Generation and Printing

## Intent

Transform the existing text QR values (`ubicaciones.qr_valor`) into printable PNG QR codes and expose A4 print sheets. Warehouse staff will be able to generate QR labels per estante and print them at selectable sizes (1, 2, 4, 6, 8 or 9 per A4 page).

## Scope

### In Scope
- Backend QR image service using `qrcode[pil]==8.0` with disk cache and non-blocking `asyncio.to_thread`.
- Single-QR endpoint: `GET /api/v1/ubicaciones/{id}/qr.png?size={px}`.
- Estante QR bundle endpoints: `GET /api/v1/estantes/{id}/qrs` (zip/PNG list) and `GET /api/v1/estantes/{id}/qrs/print` (A4 sheet).
- Config additions: `qr_cache_dir`, `qr_default_size`; `.gitignore` for `qr_cache/`.
- SvelteKit print UI on the estante admin page: select estante, QRs per page, size, then open printable sheet.
- Lazy generation: QR PNGs are generated on first request and cached; existing `qr_valor` strings remain the source of truth.

### Out of Scope
- QR styling customization (colors, logos, error correction levels).
- Batch/multi-estante print jobs.
- Physical-layout-aware positioning on A4.
- Scan-to-verify QR validation workflow.

## Capabilities

### New Capabilities
- `qr-generation-service`: Generate, resize, cache and serve individual QR PNGs from `qr_valor` strings.
- `qr-print-endpoints`: Bundle an estante's QRs and render A4 printable sheets.
- `qr-print-ui`: Frontend controls for estante selection, per-page count and QR size.

### Modified Capabilities
- None at the spec level; estante creation continues to generate only `qr_valor` text strings.

## Approach

Use the user's reference implementation: `qrcode.make(qr_valor)` produces a PIL image, resized with `Image.Resampling.NEAREST`, wrapped in `asyncio.to_thread`. Cache path: `{QR_CACHE_DIR}/{qr_valor}_{size}.png`. `get_or_create_qr_path()` reuses cached files or generates and persists new ones via `to_thread`.

For A4 sheets, compose cached PNGs onto an A4 canvas (2480×3508 px at 300 DPI or CSS `@media print`) using Pillow. Keep a pure-PNG option to avoid a PDF dependency, but evaluate `fpdf2` or `reportlab` if browser print of a large PNG is unwieldy.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/services/qr.py` | New | QR generation, resize, disk cache helpers. |
| `backend/app/api/v1/endpoints/ubicaciones.py` | Modified | Add single QR PNG endpoint. |
| `backend/app/api/v1/endpoints/estantes.py` | Modified | Add bundle and A4 print endpoints. |
| `backend/app/core/config.py` | Modified | Add `qr_cache_dir`, `qr_default_size`. |
| `backend/requirements.txt` | Modified | Add `qrcode[pil]==8.0`. |
| `frontend/src/routes/admin/estantes/+page.svelte` | Modified | Add print controls and preview link. |
| `.gitignore` | Modified | Ignore `qr_cache/`. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| OneDrive path with spaces breaks file I/O | Medium | Use `Path` from `pathlib`; validate cache dir on startup. |
| Cache dir missing on first run | Medium | Ensure directory creation in lifespan/startup event. |
| Large estantes (7×5) slow first print | Medium | Generate per-QR concurrently with `asyncio.gather` + `to_thread`; cache survives restarts. |
| PDF dependency bloat | Low | Default to PNG A4 sheet; defer PDF library decision to design phase. |

## Rollback Plan

1. Revert the four backend files and the frontend page.
2. Remove `qrcode[pil]==8.0` from `requirements.txt`.
3. Delete `qr_cache/` directory (or leave it; it is a pure cache).
4. Existing `qr_valor` strings and scanner lookup flow remain untouched, so no data migration is needed.

## Dependencies

- `qrcode[pil]==8.0` (Pillow included).
- Optional: `fpdf2` or `reportlab` if PDF output is chosen during design.

## Success Criteria

- [ ] `GET /api/v1/ubicaciones/{id}/qr.png?size=200` returns a valid PNG encoding the ubicacion's `qr_valor`.
- [ ] Repeated requests for the same `qr_valor` and size reuse the cached file.
- [ ] `GET /api/v1/estantes/{id}/qrs/print?per_page=4&size=200` returns an A4-ready image with 4 QR codes.
- [ ] Frontend print UI opens the generated sheet in a new tab and browser print produces a usable A4 page.
- [ ] Cache directory is created automatically and is ignored by git.
