# Spec: audit-trail

## Capability Summary
Read-only view of all stock movements (`movimientos`) with filtering by user, product, location, and date range. Supports CSV export. Records are immutable — append-only, never edited or deleted.

## Requirements

### Functional
1. The backend MUST expose a `GET /api/v1/movimientos` endpoint that returns all movements ordered by `timestamp DESC`.
2. The endpoint MUST support query parameters for filtering:
   - `usuario_id` — movements by a specific user.
   - `producto_id` — movements for a specific product.
   - `ubicacion_id` — movements at a specific location.
   - `desde` and `hasta` — ISO 8601 date range.
3. The response MUST paginate with `limit` (default 50, max 500) and `offset` parameters.
4. Each movement record in the response MUST include: `id`, `usuario` (nombre), `producto` (sku, descripcion), `ubicacion` (estante nombre, fila, columna), `cantidad`, `stock_anterior`, `stock_nuevo`, `timestamp`, `tipo`.
5. The backend MUST expose a `GET /api/v1/movimientos/export/csv` endpoint that returns a CSV file of the filtered results (same filters as above, no pagination limit).
6. The CSV MUST contain headers: `id,usuario,producto_sku,producto_descripcion,estante,fila,columna,cantidad,stock_anterior,stock_nuevo,fecha_hora,tipo`.
7. No API endpoint SHALL allow updating or deleting a `movimientos` record. The table is append-only.
8. The frontend MUST display the audit trail in a scrollable list or table optimized for mobile, with 48px minimum row height.

### Non-Functional
9. Query latency for the first page MUST be under 300 ms.
10. CSV export SHOULD stream the response to avoid loading large result sets into memory.

## Scenarios

### Scenario 1: Happy Path — View All Movements
**Given** the database has 200 movement records  
**When** the admin opens the Audit Trail page  
**Then** the backend returns the first 50 records ordered by `timestamp DESC`  
**And** the frontend renders each row with user name, product SKU, location, quantities, and timestamp  
**And** a "Cargar mas" button fetches the next 50 records

### Scenario 2: Happy Path — Filter by User
**Given** user "Juan Perez" has 30 movements and user "Maria Lopez" has 20  
**When** the admin selects filter "Usuario = Juan Perez"  
**Then** the backend returns only Juan Perez's 30 movements  
**And** the frontend updates the list accordingly

### Scenario 3: Happy Path — Filter by Date Range
**Given** movements exist from 2024-01-01 to 2024-12-31  
**When** the admin sets `desde=2024-06-01` and `hasta=2024-06-30`  
**Then** the backend returns only movements within June 2024  
**And** the count in the UI matches the filtered result set

### Scenario 4: Happy Path — Export to CSV
**Given** the admin has filtered movements to show only `ubicacion_id = U-001`  
**When** the admin taps "Exportar CSV"  
**Then** the backend generates a CSV with all matching records (no pagination)  
**And** the file is downloaded with filename `movimientos_U-001_YYYYMMDD.csv`  
**And** the CSV contains the correct headers and UTF-8 encoding

### Scenario 5: Error Case — Attempt to Delete Movement (Blocked)
**Given** a malicious or buggy client sends `DELETE /api/v1/movimientos/123`  
**When** the request reaches the backend  
**Then** the backend returns HTTP 405 Method Not Allowed  
**And** no record is modified

### Scenario 6: Error Case — Invalid Date Format
**Given** the admin sends `desde=01-06-2024` (non-ISO format)  
**When** the request reaches the backend  
**Then** the backend returns HTTP 422 Unprocessable Entity  
**And** the error explains the expected ISO 8601 format

### Scenario 7: Edge Case — Empty Result Set
**Given** no movements match the applied filters  
**When** the query executes  
**Then** the backend returns HTTP 200 with an empty `items` array and `total: 0`  
**And** the frontend shows a friendly message "No hay movimientos para los filtros seleccionados"

## Design Notes (from fastapi-templates and SQLite Database Expert skills)
- FastAPI route with Pydantic `MovimientoFilter` query model and `MovimientoOut` response model.
- Use a single parameterized SQL query with JOINs to `usuarios`, `productos`, and `ubicaciones` (and `estantes` for display name).
- Build the WHERE clause dynamically from filter parameters; always whitelist column names to prevent injection.
- CSV export: use Python `csv` module with `io.StringIO`, or stream with `StreamingResponse`.
- SQLite index: `CREATE INDEX idx_movimientos_timestamp ON movimientos(timestamp DESC)` to ensure fast sorting.
