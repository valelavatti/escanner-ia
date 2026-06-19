# Proposal: ASG Scanner — Accesaniga Stock Control App

## Summary
Build a mobile-first PWA for warehouse stock control via barcode/QR scanning. Users scan a shelf QR to anchor location, then batch-scan product barcodes to update stock with full audit traceability. Core differentiator: a visual warehouse map with variable-dimension nested CSS grids per shelf.

## Intent
Accesaniga currently lacks a digital stock-control workflow for its warehouse. This app replaces paper/Excel tracking with a fast, one-handed scanning experience that records who changed what, where, and when — enabling accurate inventory visibility and auditability without heavy process overhead.

## Scope

### In Scope (MVP)
- Simple session-based login (audit/tracking only, not security)
- Excel import of product catalog (sku, descripcion, codigo_de_barra)
- Single-scanner QR + barcode capture with auto-format detection (html5-qrcode)
- Product lookup with accumulated stock display
- Stock entry/adjustment with audit logging
- QR-sector anchoring workflow (scan shelf once, batch-scan products)
- Visual warehouse map: nested CSS Grid per shelf, variable rows/columns
- Shelf configuration (admin: add/remove shelves, set dimensions)
- Audit trail / scan history view

### Out of Scope (Post-MVP)
- Excel stock export by SKU (future: complete an Excel's stock column by crossing SKU — not the initial catalog import, which IS in scope)
- Multi-warehouse support
- Real-time cloud sync / multi-device concurrency
- Label printing
- ERP/WMS integration
- Low-stock alerts / threshold rules (display only in MVP)
- Role-based permissions (all users equal in MVP)

## Capabilities

### New Capabilities
- `auth-session`: Simple login for audit tracking
- `excel-import`: Product catalog upload via pandas/openpyxl
- `barcode-scanning`: Unified QR/barcode scanner with auto-format detection
- `stock-management`: Product lookup, accumulated stock, entry with audit logging
- `visual-map`: Warehouse map with per-shelf nested CSS grids (variable dimensions)
- `shelf-admin`: Shelf CRUD and dimension configuration
- `audit-trail`: History view of all stock movements

### Modified Capabilities
- None (greenfield project)

## Approach

| Layer | Tech | Rationale |
|-------|------|-----------|
| Frontend | SvelteKit PWA | Fastest TTI, smallest bundle, mobile-first |
| Scanner | html5-qrcode v2.3.8 | Single instance handles QR+barcode; format callback distinguishes sector vs product; torch/zoom for warehouse lighting |
| Backend | FastAPI (Python) | Async, Pydantic validation, auto OpenAPI docs |
| Database | SQLite (WAL mode) | Zero-config, migrate to PostgreSQL if concurrency grows |
| Excel import | pandas + openpyxl | Standard Python stack for xlsx parsing |
| Visual map | CSS Grid (nested) | Each shelf = independent grid; variable rows/cols; 48px touch targets |

### Architecture Notes
- Scanner auto-detects format: `QR_CODE` → sector lookup/anchor; `EAN_13`/`CODE_128`/`UPC_A` → product lookup. No mode switching UI.
- SQLite in WAL mode with `SQLITE_BUSY` retry logic. Migration path to PostgreSQL documented.
- Auth sessions stored server-side; user identity attached to every `movimientos` record.
- Shelf dimension changes do NOT mutate historical audit records (foreign keys remain valid).

## Data Model Overview

```
productos      : sku, descripcion, codigo_de_barra
estantes       : id, nombre, orden_visual, filas, columnas
ubicaciones    : id, estante_id, fila, columna, producto_id, stock_actual
usuarios       : id, nombre
movimientos    : id, usuario_id, producto_id, ubicacion_id, cantidad,
                 stock_anterior, stock_nuevo, timestamp, tipo (alta/ajuste)
```

## Key UX Flows

1. **Login** → simple name selection → session created
2. **Scan shelf QR** → sector auto-filled/anchored → location pinned
3. **Scan product barcode** → instant DB lookup → shows sku, description, accumulated stock
4. **Enter/adjust stock** → tap save → audit record written (who, when, what, how much, where)
5. **Next product** (same shelf) → location still anchored → repeat step 3-4
6. **Shelf done** → scan next sector QR → location updates
7. **Visual map** → admin sees color-coded shelf grid (green/yellow/gray/blue) → tap to assign product explicitly

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| html5-qrcode in maintenance mode | Med | Pin v2.3.8; evaluate fork/migration if critical bugs arise |
| SQLite concurrency (`SQLITE_BUSY`) | Med | WAL mode + exponential backoff retry; document PostgreSQL migration path |
| Camera permissions on iOS (PWA) | Med | Guide user through Safari settings; test early on target devices |
| Visual map complexity (variable grids) | Med | Prototype grid layout first; ensure 48px touch targets; defer animations |
| One-handed usability | Low | Large tap targets; minimal button count; auto-advance after save |

## Rollback Plan
Greenfield project — rollback = stop deployment, drop database file, and restart from scratch. No legacy data to migrate back. Keep SQLite file in a well-known path for easy deletion. First production data import should be reproducible from the original Excel file.

## Delivery Strategy
`ask-on-risk` — if any risk materializes during implementation (scanner library issues, grid performance problems, SQLite contention), pause and ask before proceeding.

## Dependencies
- Warehouse WiFi coverage for PWA operation
- Excel product catalog prepared with columns: sku, descripcion, codigo_de_barra
- Physical QR codes printed and placed on each shelf/sector

## Success Criteria
- [ ] Scan-to-result latency under 1 second on warehouse WiFi
- [ ] Single-handed stock entry flow completed without keyboard frustration
- [ ] Audit trail shows every stock change with user, timestamp, and location
- [ ] Visual map renders all shelves with correct variable dimensions and color coding
- [ ] Excel import loads product catalog without manual column remapping

## Open Questions
- None — all ambiguities resolved in requirements refinement.
