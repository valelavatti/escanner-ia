# Tasks: Product Locations View

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~230-370 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | single PR |
| Delivery strategy | single-pr |
| Chain strategy | size-exception |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Backend endpoint + frontend fallback + card | PR 1 | Fully additive; existing QR-first flow untouched |

## Phase 1: Backend — Schemas & Repository

- [x] 1.1 Add `ProductoUbicacionItem` and `ProductoUbicacionesResponse` to `backend/app/schemas/productos.py` (~15 lines). Skill: `fastapi-templates`. Files: `schemas/productos.py`. Acceptance: Pydantic models compile; `stock_total` is a plain int.
- [x] 1.2 Add `get_producto_ubicaciones(db, sku, deposito_ids)` to `backend/app/repositories/movimiento_repository.py` (~50 lines). Skill: `SQLite Database Expert`. Files: `repositories/movimiento_repository.py`. Acceptance: two SELECTs (regular + Suelto) merged in Python; mirrors `get_producto_stock_total`; `deposito_ids=None/[]/[...]` contract matches `list_movimientos`.
- [x] 1.3 Add `GET /api/v1/productos/{codigo_de_barra}/ubicaciones` to `backend/app/api/v1/endpoints/productos.py` (~30 lines). Skill: `fastapi-templates`. Files: `endpoints/productos.py`. Acceptance: 200 with schema, 404 on unknown barcode, 401 unauth, no per-row `require_deposito_access`.

## Phase 2: Frontend — API Client & Component

- [x] 2.1 Add `ProductoUbicacionItem` + `ProductoUbicacionesResponse` types and `getProductoUbicaciones(codigo)` to `frontend/src/lib/api/client.ts` (~25 lines). Skill: `sveltekit-structure`. Files: `lib/api/client.ts`. Acceptance: function calls `api<T>`; throws `ApiError` on 404.
- [x] 2.2 Create `frontend/src/lib/components/ProductLocationsCard.svelte` (~150 lines). Skills: `sveltekit-structure`, `Frontend Responsive Design Standards`. Files: `lib/components/ProductLocationsCard.svelte`. Acceptance: tappable cards ≥48px; empty state copy exact from spec; "Suelto" pill when `estante_nombre === 'Suelto'`; "Cancelar" button.

## Phase 3: Frontend — Scanner Page Wiring

- [x] 3.1 Add 5 `$state` vars and import `ProductLocationsCard` + `getProductoUbicaciones` in `frontend/src/routes/scanner/+page.svelte` (~20 lines). Skill: `sveltekit-structure`. Files: `routes/scanner/+page.svelte`. Acceptance: imports compile; no behavior change yet.
- [x] 3.2 Replace `showError('Escaneá un QR de sector primero')` early-return with `getProductoUbicaciones` call; add `handleSelectLocation` + `handleCancelLocations` handlers (~50 lines). Skill: `sveltekit-structure`. Files: `routes/scanner/+page.svelte`. Acceptance: 404 → red flash "Producto no encontrado"; pause/resume scanner; debounce preserved.
- [x] 3.3 Add `{#if showLocationsCard}` render block after `lastScan` div (~10 lines). Skill: `sveltekit-structure`. Files: `routes/scanner/+page.svelte`. Acceptance: card mounts on `showLocationsCard=true`; `anchoredLocation` is set via the same shape as `selectUbicacion`.

## Phase 4: Manual Verification

- [x] 4.1 Verify backend spec scenarios: 2 regular shelves, Suelto-only, empty, 404, admin sees all, non-admin filtered, no-access returns `[]`. Files: `backend/`. Acceptance: every "Scenario" in `specs/product-locations.md` passes via `curl` against running backend.
- [x] 4.2 Verify frontend spec scenarios: QR-first flow unchanged, fallback shows card, tap anchors and shows `ProductCard`, Cancelar resumes, empty state copy, 404 red flash, debounce still applies. Files: `frontend/`. Acceptance: every "Scenario" in `specs/product-locations.md` and `specs/barcode-scanning-delta.md` passes manually.
- [x] 4.3 Verify existing QR-first flow byte-identical: `git diff` on the `if (location)` branch of `handleProductScan` shows zero changes. Files: `routes/scanner/+page.svelte`. Acceptance: only the `if (!location)` branch differs from main.
