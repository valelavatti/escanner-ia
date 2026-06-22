# Tasks: ASG Scanner — Accesaniga Stock Control App

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~3,900 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Bootstrap+Schema+Auth) → PR 2 (Excel Import) → PR 3 (Shelf Admin+Ubicaciones) → PR 4 (Scanner) → PR 5 (Stock Management) → PR 6 (Visual Map) → PR 7 (Audit Trail) → PR 8 (Integration+PWA+Polish). High-risk PRs 1–6 should be sub-sliced into reviewable units. |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending — orchestrator will ask the user to select `stacked-to-main` or `feature-branch-chain` |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Depends on | Notes |
|------|------|-----------|------------|-------|
| 1 | Bootstrap repo, FastAPI + SvelteKit scaffold, SQLite WAL + migration runner | PR 1a | — | Base = main |
| 2 | Database schema + indexes + seed users | PR 1b | Unit 1 | |
| 3 | Auth backend + frontend login/guard | PR 1c | Unit 2 | |
| 4 | Excel import backend (pandas validation, dedup, transaction) | PR 2a | Unit 3 | |
| 5 | Excel import frontend upload UI | PR 2b | Unit 4 | |
| 6 | Estantes/Ubicaciones backend + QR generation | PR 3a | Unit 3 | |
| 7 | Shelf admin UI + soft-delete warnings | PR 3b | Unit 6 | |
| 8 | Scanner html5-qrcode wrapper + lifecycle + camera errors | PR 4a | Unit 3 | Context7 `/mebjas/html5-qrcode` |
| 9 | Scanner format branch + debounce + sector lookup | PR 4b | Units 8, 6 | Context7 `/mebjas/html5-qrcode` |
| 10 | Movimientos backend + SQLITE_BUSY retry + CSV export | PR 5a | Unit 6 | |
| 11 | Product card, stock input, scanner save flow | PR 5b | Units 10, 9 | |
| 12 | Visual map render (WarehouseMap + ShelfGrid + cells) | PR 6a | Unit 6 | |
| 13 | Visual map interaction (selection, detail panel) | PR 6b | Unit 12 | |
| 14 | Visual map API integration (assign/relocation) | PR 6c | Units 13, 10 | |
| 15 | Audit trail list + filters + CSV download | PR 7 | Unit 10 | |
| 16 | PWA manifest/service worker, safe-area, end-to-end QA | PR 8 | Units 11, 14, 15 | |

---

## Phase 0: Project Bootstrap

- [x] **0.1 Bootstrap FastAPI backend scaffold and project structure**
  - **Skill to load:** `fastapi-templates`
  - **Context7 query:** none
  - **Depends on:** —
  - **Capability:** infrastructure
  - **Files to create/modify:** `backend/pyproject.toml`, `backend/requirements.txt`, `backend/main.py`, `backend/app/__init__.py`, `backend/app/core/config.py`, `backend/app/api/__init__.py`, `backend/app/repositories/__init__.py`
  - **Acceptance criteria:**
    - [ ] `uvicorn backend.main:app --reload` starts without errors.
    - [ ] `GET /health` (or root ping) returns HTTP 200.
  - **Estimated lines:** 90
  - **PR slice:** PR 1a

- [x] **0.2 Bootstrap SvelteKit PWA frontend and static build target**
  - **Skill to load:** `sveltekit-structure`, `Frontend Responsive Design Standards`
  - **Context7 query:** none
  - **Depends on:** —
  - **Capability:** infrastructure
  - **Files to create/modify:** `frontend/package.json`, `frontend/svelte.config.js`, `frontend/vite.config.ts`, `frontend/src/app.html`, `frontend/src/app.css`, `frontend/static/manifest.json`, `frontend/static/icon-192.png`
  - **Acceptance criteria:**
    - [ ] `npm install && npm run build` produces `frontend/build/`.
    - [ ] `manifest.json` exists and `app.html` includes `viewport-fit=cover`.
  - **Estimated lines:** 110
  - **PR slice:** PR 1a

