# Spec: visual-map

## Capability Summary
A visual warehouse map where each `estante` (shelf) is rendered as an independent CSS Grid with variable `filas` x `columnas`. Cells are color-coded (green = stock OK, yellow = low stock, gray = empty, blue = selected). Tapping a cell shows product info or offers assignment. Touch targets meet mobile accessibility minimums.

## Requirements

### Functional
1. The visual map MUST render every `estante` as a vertically stacked, independent CSS Grid.
2. Each `estante` grid MUST have exactly `filas` rows and `columnas` columns, dynamically generated from the `estantes` table.
3. Each cell represents one `ubicacion` (row, column) within the `estante`.
4. Cell colors MUST be:
   - **Green** (`#22c55e`): the `ubicacion` has a product assigned and `stock_actual > 0`.
   - **Yellow** (`#eab308`): the `ubicacion` has a product assigned and `stock_actual` is at or below a future low-stock threshold (MVP: yellow logic MAY be hard-coded to `stock_actual <= 5` or disabled; color constant MUST be reserved).
   - **Gray** (`#9ca3af`): the `ubicacion` has no product assigned (`producto_id IS NULL`).
   - **Blue** (`#3b82f6`): the cell is currently selected by the user.
5. Touch targets for each cell MUST be a minimum of 48x48 CSS pixels.
6. Tapping an **empty** cell (gray) MUST open a panel with an option to assign the currently-scanned product (if any) or search for a product to assign.
7. Tapping an **occupied** cell (green/yellow) MUST open a panel showing: product `sku`, `descripcion`, `stock_actual`, and an option to relocate the product to another cell.
8. Assignment or relocation MUST be confirmed via an explicit button (e.g., "Confirmar asignacion"). The action SHALL NOT execute on cell tap alone.
9. Adding, removing, or resizing `estante` dimensions MUST NOT mutate historical `movimientos` records. Foreign keys to `ubicaciones` MUST remain valid; out-of-bounds ubicaciones MUST be flagged, not auto-deleted.
10. The map MUST be scrollable vertically to accommodate any number of `estantes`.

### Non-Functional
11. The layout MUST be mobile-first: full width on phone, centered container on tablet/desktop.
12. The page MUST respect safe-area insets (`env(safe-area-inset-*)`) for notched devices.
13. Animations for cell state changes SHOULD be minimal or deferred to post-MVP to preserve performance.

## Scenarios

### Scenario 1: Happy Path — Render Map with Variable Shelves
**Given** the database has:
  - `estante` "A" with `filas=3`, `columnas=4`
  - `estante` "B" with `filas=2`, `columnas=6`  
**When** the admin opens the Visual Map page  
**Then** shelf "A" renders as a 3x4 CSS Grid  
**And** shelf "B" renders as a 2x6 CSS Grid  
**And** both grids are stacked vertically  
**And** each cell is at least 48x48px

### Scenario 2: Happy Path — Tap Empty Cell to Assign
**Given** the user has a product scanned and ready to assign  
**And** cell (fila=2, columna=3) in estante "A" is gray (empty)  
**When** the user taps that cell  
**Then** a detail panel opens showing "Celda vacia"  
**And** a button "Asignar producto escaneado" is visible  
**When** the user taps "Asignar producto escaneado"  
**Then** the backend updates `ubicaciones.producto_id` and `stock_actual`  
**And** the cell turns green  
**And** a success toast is shown

### Scenario 3: Happy Path — Tap Occupied Cell to View
**Given** cell (fila=1, columna=1) in estante "A" has product "SKU-001" with stock `8`  
**When** the user taps that cell  
**Then** the cell turns blue (selected)  
**And** a detail panel opens showing `sku: SKU-001`, `descripcion: "Tornillo M6"`, `stock_actual: 8`  
**And** a "Reubicar" button is visible

### Scenario 4: Edge Case — Accidental Tap Prevention
**Given** the user taps an occupied cell  
**When** the tap occurs  
**Then** the product is NOT moved or modified  
**And** no backend write occurs  
**And** only the selection state changes (blue highlight)

### Scenario 5: Edge Case — Out-of-Bounds Ubicaciones After Resize
**Given** `estante` "A" had `filas=4`, `columnas=4` and ubicaciones existed at (4,4)  
**When** the admin edits `estante` "A" to `filas=3`, `columnas=4`  
**Then** the map renders only rows 1-3  
**And** the ubicacion at (4,4) is NOT deleted  
**And** the backend flags (4,4) as "out of bounds" in the admin view  
**And** all `movimientos` referencing (4,4) remain intact

### Scenario 6: Error Case — No Network on Map Load
**Given** the device loses warehouse WiFi  
**When** the user opens the Visual Map  
**Then** the frontend shows an offline placeholder: "Sin conexion. Los datos pueden estar desactualizados."  
**And** if cached data is available, it is displayed with a stale-data indicator

## Design Notes (from sveltekit-structure and Frontend Responsive Design Standards skills)
- Use a SvelteKit route `/map/+page.svelte` with a reactive `$state` or writable store for the selected cell.
- Each shelf is a `<section>` containing a CSS Grid: `display: grid; grid-template-columns: repeat(var(--cols), minmax(48px, 1fr)); grid-template-rows: repeat(var(--rows), minmax(48px, 1fr));`
- Mobile-first: default styles for 375px width, then enhance for larger screens.
- Safe-area insets: `padding-top: env(safe-area-inset-top); padding-bottom: env(safe-area-inset-bottom);`
- Use `+error.svelte` at the map route level to catch loading failures.
