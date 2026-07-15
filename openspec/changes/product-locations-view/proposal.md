# Proposal: Product Locations View

## Intent

When an operator scans a product barcode without an anchored location, the scanner BLOCKS them with a red flash ("Escaneá un QR de sector primero"). In a real warehouse, an operator picks up a product, scans it, and wants to know "where does this go?" or "how many do we have across all locations?". This change adds a fallback flow: scan product without QR → see all locations → tap one → enter stock. The existing QR-first flow stays unchanged.

## Scope

### In Scope
- **Backend endpoint**: `GET /api/v1/productos/{codigo_de_barra}/ubicaciones` — all ubicaciones where the product is stored, with stock at each; deposito-permission filtered; Suelto included via movimientos
- **Scanner change**: `handleProductScan` without anchored location → call new endpoint → show `ProductLocationsCard` instead of red flash
- **New component**: `ProductLocationsCard.svelte` — product header, total stock badge, tappable location cards, "Cancelar" button
- **Location selection**: tap → anchors location → transitions to existing `ProductCard` + `StockInput` flow
- **Empty state**: "Producto no encontrado en ninguna ubicación" + option to scan QR to assign

### Out of Scope
- Product search by name (barcode only)
- Product relocation between locations
- Low-stock alerts per location
- Product image/photo

## Capabilities

### New Capabilities
- `product-locations`: Lookup all ubicaciones where a product is stored, with per-location stock, total stock, and deposito-permission filtering

### Modified Capabilities
- `barcode-scanning`: Product scan without anchored location no longer blocks with red flash — instead shows `ProductLocationsCard` for location selection

## Approach

- **Backend**: new repo function `get_producto_ubicaciones(db, sku, deposito_ids)` — UNION regular shelves (`ubicaciones.producto_id = sku`) + Suelto (`movimientos` with Suelto estante). Endpoint uses existing `get_deposito_ids_for_user(db, user)` for permission filtering (None = admin, list = non-admin), matching the `list_movimientos` pattern. New Pydantic response schema `ProductoUbicacionesResponse`.
- **Frontend**: modify `handleProductScan` in `scanner/+page.svelte` — when `anchoredLocation` is null, call `getProductoUbicaciones(barcode)` instead of `showError`. New `ProductLocationsCard.svelte` renders the list; tap reuses existing `selectUbicacion` anchoring logic, then calls `getProductoByBarcodeWithStock` to load the product card. No new stores — reuses `anchoredLocation`.
- **No new dependencies**. No schema migrations — purely additive queries.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/app/api/v1/endpoints/productos.py` | Modified | New `GET /{codigo_de_barra}/ubicaciones` endpoint |
| `backend/app/repositories/movimiento_repository.py` | Modified | New `get_producto_ubicaciones` with Suelto support |
| `backend/app/repositories/ubicacion_repository.py` | Modified | New `list_ubicaciones_by_producto` query |
| `backend/app/schemas/productos.py` | Modified | New `ProductoUbicacionesResponse` schema |
| `frontend/src/lib/api/client.ts` | Modified | New `getProductoUbicaciones` + types |
| `frontend/src/routes/scanner/+page.svelte` | Modified | `handleProductScan` fallback to locations view |
| `frontend/src/lib/components/ProductLocationsCard.svelte` | New | Tappable location list component |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Slow query if product in many locations | Low | Warehouse products typically 1-3 locations; indexed on `producto_id` |
| UX complexity (two flows now) | Med | Location cards clearly tappable; "Cancelar" returns to scanning; QR-first flow unchanged |
| Permission filtering correctness | Med | Reuse `get_deposito_ids_for_user` pattern from `list_movimientos`; test with non-admin |
| Suelto stock from movimientos, not ubicaciones | Med | UNION query handles both sources; reuse `_get_stock_anterior` logic |

## Rollback Plan

- **Backend**: remove new endpoint + repo functions + schema (all additive — no existing code modified)
- **Frontend**: revert `handleProductScan` to original block + red flash; delete `ProductLocationsCard.svelte`
- **No database migrations** — no schema changes to revert

## Dependencies

- None — uses existing FastAPI + SvelteKit + SQLite stack

## Success Criteria

- [ ] Scanning a product barcode without anchored location shows all its locations instead of blocking
- [ ] Each location card shows estante, QR, fila/columna, and stock at that location
- [ ] Total stock across all locations is displayed
- [ ] Tapping a location anchors it and shows the stock entry form
- [ ] Endpoint respects deposito permissions (non-admin sees only accessible depositos)
- [ ] Suelto appears as a location when the product has movements there
- [ ] Existing QR-first flow (scan QR → scan product → enter stock) works unchanged