- [x] **0.3 Configure SQLite connection pool, WAL pragmas, and migration runner**
  - **Skill to load:** `fastapi-templates`, `SQLite Database Expert`
  - **Context7 query:** none
  - **Depends on:** 0.1
  - **Capability:** infrastructure
  - **Files to create/modify:** `backend/app/core/database.py`, `backend/app/core/migrations.py`, `backend/migrations/.gitkeep`
  - **Acceptance criteria:**
    - [ ] Every new connection runs `PRAGMA foreign_keys = ON`, `journal_mode = WAL`, `synchronous = NORMAL`, `busy_timeout = 5000`, `temp_store = MEMORY`.
    - [ ] Migration runner executes versioned SQL scripts in order on startup.
  - **Estimated lines:** 90
  - **PR slice:** PR 1a

- [ ] **0.4 Create shared TypeScript types and API client stub**
  - **Skill to load:** `sveltekit-structure`
  - **Context7 query:** none
  - **Depends on:** 0.2
  - **Capability:** infrastructure
  - **Files to create/modify:** `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/config.ts`
  - **Acceptance criteria:**
    - [ ] Types mirror backend Pydantic schemas (`UserSession`, `ProductOut`, `UbicacionOut`, `MovimientoOut`, etc.).
    - [ ] `api` client sets `Accept`/`Content-Type: application/json` and reads base URL from env.
  - **Estimated lines:** 70
  - **PR slice:** PR 1a

- [ ] **0.5 Implement root layout, auth guard, bottom nav, and safe-area insets**
  - **Skill to load:** `sveltekit-structure`, `Frontend Responsive Design Standards`
  - **Context7 query:** none
  - **Depends on:** 0.2, 0.4
  - **Capability:** auth-session
  - **Files to create/modify:** `frontend/src/routes/+layout.svelte`, `frontend/src/routes/+page.svelte`, `frontend/src/lib/components/BottomNav.svelte`, `frontend/src/lib/stores/session.ts`
  - **Acceptance criteria:**
    - [ ] Unauthenticated users on protected routes are redirected to `/login`.
    - [ ] Bottom nav renders on `/scanner`, `/mapa`, `/historial`, `/admin/**`.
    - [ ] Safe-area insets applied via `env(safe-area-inset-*)`.
  - **Estimated lines:** 110
  - **PR slice:** PR 1c

---

## Phase 1: Database Schema

- [x] **1.1 Create migration v1 for all core tables**
  - **Skill to load:** `SQLite Database Expert`
  - **Context7 query:** none
  - **Depends on:** 0.3
  - **Capability:** infrastructure
  - **Files to create/modify:** `backend/migrations/001_create_tables.sql`, `backend/app/core/migrations.py`
  - **Acceptance criteria:**
    - [ ] Tables `productos`, `estantes`, `ubicaciones`, `usuarios`, `sessions`, `movimientos` created with correct columns, types, CHECK constraints, and foreign keys per design section 2.
    - [ ] Migration runs idempotently.
  - **Estimated lines:** 120
  - **PR slice:** PR 1b

- [x] **1.2 Create indexes and foreign-key enforcement migration**
  - **Skill to load:** `SQLite Database Expert`
  - **Context7 query:** none
  - **Depends on:** 1.1
  - **Capability:** infrastructure
  - **Files to create/modify:** `backend/migrations/002_create_indexes.sql`
  - **Acceptance criteria:**
    - [ ] Indexes exist for `productos(codigo_de_barra, sku)`, `ubicaciones(estante_id, qr_valor, producto_id)`, `movimientos(timestamp DESC, usuario_id, producto_id, ubicacion_id)`, `sessions(token, expires_at)`, and partial `estantes(deleted_at)`.
  - **Estimated lines:** 80
  - **PR slice:** PR 1b

- [x] **1.3 Seed default usuarios migration**
  - **Skill to load:** `SQLite Database Expert`
  - **Context7 query:** none
  - **Depends on:** 1.1
  - **Capability:** auth-session
  - **Files to create/modify:** `backend/migrations/003_seed_users.sql`
  - **Acceptance criteria:**
    - [ ] Inserts `Admin`, `Operario 1`, `Operario 2` only when `usuarios` is empty.
  - **Estimated lines:** 40
  - **PR slice:** PR 1b

