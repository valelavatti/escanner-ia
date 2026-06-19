# Spec: stock-management

## Capability Summary
Product lookup by barcode, display of accumulated stock, and stock entry/adjustment with full audit logging. Every movement creates an immutable record in `movimientos` capturing user, product, location, quantity, previous stock, new stock, timestamp, and movement type.

## Requirements

### Functional
1. When a product barcode is scanned, the backend MUST return the product's `sku`, `descripcion`, and the accumulated `stock_actual` for the anchored `ubicacion`.
2. The user MUST be able to enter a stock quantity. Upon saving, the backend MUST:
   a. Read the current `stock_actual` for the product at the anchored `ubicacion`.
   b. Calculate `stock_nuevo = stock_anterior + cantidad` for an "alta" (addition), or `stock_nuevo = cantidad` for an "ajuste" (adjustment).
   c. Insert a `movimientos` record with `tipo`, `usuario_id`, `producto_id`, `ubicacion_id`, `cantidad`, `stock_anterior`, `stock_nuevo`, and `timestamp`.
   d. Update `ubicaciones.stock_actual` to `stock_nuevo`.
3. The backend MUST reject any stock movement that would result in a negative `stock_nuevo`, returning HTTP 400 with a clear validation error.
4. If two users scan the same product near-simultaneously, the SQLite WAL mode MUST allow concurrent reads. If a write encounters `SQLITE_BUSY`, the backend MUST retry with exponential backoff (up to 3 retries, base delay 50 ms).
5. Both concurrent movements MUST be recorded with correct `stock_anterior` and `stock_nuevo` chaining (i.e., the second write sees the first write's result because SQLite serializes writes).
6. The `movimientos` table is append-only; records MUST NOT be updated or deleted by any API.
7. The backend MUST support an explicit "ajuste" (adjustment) movement type where the user sets the absolute stock value, distinct from "alta" (incremental addition).

### Non-Functional
8. Stock save latency MUST be under 500 ms on warehouse WiFi.
9. All DB operations MUST use parameterized queries; string concatenation into SQL is prohibited.
10. Stock reads and writes MUST occur inside a SQLite transaction for atomicity.

## Scenarios

### Scenario 1: Happy Path — Scan Product and Add Stock
**Given** ubicacion `U-001` is anchored  
**And** product `P-100` has `stock_actual = 10` at `U-001`  
**When** the user scans product `P-100` and enters quantity `5`  
**And** taps "Guardar" with movement type "alta"  
**Then** the backend reads `stock_anterior = 10`  
**And** creates a `movimientos` record with `cantidad = 5`, `stock_anterior = 10`, `stock_nuevo = 15`, `tipo = "alta"`  
**And** updates `ubicaciones.stock_actual` to `15`  
**And** returns HTTP 201 with the movement record

### Scenario 2: Happy Path — Adjust Stock Explicitly
**Given** ubicacion `U-001` is anchored  
**And** product `P-100` has `stock_actual = 15` at `U-001`  
**When** the user selects "Ajustar stock" and enters absolute quantity `12`  
**Then** the backend creates a `movimientos` record with `cantidad = -3`, `stock_anterior = 15`, `stock_nuevo = 12`, `tipo = "ajuste"`  
**And** updates `ubicaciones.stock_actual` to `12`

### Scenario 3: Error Case — Negative Stock Prevention
**Given** ubicacion `U-001` is anchored  
**And** product `P-100` has `stock_actual = 2` at `U-001`  
**When** the user attempts an "ajuste" to quantity `-1`  
**Then** the backend returns HTTP 400  
**And** the error body contains `{ "error": "El stock no puede ser negativo" }`  
**And** no `movimientos` record is created  
**And** `ubicaciones.stock_actual` remains `2`

### Scenario 4: Edge Case — Concurrent Scans (SQLite Serialization)
**Given** user A and user B both scan product `P-100` at ubicacion `U-001` at nearly the same time  
**And** the current `stock_actual` is `10`  
**When** user A saves quantity `5` and user B saves quantity `3` simultaneously  
**Then** SQLite serializes the two writes  
**And** user A's movement has `stock_anterior = 10`, `stock_nuevo = 15`  
**And** user B's movement has `stock_anterior = 15`, `stock_nuevo = 18`  
**And** the final `stock_actual` is `18`

### Scenario 5: Edge Case — SQLITE_BUSY Retry
**Given** a write transaction encounters `SQLITE_BUSY` because another connection holds the write lock  
**When** the backend attempts to save a stock movement  
**Then** the backend retries up to 3 times with exponential backoff (50 ms, 100 ms, 200 ms)  
**And** if all retries fail, returns HTTP 503 with message "Base de datos ocupada, intente de nuevo"  
**And** the client SHOULD display a retry button

### Scenario 6: Edge Case — Product Scanned Without Anchored Location
**Given** the user has NOT anchored a ubicacion (no sector QR scanned)  
**When** the user scans a product barcode  
**Then** the frontend shows a warning "Escanee primero el QR del sector"  
**And** the stock entry form is disabled until a location is anchored

## Design Notes (from fastapi-templates and SQLite Database Expert skills)
- Use FastAPI async route with Pydantic `StockMovementCreate` schema.
- Use a repository pattern: `StockRepository` handles all SQL via parameterized queries.
- Enable `PRAGMA foreign_keys = ON` and `PRAGMA journal_mode = WAL` on every connection.
- Wrap the read-stock → insert-movement → update-stock sequence in a single transaction.
- Retry logic: catch `sqlite3.OperationalError` with `SQLITE_BUSY`; sleep and retry.
- Never expose raw SQL errors in HTTP responses.
