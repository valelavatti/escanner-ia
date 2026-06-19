# Spec: shelf-admin

## Capability Summary
Admin CRUD for `estantes` (shelves). Creating or editing an `estante` auto-generates the corresponding `ubicaciones` grid. Dimension changes preserve existing ubicaciones when in-bounds and flag out-of-bounds ubicaciones. Deletion supports soft delete to preserve audit history.

## Requirements

### Functional
1. The backend MUST expose endpoints to create, read, update, and delete `estantes`.
2. Creating an `estante` with `nombre`, `filas`, and `columnas` MUST auto-generate `filas * columnas` `ubicaciones` records, each with a unique `(estante_id, fila, columna)` tuple.
3. Each auto-generated `ubicacion` MUST have a deterministic QR value string formatted as `{estante_nombre}-F{fila}-C{columna}` (e.g., "A-F1-C2"), stored in a `qr_valor` column.
4. Updating an `estante`'s dimensions (`filas` or `columnas`) MUST:
   a. Preserve all existing `ubicaciones` that still fall within the new bounds.
   b. Generate new `ubicaciones` for any new grid positions.
   c. Flag (but NOT auto-delete) any `ubicaciones` that fall outside the new bounds. Flagging MAY be done via an `estado` column (e.g., `activo` / `fuera_de_rango`).
5. The admin UI MUST show a warning and require explicit confirmation before any action that would flag ubicaciones as out-of-bounds.
6. Deleting an `estante` MUST perform a soft delete (set `deleted_at` timestamp) so that `movimientos` foreign keys remain valid and audit history is preserved.
7. A hard delete MAY be offered as a separate, explicitly warned admin action, but MUST require confirmation and MUST cascade or block if `movimientos` exist.
8. The `estante` MUST have an `orden_visual` integer to control display order on the Visual Map.

### Non-Functional
9. All CRUD endpoints MUST validate input with Pydantic schemas.
10. Database writes MUST use parameterized queries and SQLite transactions.

## Scenarios

### Scenario 1: Happy Path — Create Shelf
**Given** the admin is on the shelf configuration screen  
**When** the admin enters nombre="A", filas=3, columnas=4, orden_visual=1  
**And** taps "Crear"  
**Then** the backend inserts `estante` "A"  
**And** generates 12 `ubicaciones`: A-F1-C1 through A-F3-C4  
**And** each `ubicacion` has `qr_valor` like "A-F1-C1"  
**And** returns HTTP 201 with the created estante and ubicacion count

### Scenario 2: Happy Path — Edit Shelf Dimensions (Expansion)
**Given** `estante` "A" has `filas=2`, `columnas=2` with 4 ubicaciones  
**When** the admin changes it to `filas=3`, `columnas=4`  
**Then** the existing 4 ubicaciones are preserved  
**And** 8 new ubicaciones are generated for the expanded grid  
**And** no ubicaciones are flagged as out-of-bounds

### Scenario 3: Edge Case — Edit Shelf Dimensions (Shrink with Out-of-Bounds)
**Given** `estante` "A" has `filas=4`, `columnas=4` with 16 ubicaciones  
**And** some ubicaciones already have products or movement history  
**When** the admin changes it to `filas=3`, `columnas=3`  
**Then** the backend identifies 7 ubicaciones as out-of-bounds  
**And** the UI shows a warning: "7 ubicaciones quedaran fuera de rango. Esto no elimina el historial, pero ocultara las celdas del mapa."  
**And** the admin MUST confirm before the update proceeds  
**And** upon confirmation, the 7 out-of-bounds ubicaciones are flagged `estado = "fuera_de_rango"`  
**And** the remaining 9 ubicaciones remain `estado = "activo"`

### Scenario 4: Edge Case — Soft Delete Preserves History
**Given** `estante` "A" has 12 ubicaciones and 50 `movimientos` referencing them  
**When** the admin taps "Eliminar estante"  
**Then** the UI warns: "El historial de movimientos se conservara, pero el estante ya no aparecera en el mapa."  
**And** upon confirmation, the backend sets `estantes.deleted_at = now()`  
**And** all related `ubicaciones` remain in the database  
**And** all `movimientos` remain intact

### Scenario 5: Error Case — Duplicate Shelf Name
**Given** an `estante` named "A" already exists  
**When** the admin tries to create another `estante` named "A"  
**Then** the backend returns HTTP 400  
**And** the error body contains `{ "error": "Ya existe un estante con el nombre 'A'" }`

### Scenario 6: Happy Path — QR Value Generation
**Given** `estante` "B" with `filas=2`, `columnas=2`  
**When** the estante is created  
**Then** the `qr_valor` for ubicacion at fila=2, columna=1 is "B-F2-C1"  
**And** scanning "B-F2-C1" as a QR code anchors the scanner to that exact ubicacion

## Design Notes (from fastapi-templates and SQLite Database Expert skills)
- FastAPI endpoints: `POST /api/v1/estantes`, `GET /api/v1/estantes`, `PATCH /api/v1/estantes/{id}`, `DELETE /api/v1/estantes/{id}` (soft delete).
- Use a repository function `generate_ubicaciones(estante_id, filas, columnas)` that inserts missing positions with `INSERT OR IGNORE` or an explicit existence check.
- For dimension shrink, use a transaction: update `estante` dimensions, then `UPDATE ubicaciones SET estado = 'fuera_de_rango' WHERE fila > ? OR columna > ?`.
- Pydantic schemas: `EstanteCreate`, `EstanteUpdate`, `EstanteOut`.