- [x] **1.4 Wire migration runner into FastAPI startup lifespan**
  - **Skill to load:** `fastapi-templates`, `SQLite Database Expert`
  - **Context7 query:** none
  - **Depends on:** 1.1, 1.2, 1.3
  - **Capability:** infrastructure
  - **Files to create/modify:** `backend/main.py`, `backend/app/core/database.py`
  - **Acceptance criteria:**
    - [ ] Server startup executes pending migrations before accepting requests.
    - [ ] Migration failure prevents startup and logs the failing script.
  - **Estimated lines:** 60
  - **PR slice:** PR 1b

---

## Phase 2: Auth Session

- [x] **2.1 Implement usuarios and sessions repositories**
  - **Skill to load:** `fastapi-templates`, `SQLite Database Expert`
  - **Context7 query:** none
  - **Depends on:** 1.4
  - **Capability:** auth-session
  - **Files to create/modify:** `backend/app/repositories/auth_repository.py`, `backend/app/repositories/usuario_repository.py`
  - **Acceptance criteria:**
    - [x] `get_user_by_name`, `create_session`, `get_session`, `delete_session` use parameterized queries.
    - [x] Sessions have expiry (default 8h).
  - **Estimated lines:** 90
  - **PR slice:** PR 1c

- [x] **2.2 Implement auth endpoints and session dependency**
  - **Skill to load:** `fastapi-templates`, `SQLite Database Expert`
  - **Context7 query:** none
  - **Depends on:** 2.1
  - **Capability:** auth-session
  - **Files to create/modify:** `backend/app/api/v1/endpoints/auth.py`, `backend/app/api/v1/deps.py`, `backend/app/schemas/auth.py`, `backend/app/api/v1/router.py`
  - **Acceptance criteria:**
    - [x] `POST /api/v1/auth/login` returns `LoginResponse` (spec scenario 1).
    - [x] `POST /api/v1/auth/logout` invalidates session (spec scenario 5).
    - [x] `GET /api/v1/auth/me` returns current session.
    - [x] Protected routes return HTTP 401 for missing/invalid tokens (spec scenario 3).
  - **Estimated lines:** 130
  - **PR slice:** PR 1c

- [x] **2.3 Implement frontend session store and authenticated API client**
  - **Skill to load:** `sveltekit-structure`
  - **Context7 query:** none
  - **Depends on:** 0.4, 2.2 (backend contract)
  - **Capability:** auth-session
  - **Files to create/modify:** `frontend/src/lib/stores/session.ts`, `frontend/src/lib/api/client.ts`
  - **Acceptance criteria:**
    - [x] `sessionStore` persists token (e.g., `localStorage`) and user info.
    - [x] `api` attaches `Authorization` header; 401 redirects to `/login`.
  - **Estimated lines:** 70
  - **PR slice:** PR 1c

- [x] **2.4 Implement login page and root auth guard redirect**
  - **Skill to load:** `sveltekit-structure`, `Frontend Responsive Design Standards`
  - **Context7 query:** none
  - **Depends on:** 0.5, 2.3
  - **Capability:** auth-session
  - **Files to create/modify:** `frontend/src/routes/login/+page.svelte`, `frontend/src/routes/+layout.svelte`
  - **Acceptance criteria:**
    - [x] Empty name blocked client-side with validation message (spec scenario 2).
    - [x] Login calls `/api/v1/auth/login`; success redirects to `/` (scanner placeholder).
    - [x] Auth guard redirects unauthenticated users to `/login` and authenticated users away from `/login`.
  - **Estimated lines:** 100
  - **PR slice:** PR 1c

---

## Phase 3: Excel Import

- [x] **3.1 Implement productos repository with search and barcode lookup**
  - **Skill to load:** `fastapi-templates`, `SQLite Database Expert`
  - **Context7 query:** none
  - **Depends on:** 1.4
  - **Capability:** excel-import
  - **Files to create/modify:** `backend/app/repositories/producto_repository.py`, `backend/app/schemas/productos.py`, `backend/app/api/v1/endpoints/productos.py`, `backend/app/api/v1/router.py`
  - **Acceptance criteria:**
    - [x] Search by `sku`/`descripcion`/`codigo_de_barra` with query param.
    - [x] Lookup by exact `codigo_de_barra`.
    - [x] All queries parameterized.
  - **Estimated lines:** 80
  - **PR slice:** PR 2a

- [ ] **3.2 Implement `/api/import/excel` endpoint with pandas validation and duplicate strategies**
  - **Skill to load:** `fastapi-templates`, `pandas-pro`, `SQLite Database Expert`
  - **Context7 query:** none
  - **Depends on:** 2.2 (auth), 3.1
  - **Capability:** excel-import
  - **Files to create/modify:** `backend/app/api/import_excel.py`, `backend/app/services/excel_import.py`, `backend/app/schemas/import_excel.py`, `backend/main.py`
  - **Acceptance criteria:**
    - [ ] Validates required columns `sku`, `descripcion`, `codigo_de_barra` (spec scenario 2).
    - [ ] Drops completely empty rows silently (spec scenario 3).
    - [ ] Supports `duplicate_strategy=error|skip|overwrite` (spec scenarios 4–6).
    - [ ] Rejects barcode conflicts with existing different SKU (spec scenario 7).
    - [ ] Wraps writes in a SQLite transaction; any error rolls back all changes.
  - **Estimated lines:** 180
  - **PR slice:** PR 2a

- [x] **3.3 Implement Excel upload UI in `/admin/import`**
  - **Skill to load:** `sveltekit-structure`, `Frontend Responsive Design Standards`
  - **Context7 query:** none
  - **Depends on:** 2.4 (login), 3.2 (backend)
  - **Capability:** excel-import
  - **Files to create/modify:** `frontend/src/routes/admin/import/+page.svelte`, `frontend/src/routes/admin/import/+page.ts`, `frontend/src/lib/api/client.ts`, `frontend/src/routes/+page.svelte`
  - **Acceptance criteria:**
    - [x] File input accepts `.xlsx` and `.xls`.
    - [x] Upload shows loading state.
    - [x] Result summary shows imported/skipped/conflicts/overwritten and error list.
  - **Estimated lines:** 130
  - **PR slice:** PR 2b

- [ ] **3.4 Add backend integration tests for Excel import scenarios**
  - **Skill to load:** `fastapi-templates`, `pandas-pro`
  - **Context7 query:** none
  - **Depends on:** 3.2
  - **Capability:** excel-import
  - **Files to create/modify:** `backend/tests/test_import_excel.py`, `backend/tests/fixtures/products_valid.xlsx`, `backend/tests/fixtures/products_missing_col.xlsx`, `backend/tests/fixtures/products_duplicates.xlsx`, `backend/tests/fixtures/products_barcode_conflict.xlsx`
  - **Acceptance criteria:**
    - [ ] Covers spec scenarios 1–7: happy path, missing columns, empty rows, duplicate strategies, barcode conflicts.
  - **Estimated lines:** 120
  - **PR slice:** PR 2b

---

## Phase 4: Shelf Admin + Ubicaciones

- [x] **4.1 Implement estantes and ubicaciones repositories**
  - **Skill to load:** `fastapi-templates`, `SQLite Database Expert`
  - **Context7 query:** none
  - **Depends on:** 1.4
  - **Capability:** shelf-admin
  - **Files to create/modify:** `backend/app/repositories/estantes.py`, `backend/app/repositories/ubicaciones.py`, `backend/app/schemas/estantes.py`, `backend/app/schemas/ubicaciones.py`
  - **Acceptance criteria:**
    - [ ] Create `estante` with `filas`/`columnas` auto-generates `filas * columnas` `ubicaciones` with `qr_valor = {nombre}-F{fila}-C{columna}` (spec scenario 1, 6).
    - [ ] Dimension updates preserve in-bounds cells, flag out-of-bounds as `fuera_de_rango`, generate new cells (spec scenarios 2–3).
    - [ ] Soft delete sets `deleted_at`; duplicate name returns clear 400 (spec scenarios 4–5).
  - **Estimated lines:** 160
  - **PR slice:** PR 3a

- [x] **4.2 Implement `/api/estantes` and `/api/ubicaciones` endpoints**
  - **Skill to load:** `fastapi-templates`, `SQLite Database Expert`
  - **Context7 query:** none
  - **Depends on:** 2.2, 4.1
  - **Capability:** shelf-admin
  - **Files to create/modify:** `backend/app/api/estantes.py`, `backend/app/api/ubicaciones.py`, `backend/main.py`
  - **Acceptance criteria:**
    - [ ] `POST /api/estantes` creates shelf + cells.
    - [ ] `GET /api/estantes` lists shelves including soft-deleted flag.
    - [ ] `PUT /api/estantes/{id}` updates dims and returns impacted ubicaciones.
    - [ ] `DELETE /api/estantes/{id}` soft deletes.
    - [ ] `GET /api/ubicaciones?estante_id=` returns filtered cells.
  - **Estimated lines:** 110
  - **PR slice:** PR 3a

- [x] **4.3 Implement shelf admin UI with dimension form and soft-delete warnings**
  - **Skill to load:** `sveltekit-structure`, `Frontend Responsive Design Standards`
  - **Context7 query:** none
  - **Depends on:** 2.4, 4.2
  - **Capability:** shelf-admin
  - **Files to create/modify:** `frontend/src/routes/admin/estantes/+page.svelte`, `frontend/src/routes/admin/estantes/+page.ts`, `frontend/src/routes/admin/+layout.svelte`, `frontend/src/lib/api/client.ts`, `frontend/src/routes/+page.svelte`
  - **Acceptance criteria:**
    - [x] Create/edit form validates `filas`/`columnas` (1–50) and `orden_visual`.
    - [x] Shrinking dimensions shows warning and requires confirmation (spec scenario 3).
    - [x] Delete shows warning that history is preserved (spec scenario 4).
  - **Estimated lines:** 150
  - **PR slice:** PR 3b

- [x] **4.4 Implement `/api/sectores/lookup` endpoint for QR sector anchoring**
  - **Skill to load:** `fastapi-templates`, `SQLite Database Expert`
  - **Context7 query:** none
  - **Depends on:** 4.2
  - **Capability:** barcode-scanning, shelf-admin
  - **Files to create/modify:** `backend/app/api/sectores.py`, `backend/app/repositories/ubicaciones.py`, `backend/main.py`
  - **Acceptance criteria:**
    - [ ] `GET /api/sectores/lookup?qr_valor=` returns `UbicacionOut` for active ubicacion or 404.
  - **Estimated lines:** 60
  - **PR slice:** PR 3a

---

## Phase 5: Barcode Scanning

- [x] **5.1 Create `Scanner.svelte` wrapper for html5-qrcode with lifecycle and camera error handling**
  - **Skill to load:** `sveltekit-structure`, `Frontend Responsive Design Standards`
  - **Context7 query:** `/mebjas/html5-qrcode` (scanner lifecycle, `stop()`/`clear()`, camera permissions, `Html5QrcodeScannerState`)
  - **Depends on:** 0.2
  - **Capability:** barcode-scanning
  - **Files to create/modify:** `frontend/src/lib/components/Scanner.svelte`, `frontend/src/routes/scanner/+page.ts`
  - **Acceptance criteria:**
    - [ ] Initializes `Html5QrcodeScanner` on mount with `formatsToSupport: [QR_CODE, EAN_13, CODE_128, UPC_A]`, `facingMode: "environment"`, torch/zoom controls.
    - [ ] `onDestroy` pauses/stops/clears and releases camera (spec scenario 6).
    - [ ] Camera permission denial shows fallback text and retry button (spec scenario 5).
    - [ ] Route disables SSR (`export const ssr = false`).
  - **Estimated lines:** 140
  - **PR slice:** PR 4a

- [x] **5.2 Add scanner format detection, debounce, and anchored-location flow**
  - **Skill to load:** `sveltekit-structure`
  - **Context7 query:** `/mebjas/html5-qrcode` (format detection callback, `result.result.format.formatName`, `pause()`/`resume()`)
  - **Depends on:** 5.1, 2.3 (session), 4.4 (sector lookup), 3.1 (product lookup)
  - **Capability:** barcode-scanning
  - **Files to create/modify:** `frontend/src/lib/components/Scanner.svelte`, `frontend/src/lib/stores/scanner.ts`, `frontend/src/routes/scanner/+page.svelte`
  - **Acceptance criteria:**
    - [ ] 2-second debounce on identical code (spec scenario 7).
    - [ ] `QR_CODE` scans call `/api/sectores/lookup` and anchor location (spec scenario 1, 4).
    - [ ] Barcode scans call `/api/productos/{codigo}` only when location anchored; warns otherwise (spec scenario 2, 6).
    - [ ] Unknown product shows "Producto no encontrado" (spec scenario 3).
  - **Estimated lines:** 130
  - **PR slice:** PR 4b

- [x] **5.3 Build `/scanner` page layout with anchored location banner and scan status**
  - **Skill to load:** `sveltekit-structure`, `Frontend Responsive Design Standards`
  - **Context7 query:** none
  - **Depends on:** 5.2
  - **Capability:** barcode-scanning
  - **Files to create/modify:** `frontend/src/routes/scanner/+page.svelte`
  - **Acceptance criteria:**
    - [ ] Page displays current anchored sector or prompt to scan QR.
    - [ ] 48px tap targets for all controls.
    - [ ] Navigating away releases camera.
  - **Estimated lines:** 80
  - **PR slice:** PR 4b

---

## Phase 6: Stock Management

- [x] **6.1 Implement movimientos repository with transaction, stock chaining, and SQLITE_BUSY retry**
  - **Skill to load:** `fastapi-templates`, `SQLite Database Expert`
  - **Context7 query:** none
  - **Depends on:** 1.4, 2.1
  - **Capability:** stock-management
  - **Files to create/modify:** `backend/app/repositories/movimiento_repository.py`
  - **Acceptance criteria:**
    - [x] `alta` adds quantity; `ajuste` sets absolute stock (spec scenarios 1–2).
    - [x] Rejects negative `stock_nuevo` (spec scenario 3).
    - [x] Retry on `SQLITE_BUSY` up to 3 times (50ms, 100ms, 200ms) then HTTP 503 (spec scenario 5).
    - [x] Concurrent writes chain stock correctly (spec scenario 4).
  - **Estimated lines:** 150
  - **PR slice:** PR 5a

- [x] **6.2 Implement `/api/movimientos` endpoints (POST, GET filters/pagination, CSV export)**
  - **Skill to load:** `fastapi-templates`, `SQLite Database Expert`
  - **Context7 query:** none
  - **Depends on:** 6.1
  - **Capability:** stock-management, audit-trail
  - **Files to create/modify:** `backend/app/api/v1/endpoints/movimientos.py`, `backend/app/schemas/movimiento.py`, `backend/app/api/v1/router.py`
  - **Acceptance criteria:**
    - [x] `POST /api/movimientos` returns `MovimientoOut`.
    - [x] `GET /api/movimientos` filters by `usuario_id`, `producto_id`, `ubicacion_id`, `desde`, `hasta` and paginates.
    - [x] `GET /api/movimientos/export.csv` streams UTF-8 CSV with headers `id,usuario,producto_sku,producto_descripcion,estante,fila,columna,cantidad,stock_anterior,stock_nuevo,fecha_hora,tipo`.
  - **Estimated lines:** 140
  - **PR slice:** PR 5a

- [x] **6.3 Create `ProductCard` and `StockInput` components**
  - **Skill to load:** `sveltekit-structure`, `Frontend Responsive Design Standards`
  - **Context7 query:** none
  - **Depends on:** 0.4
  - **Capability:** stock-management
  - **Files to create/modify:** `frontend/src/lib/components/ProductCard.svelte`, `frontend/src/lib/components/StockInput.svelte`
  - **Acceptance criteria:**
    - [ ] `ProductCard` shows sku, descripcion, and `stock_actual` for anchored ubicacion.
    - [ ] `StockInput` has numeric quantity input, `alta`/`ajuste` toggle, and `Guardar` button.
    - [ ] Touch targets minimum 48x48px.
  - **Estimated lines:** 100
  - **PR slice:** PR 5b

- [x] **6.4 Wire scanner save flow to `/api/movimientos` with success/error feedback**
  - **Skill to load:** `sveltekit-structure`, `Frontend Responsive Design Standards`
  - **Context7 query:** none
  - **Depends on:** 5.2, 6.2, 6.3
  - **Capability:** stock-management
  - **Files to create/modify:** `frontend/src/routes/scanner/+page.svelte`, `frontend/src/lib/stores/scanner.ts`
  - **Acceptance criteria:**
    - [ ] `Guardar` POSTs `{ubicacion_id, cantidad, tipo}` from scannerStore.
    - [ ] On success shows toast, keeps location anchored, clears last product.
    - [ ] On 503 shows retry button; form disabled while `isSaving`.
  - **Estimated lines:** 90
  - **PR slice:** PR 5b

---

## Phase 7: Visual Map

- [ ] **7.1 Create map store and `/mapa` page shell with SSR disabled**
  - **Skill to load:** `sveltekit-structure`
  - **Context7 query:** none
  - **Depends on:** 0.4, 2.3
  - **Capability:** visual-map
  - **Files to create/modify:** `frontend/src/lib/stores/map.ts`, `frontend/src/routes/mapa/+page.svelte`, `frontend/src/routes/mapa/+page.ts`
  - **Acceptance criteria:**
    - [ ] `mapStore` holds `estantes`, `ubicaciones` keyed by `estante_id`, and `selectedCellId`.
    - [ ] Page fetches `/api/estantes` and `/api/ubicaciones`; handles network error with offline placeholder (spec scenario 6).
    - [ ] Route disables SSR.
  - **Estimated lines:** 80
  - **PR slice:** PR 6a

- [ ] **7.2 Build `ShelfGrid.svelte` with variable rows/columns and 48px cells**
  - **Skill to load:** `sveltekit-structure`, `Frontend Responsive Design Standards`
  - **Context7 query:** none
  - **Depends on:** 7.1
  - **Capability:** visual-map
  - **Files to create/modify:** `frontend/src/lib/components/ShelfGrid.svelte`
  - **Acceptance criteria:**
    - [ ] CSS Grid uses inline `--rows`/`--cols` custom properties.
    - [ ] `grid-template-columns: repeat(var(--cols), minmax(48px, 1fr))`.
    - [ ] Allows horizontal scroll on very narrow screens to preserve 48px cells (spec scenario 1).
  - **Estimated lines:** 90
  - **PR slice:** PR 6a

- [ ] **7.3 Build `LocationCell.svelte` with color coding and tap selection**
  - **Skill to load:** `sveltekit-structure`, `Frontend Responsive Design Standards`
  - **Context7 query:** none
  - **Depends on:** 7.2
  - **Capability:** visual-map
  - **Files to create/modify:** `frontend/src/lib/components/LocationCell.svelte`
  - **Acceptance criteria:**
    - [ ] Color classes: empty gray, ok green, low yellow (<=5), selected blue.
    - [ ] Tap updates `selectedCellId`; no backend write on tap (spec scenarios 3–4).
  - **Estimated lines:** 80
  - **PR slice:** PR 6b

- [ ] **7.4 Build `WarehouseMap.svelte` stacking shelves and detail panel**
  - **Skill to load:** `sveltekit-structure`, `Frontend Responsive Design Standards`
  - **Context7 query:** none
  - **Depends on:** 7.3
  - **Capability:** visual-map
  - **Files to create/modify:** `frontend/src/lib/components/WarehouseMap.svelte`
  - **Acceptance criteria:**
    - [ ] Iterates `estantes` sorted by `orden_visual`.
    - [ ] Renders `ShelfGrid` per estante with its ubicaciones.
    - [ ] Detail panel opens below tapped shelf showing empty/occupied info (spec scenarios 2–3).
  - **Estimated lines:** 100
  - **PR slice:** PR 6b

- [ ] **7.5 Implement ubicacion assignment/relocation API and map integration**
  - **Skill to load:** `fastapi-templates`, `SQLite Database Expert`, `sveltekit-structure`
  - **Context7 query:** none
  - **Depends on:** 4.2, 7.4
  - **Capability:** visual-map
  - **Files to create/modify:** `backend/app/api/ubicaciones.py` (`assign`), `frontend/src/lib/components/WarehouseMap.svelte`, `frontend/src/lib/api.ts`
  - **Acceptance criteria:**
    - [ ] `PUT /api/ubicaciones/{id}/assign` updates `producto_id`.
    - [ ] Empty cell panel offers "Asignar producto escaneado" or search (spec scenario 2).
    - [ ] Occupied panel shows `Reubicar` button with explicit confirmation.
    - [ ] Success updates cell color without full reload.
  - **Estimated lines:** 120
  - **PR slice:** PR 6c

---

## Phase 8: Audit Trail

- [ ] **8.1 Implement `/historial` page with filterable audit list**
  - **Skill to load:** `sveltekit-structure`, `Frontend Responsive Design Standards`
  - **Context7 query:** none
  - **Depends on:** 6.2 (backend), 2.3
  - **Capability:** audit-trail
  - **Files to create/modify:** `frontend/src/routes/historial/+page.svelte`, `frontend/src/lib/components/AuditTrail.svelte`, `frontend/src/lib/components/MovimientoFilters.svelte`
  - **Acceptance criteria:**
    - [ ] Renders movements ordered by timestamp DESC with user, product SKU, location, qty, timestamp.
    - [ ] 48px minimum row height.
    - [ ] Filters by user, product, location, date range; pagination via `Cargar mas` (spec scenarios 1–3, 7).
  - **Estimated lines:** 130
  - **PR slice:** PR 7

- [ ] **8.2 Add CSV export download from audit trail UI**
  - **Skill to load:** `sveltekit-structure`, `Frontend Responsive Design Standards`
  - **Context7 query:** none
  - **Depends on:** 8.1
  - **Capability:** audit-trail
  - **Files to create/modify:** `frontend/src/lib/components/AuditTrail.svelte`
  - **Acceptance criteria:**
    - [ ] "Exportar CSV" button links to `/api/movimientos/export.csv` with current filters.
    - [ ] Download filename includes filter and date, e.g., `movimientos_U-001_20260619.csv` (spec scenario 4).
  - **Estimated lines:** 50
  - **PR slice:** PR 7

---

## Phase 9: Integration + PWA + Polish

- [ ] **9.1 Configure PWA manifest, service worker, and icon placeholders**
  - **Skill to load:** `sveltekit-structure`, `Frontend Responsive Design Standards`
  - **Context7 query:** none
  - **Depends on:** 0.2
  - **Capability:** infrastructure
  - **Files to create/modify:** `frontend/vite.config.ts` (vite-plugin-pwa), `frontend/src/app.html`, `frontend/static/manifest.json`, `frontend/static/icon-192.png`, `frontend/static/icon-512.png`
  - **Acceptance criteria:**
    - [ ] Manifest contains `name`, `short_name`, `start_url`, `display`, `theme_color`, `background_color`, icons.
    - [ ] Service worker registered; standalone install prompt works on supported devices.
  - **Estimated lines:** 90
  - **PR slice:** PR 8

- [ ] **9.2 Apply safe-area insets, bottom nav active states, and offline placeholders**
  - **Skill to load:** `sveltekit-structure`, `Frontend Responsive Design Standards`
  - **Context7 query:** none
  - **Depends on:** 0.5, 7.1, 8.1
  - **Capability:** infrastructure, visual-map, audit-trail
  - **Files to create/modify:** `frontend/src/routes/+layout.svelte`, `frontend/src/lib/components/BottomNav.svelte`, `frontend/src/routes/mapa/+page.svelte`, `frontend/src/routes/historial/+page.svelte`
  - **Acceptance criteria:**
    - [ ] Global safe-area padding applied.
    - [ ] Active route highlighted in bottom nav.
    - [ ] Network errors show friendly offline message.
  - **Estimated lines:** 80
  - **PR slice:** PR 8

- [ ] **9.3 Run end-to-end scan flow test and responsive QA on target devices**
  - **Skill to load:** `sveltekit-structure`, `Frontend Responsive Design Standards`
  - **Context7 query:** `/mebjas/html5-qrcode` (iOS Safari camera permissions, `OverconstrainedError`, torch/zoom availability)
  - **Depends on:** 5.3, 6.4, 7.5, 8.2
  - **Capability:** barcode-scanning, stock-management, visual-map, audit-trail
  - **Files to create/modify:** `frontend/tests/scanner.e2e.test.ts` (optional), `docs/qa-checklist.md`
  - **Acceptance criteria:**
    - [ ] Scan sector QR → location anchored.
    - [ ] Scan product barcode → product displayed.
    - [ ] Enter stock → save → audit trail shows record.
    - [ ] Visual map reflects stock and no cell is below 48px.
    - [ ] Camera releases on navigation.
  - **Estimated lines:** 100
  - **PR slice:** PR 8

- [ ] **9.4 Write README with deployment, rollback, and stack instructions**
  - **Skill to load:** `cognitive-doc-design` (if available)
  - **Context7 query:** none
  - **Depends on:** all previous
  - **Capability:** infrastructure
  - **Files to create/modify:** `README.md`
  - **Acceptance criteria:**
    - [ ] Covers install, run, build, PWA install, SQLite rollback, and environment variables.
  - **Estimated lines:** 60
  - **PR slice:** PR 8
