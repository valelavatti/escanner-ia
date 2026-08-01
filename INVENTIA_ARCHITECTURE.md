# InvenTIA Picking Architecture and Analysis

> **Document status:** proposed architecture and implementation analysis. This is a design document, not an implementation. Repository facts are identified as current; all new tables, endpoints, and algorithms are proposed.

## 1. Executive Decision

**One-sentence architecture:** Keep FastAPI and SQLite as the authoritative transaction boundary for remitos, stock, deterministic route planning, scan validation, and picking state; use the existing SvelteKit scanner as the operator interface; and use n8n, a strictly constrained LLM, and an optional edge-tts service only for post-transaction language and audio delivery.

The MVP will model each physical shelf as an integer point on a fictional warehouse plane and will calculate walking cost with Manhattan distance. A remito is planned globally, including the choice of physical location for every requested quantity, and is recalculated from the employee's actual starting anchor and after every accepted pick.

### Non-negotiable decisions

| Area | Decision |
| --- | --- |
| Source of truth | FastAPI owns data validation, stock, route calculation, picking state, authorization, transactions, and idempotency. |
| Physical model | `estantes` receive integer route coordinates. `ubicaciones.fila` and `ubicaciones.columna` remain local shelf-cell coordinates. |
| MVP cost | Minimize total walking distance first. Break equal-distance ties with fewer aisle changes, then a deterministic stable key. |
| Multiple locations | Select the combination of locations that minimizes the complete remito route, not the nearest location to the employee at one decision point. |
| Initial anchor | A QR always identifies its persisted location. A product barcode identifies the start only when the SKU has exactly one eligible physical location for the remito. Otherwise request a location QR or explicit selection. |
| Scan authority | FastAPI classifies scans and commits accepted state changes. The browser's debounce is only a user-experience optimization. |
| AI boundary | n8n may orchestrate small authenticated HTTPS events. The LLM may produce structured language only. Neither n8n nor the LLM may write SQLite, confirm a pick, or invent coordinates. |
| Audio | A separate edge-tts service may cache generated audio and return an audio URL. A timeout, invalid response, or playback error falls back to browser speech or deterministic text. |
| QR values | Existing persisted `ubicaciones.qr_valor` values are authoritative. Route calculations must never regenerate QR labels. |

"Perfect route" has a precise but limited meaning here: it is optimal under the selected cost function and the data snapshot used by the planner. It is not universally perfect for a real warehouse because the MVP does not know every obstacle, congestion condition, elevation, or human preference.

## 2. What Is Already Present in the Repository

### 2.1 Verified stack and runtime shape

The repository already contains an internal stock application with this relevant stack:

| Layer | Current implementation | Evidence |
| --- | --- | --- |
| Backend API | FastAPI on Python | `backend/app/main.py`, `backend/requirements.txt` |
| Persistence | SQLite accessed asynchronously with `aiosqlite` | `backend/app/core/database.py` |
| SQLite behavior | Foreign keys enabled, WAL mode, normal synchronous mode, busy timeout | `backend/app/core/database.py` |
| Migrations | Versioned SQL scripts run at application startup | `backend/app/core/migrations.py`, `backend/migrations/` |
| Frontend | SvelteKit + Vite + PWA-oriented frontend | `README.md`, `frontend/` |
| Authentication | Server-side sessions and bearer token requests; users can have per-deposito roles | `backend/migrations/001_create_tables.sql`, `010_create_usuario_deposito.sql`, `frontend/src/lib/api/client.ts` |

The current database connection is configured with `PRAGMA foreign_keys = ON`, `PRAGMA journal_mode = WAL`, `PRAGMA synchronous = NORMAL`, `PRAGMA busy_timeout = 5000`, and `PRAGMA temp_store = MEMORY`. New picking writes should use the same connection/dependency pattern and should remain inside explicit transactions.

### 2.2 Existing inventory model

The current schema already provides most of the physical inventory hierarchy:

| Existing table | Current role | Important fields for InvenTIA |
| --- | --- | --- |
| `productos` | Product master and exact scan lookup | `sku` primary key, `descripcion`, unique `codigo_de_barra` |
| `estantes` | Shelf definition | `id`, `nombre`, `orden_visual`, `filas`, `columnas`, `deleted_at`, `deposito_id` |
| `ubicaciones` | One cell inside a shelf | `estante_id`, 1-based `fila`, 1-based `columna`, `producto_id`, `stock_actual`, unique `qr_valor`, `estado` |
| `depositos` | Warehouse boundary | `id`, `nombre` |
| `usuario_deposito` | User access and role per warehouse | `usuario_id`, `deposito_id`, `role` |
| `movimientos` | Append-only stock and assignment audit | Product, location, quantity, before/after stock, type, timestamp, user/session references |
| `sessions` and `usuarios` | Authentication and audit attribution | Existing user session and identity data |

`estantes.filas` and `estantes.columnas` describe the generated grid dimensions. `ubicaciones.fila` and `ubicaciones.columna` identify a particular local cell. None of these fields currently describe the distance between two shelves; that is the missing circulation model.

The current `estante_repository.py` creates and resizes shelf cells transactionally. Resizing can mark cells `fuera_de_rango` without deleting historical data. The route engine must therefore filter out soft-deleted shelves and non-active locations rather than assuming every generated cell is a valid route stop.

The current `movimiento_repository.py` calculates regular shelf stock from `ubicaciones.stock_actual`. It calculates `Suelto` stock by summing movement quantities. The product-location endpoint combines both sources and applies warehouse permissions. A route planner must use per-location physical stock, not only the product's global total.

### 2.3 Existing scanner behavior

The current scanner is already a suitable integration point:

- `frontend/src/lib/components/Scanner.svelte` uses `html5-qrcode` and supports QR, EAN-13, Code 128, and UPC-A formats.
- `frontend/src/routes/scanner/+page.svelte` receives both decoded text and the detected format name.
- A `QR_CODE` scan calls `lookupSector(qrValor)`, which resolves the exact persisted QR value to an active location.
- Non-QR scans are treated as product barcodes and use exact product lookup.
- If a product barcode is scanned without an anchored location, the page loads product locations and permits selecting a location or scanning a QR while the location-selection card is visible.
- If a location is anchored, a later product barcode loads product stock for that exact `ubicacion_id`.
- The page has a two-second duplicate debounce. This must remain only a UI optimization; server-side event idempotency is required for correctness.

The future picking UI should extend this flow rather than replace the scanner. The existing QR/product distinction maps directly to the proposed anchor and scan state machine.

### 2.4 QR authority and the `Suelto` exception

`ubicaciones.qr_valor` is unique and is used by the backend for exact location lookup. `ubicacion_repository.generate_qr_valor()` creates values when cells are generated, but the persisted value in the row is the authority after creation. Route calculation must read and return that value. It must not reconstruct a label from the shelf name, dimensions, row, or column.

The `Suelto` shelf was seeded as a one-cell catch-all for stock without a physical location. Existing code intentionally treats it differently: it is not a one-product-per-cell shelf, and its stock comes from movements rather than `ubicaciones.producto_id`. `Suelto` is not a physical route stop. If a remito quantity exists only there, the item must be reported as an unlocated/manual exception, not silently inserted into a walking route.

There is currently no remito, picking session, route snapshot, scan event, or picking allocation domain in the repository. The following sections define that missing domain without changing the current source code in this document.

## 3. Domain Model and Proposed Tables

The minimal design reuses the current product, warehouse, shelf, location, user, and stock-audit tables. It adds the remito and picking tables below and adds two nullable route-coordinate fields to `estantes`.

### 3.1 Existing tables to reuse

1. Reuse `productos` for SKU identity and exact barcode resolution. Do not duplicate product master data in a remito.
2. Reuse `depositos` as the remito and route boundary. An MVP remito belongs to one deposito; cross-deposito picking is out of scope.
3. Reuse `estantes` and `ubicaciones` for physical shelf and cell identity.
4. Reuse `ubicaciones.qr_valor` as the scan value. Do not create a second route QR identifier.
5. Reuse `usuarios`, `sessions`, and `usuario_deposito` for authentication and permission checks.
6. Reuse `movimientos` as the stock/audit ledger, but add a dedicated picking stock movement semantic rather than overloading an unrelated movement type.

### 3.2 Shelf route coordinates

Proposed additive fields on `estantes`:

| Field | Type | Meaning |
| --- | --- | --- |
| `ruta_x` | nullable integer | Position on the warehouse plane along the configured horizontal axis. |
| `ruta_y` | nullable integer | Position on the warehouse plane along the configured aisle/depth axis. |

Both values should be null or both non-null. A null pair means that the shelf has not yet been mapped and is not eligible for automatic routing. Coordinates should be configured per deposito and should represent the shelf access/circulation point, not the geometric center of the shelf.

For the MVP, one route point should identify one shelf access point. A partial unique index on `(deposito_id, ruta_x, ruta_y)` can prevent accidental duplicate shelf points when both coordinates are present. If the warehouse intentionally has multiple shelves at one access point, the route engine can still group their cells into one stop; that exception should be an explicit later decision rather than an accidental duplicate.

The current `orden_visual` remains a display ordering field. It is not a physical distance and must not be used as a route substitute.

### 3.3 Proposed `remitos`

One remito is the picking work order for one deposito.

| Field | Type / constraint | Purpose |
| --- | --- | --- |
| `id` | integer primary key | Internal identity. |
| `deposito_id` | required foreign key | Warehouse in which the remito is picked. |
| `referencia` | text | Human or external remito number. |
| `estado` | enum-like text | `draft`, `ready`, `in_progress`, `completed`, `cancelled`, or `exception`. |
| `created_by` | user foreign key | Audit attribution. |
| `created_at`, `updated_at` | timestamp | Lifecycle timestamps. |

The remito should be created in `draft` or `ready` and should be considered ready only after its lines are valid. A remito does not store a final route permanently because the route depends on the current stock snapshot and the employee's start anchor.

### 3.4 Proposed `remito_items`

One logical line represents a requested quantity for one SKU. If an external source has repeated lines for the same SKU, preserve the external line number but normalize or explicitly define whether the lines can be merged.

| Field | Type / constraint | Purpose |
| --- | --- | --- |
| `id` | integer primary key | Line identity. |
| `remito_id` | required foreign key | Parent remito. |
| `line_number` | integer | Stable source/display order. |
| `sku` | required foreign key to `productos.sku` | Requested product. |
| `requested_quantity` | positive integer | Quantity required by the remito. |
| `picked_quantity` | non-negative integer | Quantity accepted so far. |
| `estado` | enum-like text | `pending`, `partial`, `picked`, `unlocated`, `insufficient_stock`, or `exception`. |
| `created_at`, `updated_at` | timestamp | Audit and UI freshness. |

A line may be fulfilled from more than one physical location. The allocation is not stored as one permanent location on the item; it is represented by route steps for the current session and by accepted picking events.

### 3.5 Proposed `picking_sessions`

A session is one employee's attempt to pick a remito.

| Field | Type / constraint | Purpose |
| --- | --- | --- |
| `id` | integer primary key | Session identity. |
| `remito_id` | required foreign key | Work order. |
| `usuario_id` | required foreign key | Operator. |
| `estado` | enum-like text | `awaiting_anchor`, `active`, `paused`, `completed`, `cancelled`, or `blocked`. |
| `anchor_type` | nullable enum | `qr`, `barcode_unique`, `manual`, or null before anchoring. |
| `anchor_ubicacion_id` | nullable foreign key | Physical location used as the start. |
| `current_ubicacion_id` | nullable foreign key | Last confirmed physical location for route recalculation. |
| `route_version` | integer | Current route snapshot version. |
| `started_at`, `completed_at`, `last_activity_at` | timestamps | Lifecycle and operational visibility. |

The session is the authoritative state machine boundary. The browser should not infer completion by hiding cards; it should read the session response.

### 3.6 Proposed `picking_route_steps`

Route steps are versioned snapshots of the planner's current allocation and order.

| Field | Type / constraint | Purpose |
| --- | --- | --- |
| `id` | integer primary key | Step identity. |
| `session_id` | required foreign key | Picking session. |
| `route_version` | integer | Identifies one complete route snapshot. |
| `sequence` | integer | Position in that snapshot. |
| `remito_item_id` | required foreign key | Logical item being fulfilled. |
| `sku` | snapshot or foreign key | Product identity for fast response rendering. |
| `ubicacion_id` | required foreign key | Selected physical cell. |
| `allocated_quantity` | positive integer | Quantity to take from this cell for this step. |
| `picked_quantity` | non-negative integer | Quantity accepted at this step. |
| `estado` | enum-like text | `pending`, `current`, `completed`, `superseded`, or `exception`. |
| `qr_valor_snapshot` | text | QR value shown for this route version. |
| `estante_nombre_snapshot` | text | Display snapshot. |
| `ruta_x_snapshot`, `ruta_y_snapshot` | integers | Coordinates used by the calculation. |
| `leg_distance`, `cumulative_distance` | integer | Explain the route to the UI without recalculating it client-side. |

The snapshots are useful for auditability. If a shelf is renamed, resized, remapped, or its current QR value changes for a legitimate administrative reason, an old route remains explainable. New route versions must use the current persisted QR value.

### 3.7 Proposed `picking_events`

This is the append-only event/audit record for every anchor and scan attempt, including rejected attempts.

| Field | Type / constraint | Purpose |
| --- | --- | --- |
| `id` | integer primary key | Server event identity. |
| `session_id` | required foreign key | Picking session. |
| `client_event_id` | required text, unique per session | Idempotency key generated by the client. |
| `event_type` | enum-like text | `anchor`, `scan`, `manual_selection`, or `route_recalculated`. |
| `raw_code` | text | Decoded QR/barcode value. |
| `format` | text | Scanner format, for example `QR_CODE` or `EAN_13`. |
| `resolved_sku` | nullable text | Product resolved from a barcode. |
| `resolved_ubicacion_id` | nullable integer | Location resolved from a QR or selection. |
| `outcome` | enum-like text | `correct`, `valid_out_of_order`, `not_in_remito`, `duplicate_already_picked`, `wrong_location`, or another explicit exception. |
| `quantity_requested`, `quantity_accepted` | non-negative integers | Quantity decision for the event. |
| `route_version_before`, `route_version_after` | integers | Route evolution around the event. |
| `payload_json` | text | Small diagnostic context, never a substitute for typed columns. |
| `created_at` | timestamp | Event time. |

The unique `(session_id, client_event_id)` constraint is mandatory. A repeated request with the same client event ID must return the original result rather than apply stock or state changes again.

### 3.8 Stock, constraints, and optional reservations

`picking_events` is not the stock source. Accepted picking must update the stock ledger and the picking state in one FastAPI transaction. The current generic `movimientos` API supports `alta` and `ajuste` stock semantics plus assignment types. A future picking implementation should introduce a clear `salida` or `picking` movement type, or a dedicated stock-out service, rather than pretending that an outbound pick is an inbound `alta` or an unrelated absolute adjustment.

For a single-operator demo, the planner can read current stock and the scan transaction can verify and decrement the actual location stock. A full reservation table is not required to demonstrate the route. For multiple simultaneous pickers, add a `picking_reservations` table or equivalent reservation fields and calculate `available_stock = physical_stock - active_reservations`. Reservation expiry, cancellation, and release must be designed before claiming multi-worker correctness.

Regardless of reservation strategy:

- Planning must never change stock merely because a route was displayed.
- Invalid, duplicate, and wrong-location scans must not change stock.
- An accepted quantity must be guarded against current stock inside a transaction.
- A successful stock change, item progress update, picking event, and route-version update should commit atomically.
- `Suelto` stock is visible as an exception source but is excluded from automatic physical route steps.

## 4. Coordinate Model

### 4.1 Separate global route coordinates from local shelf coordinates

The model deliberately has two coordinate systems:

| Coordinate | Owner | Meaning | Used for walking cost? |
| --- | --- | --- | --- |
| `(ruta_x, ruta_y)` | `estantes` | Fictional access point of a shelf on the warehouse plane | Yes, in the MVP |
| `(fila, columna)` | `ubicaciones` | Cell inside that shelf's generated grid | No, not for inter-shelf walking in the MVP |

The distinction prevents a common modeling error: `F2-C3` identifies where a product is on a shelf, but it does not tell the planner how far that shelf is from another shelf.

### 4.2 Orientation convention

The route plane is a local warehouse convention, not a geographic coordinate system:

- The logical warehouse origin is `(0, 0)`. For the demo, it may represent the entrance or staging point; the chosen origin must be explicit in depot configuration.
- `ruta_x` increases from left to right when looking at the warehouse plan.
- `ruta_y` increases from the entrance toward the back of the warehouse.
- By default, `ruta_y` is also the aisle index used by the MVP's aisle-change tie-break. If a depot uses the other axis for aisles, that axis must be an explicit depot setting rather than an undocumented assumption.
- A shelf coordinate is the point where the employee enters or accesses the shelf's aisle. It is not the center of its physical footprint.
- Proposed local display convention: when facing a shelf from the aisle, `columna=1` is the leftmost cell and columns increase to the right; `fila=1` is the lowest cell and rows increase upward. This local orientation is for clear labeling only and does not affect the MVP walking distance.

The current database stores row and column numbers but does not currently document their physical orientation. The convention above must be confirmed when route coordinates are seeded.

### 4.3 Manhattan distance

For two shelf access points `A=(x1,y1)` and `B=(x2,y2)`, the MVP distance is:

```text
distance(A, B) = abs(x2 - x1) + abs(y2 - y1)
```

Example:

```text
A = (1, 1)
B = (3, 3)
distance(A, B) = abs(3 - 1) + abs(3 - 1) = 2 + 2 = 4
```

The result means four fictional grid steps: two horizontal and two vertical. If a later depot configuration says that one route unit represents 1.5 meters, the same route is estimated as 6 meters. The MVP should keep the base calculation unitless and expose scale as optional metadata; it must not claim that a unit is a real meter until the warehouse mapping supplies that fact.

Distance between two cells on the same shelf is zero in this model because both cells share the shelf access point. This intentionally ignores walking along the shelf face and handling time.

### 4.4 How shelf relationships are derived

No explicit neighbor table is required for the MVP. Two configured shelves are related by their integer coordinates:

1. Load active shelves in the same deposito with non-null coordinate pairs.
2. Treat each shelf coordinate as a virtual grid node.
3. Calculate a direct Manhattan cost between successive route stops.
4. Do not use `orden_visual` as a distance, and do not infer physical adjacency from shelf names.

This is a deterministic approximation. It assumes that a person can walk around the virtual grid and that every horizontal or vertical step has comparable cost. It does not model blocked cells, one-way aisles, stairs, doors, congestion, or forbidden crossings.

### 4.5 Evolution to an explicit graph

If the warehouse layout becomes irregular, preserve the API concept of a route stop but replace the internal distance provider:

```text
Current:
  shelf(ruta_x, ruta_y) -> Manhattan distance

Future:
  access node -> edge(weight, time, aisle_change) -> access node
```

A future graph can add `route_nodes` and `route_edges` per deposito, with shortest-path distances between shelf access nodes. Existing `ruta_x` and `ruta_y` can remain as a fallback visualization and seed for a first graph. The route algorithm should depend on a `distance(a, b)` and `aisle_changes(a, b)` abstraction so graph migration does not change remito or scan contracts.

## 5. Route Algorithm

### 5.1 Inputs and eligibility

The planner receives:

- One remito and its deposito.
- Each item SKU and remaining requested quantity.
- Current physical stock by `ubicacion_id`.
- Shelf route coordinates and aisle-axis configuration.
- Existing active route anchor, if any.
- Current user permissions for the deposito.
- A route policy/version that identifies the cost model.

An eligible automatic candidate must satisfy all of the following:

1. The location belongs to the remito's deposito.
2. Its shelf is not soft-deleted.
3. The location is `activo` and inside the current shelf dimensions.
4. The location has positive physical stock for the requested SKU.
5. The shelf has a complete `ruta_x`/`ruta_y` pair.
6. The source is a regular physical location, not `Suelto`.
7. The current user is authorized to access the deposito.

The candidate record should include `sku`, `ubicacion_id`, `estante_id`, persisted `qr_valor`, `fila`, `columna`, `stock_available`, `ruta_x`, `ruta_y`, and a stable identity key. The global product stock total is useful for display but is insufficient for route eligibility.

If the physical candidate sum is below the requested quantity, the item is `insufficient_stock` or `unlocated` depending on whether the missing quantity exists in `Suelto`. The route must expose that exception rather than fabricate a stop.

### 5.2 Automatic resolution before the employee starts

Creating or starting a picking session should automatically:

1. Validate the remito and its lines.
2. Resolve each SKU to all eligible physical candidate locations.
3. Determine whether each requested quantity can be fulfilled, including possible splits across cells.
4. Produce a provisional route plan.
5. Mark unresolved lines with an explicit reason.

The provisional plan is not yet final because the employee's real starting point is unknown. It can use the configured logical warehouse origin, defaulting to `(0, 0)` for the fictional demo if the product decides to do so. It must be labelled `provisional` and must be recalculated after anchoring. If no origin is configured, return an unanchored deterministic order and explicitly report that walking distance is not yet meaningful.

### 5.3 Variable start and anchor rules

The final route begins at the employee's actual anchor:

- **Location QR:** Resolve the exact `qr_valor` through the existing location lookup. It must point to an active physical location in the remito deposito. The QR establishes the employee's current location; it does not by itself pick stock.
- **Product barcode with exactly one eligible location:** Resolve the product by its exact unique barcode, filter locations for the current remito, and use the one eligible physical location as the start shelf. This is `barcode_unique` anchoring. The barcode anchor does not automatically tick the remito line; the subsequent picking action must be explicit.
- **Product barcode with zero or multiple eligible locations:** Do not guess the start. Return `anchor_required` with a request for a location QR or an explicit candidate selection. A product barcode is a product identity, not necessarily a physical location identity.
- **Product barcode not present in the remito:** Do not use it as a remito anchor. Report that it is not part of the active remito and keep the session waiting for a valid anchor.
- **Manual selection:** Permit an authenticated user to choose a candidate location when camera scanning is unavailable. Store the choice as an event and apply the same validation as a QR.

After the anchor is committed, recompute the entire remaining route from that shelf. The route must not simply prepend the anchor to an old route because candidate allocation may change when the starting point changes.

### 5.4 Objective and plain-language meanings

The route comparison key is lexicographic:

```text
(total_walking_distance,
 total_aisle_changes,
 stable_route_key)
```

The first two values are numeric. The last value is a deterministic comparison of stable identifiers such as line number, SKU, shelf ID, and location ID.

| Term | Plain-language meaning in this MVP |
| --- | --- |
| Walking distance | How many fictional grid steps the employee walks between shelf access points. It is the primary objective. |
| Time | Estimated duration. It would combine walking distance, walking speed, and handling/service time at stops. It is not the primary MVP objective because the repository has no measured speeds or handling durations. |
| Aisle changes | How many route legs move from one configured aisle band to another. It is a secondary tie-break, not a weighted penalty that can override a shorter distance. |
| Stable ordering | A deterministic final tie-break so the same data produces the same route across runs and machines. |

With the default `ruta_y` aisle axis, a simple aisle-change proxy is:

```text
aisle_change(A, B) = 0 if A.ruta_y == B.ruta_y else 1
```

This counts transitions between aisle bands, not the exact number of physical aisle boundaries crossed. A future graph can replace it with explicit edge metadata.

The default route does not return to the warehouse origin after the last pick because no delivery/exit endpoint exists in the current domain. A future `return_to_origin` policy may add that final leg.

### 5.5 Candidate selection is global, not greedy-by-current-distance

When a SKU exists in several locations, the planner must choose the location or combination of locations that minimizes the route for the whole remito. It must not choose the location nearest to the employee's current point in isolation and then repeat that decision for the next SKU.

Example using shelf access coordinates:

| Candidate | Coordinate | Role |
| --- | --- | --- |
| Product A, location A-near | `(1, 1)` | Nearest to the origin `(0, 0)` |
| Product A, location A-shared | `(4, 0)` | Farther from the origin |
| Product B, only location B | `(4, 0)` | Same shelf access point as A-shared, a different cell |

A current-location greedy rule chooses A-near and then B:

```text
(0,0) -> (1,1) -> (4,0) = 2 + 4 = 6
```

The global planner can choose A-shared and B together:

```text
(0,0) -> (4,0) -> (4,0) = 4 + 0 = 4
```

The second choice is globally better even though A-shared is not nearest to the starting employee. The same principle applies when a requested quantity must be split across several locations. All feasible allocations must be evaluated together for small remitos, or evaluated with a full-route marginal cost by the fallback heuristic.

### 5.6 Exact search for small demo remitos

The problem combines location allocation and stop ordering. It is closer to a generalized pickup routing problem than to a simple nearest-neighbor list.

For small remitos, the planner should:

1. Build candidate lists and remaining quantities for every line.
2. Enumerate feasible allocation variants for a line, including a split across locations when necessary.
3. Combine allocation variants into route stops.
4. Use dynamic programming over the served-demand state and the last shelf, comparing the lexicographic route key.
5. Reconstruct the chosen allocation and ordered `picking_route_steps`.

The state can be represented as a bitmask for small logical items, with an additional quantity/variant index when a line is split. The implementation threshold should be configurable and benchmarked; an initial demo threshold of roughly 8 to 10 route stops is reasonable only as a starting point, not a guaranteed performance limit.

When the exact planner returns `algorithm=exact_dp`, `optimality` should state `optimal_for_cost_function_and_snapshot`. This is the correct meaning of a perfect route in the MVP.

### 5.7 Deterministic heuristic fallback for larger remitos

For larger remitos, use a bounded deterministic heuristic rather than blocking the operator:

1. Start with the current anchor or provisional origin.
2. Consider every still-unfulfilled item and every feasible candidate/allocation option.
3. Evaluate the full-route insertion cost, not only distance from the current employee position.
4. Insert the option that produces the best lexicographic route key.
5. Repeat until all fulfillable demand is allocated.
6. Optionally run a bounded local improvement pass such as deterministic 2-opt over stops.
7. Use stable identifiers to resolve every equal-cost choice.

Return `algorithm=heuristic` and `optimality=best_effort`. The fallback may be longer than the mathematical optimum, but it must remain valid, explainable, bounded, and repeatable.

### 5.8 Route version and snapshot rules

Every route response belongs to a monotonically increasing `route_version` on the picking session. Recalculate and create a new version after:

- The initial QR, barcode, or manual anchor.
- An accepted correct or valid-out-of-order pick.
- A stock conflict that changes candidate eligibility.
- An administrative change to route coordinates or a location's active state.

Old route steps are not rewritten into the new order. They are retained as `superseded` or are queryable by their old version. The current route is the highest active version. Picking events record both versions around a state transition.

## 6. Picking State Machine and Scan Outcomes

### 6.1 Lifecycle states

```text
Remito:
  draft -> ready -> in_progress -> completed
                    |             |
                    +-> exception  +-> cancelled

Picking session:
  awaiting_anchor -> active -> completed
          |             |
          +-> blocked   +-> paused -> active
```

Suggested transitions:

- A remito enters `in_progress` when its first session starts.
- A session is `awaiting_anchor` after candidate resolution and provisional planning.
- A valid QR, unique-location barcode, or manual selection changes it to `active`.
- An accepted pick can leave a session active even if it was out of order; the route is recalculated.
- A session becomes `completed` only when every remito item is fully picked or an explicit exception policy closes the work.
- A missing physical location, insufficient stock, or invalid route configuration is visible as `blocked`/`exception`, not silently treated as completed.

### 6.2 Required scan outcomes

The API should return a machine-readable outcome and a deterministic display message key. The UI can render colors and text from the response.

| Outcome | Meaning | State mutation |
| --- | --- | --- |
| `correct` | The product and physical location match an eligible pending route step, and the requested quantity can be accepted. | Tick/update the item or step, apply the stock change, append the event, recalculate the remaining route. |
| `valid_out_of_order` | The product is in the remito and the scanned location is an eligible physical location, but it is not the current recommended next step. | Accept it exactly like a valid pick, mark that work complete, append the outcome, and recalculate the remaining route from the scanned/current location. |
| `not_in_remito` | The barcode resolves to a known SKU, but the SKU has no open line in this remito. | No item, stock, or route mutation. Append the rejected event. |
| `duplicate_already_picked` | The same client event was retried, or the item/allocated quantity is already complete. | For the same event ID, return the original response. For a new scan, append the duplicate outcome but do not change stock or progress. |
| `wrong_location` | The SKU is relevant, but the current location QR or selected physical cell is not an eligible/allocated location for the pending work. | No pick or stock mutation. Return expected/current route information that does not require the client to invent it. |

Additional explicit outcomes are needed for `anchor_required`, `invalid_code`, `unlocated_exception`, `insufficient_stock`, `inactive_location`, `permission_denied`, and `session_not_active`. They should not be collapsed into `wrong_location` because operators need different recovery actions.

### 6.3 Live scan behavior

The intended operator flow is:

1. The user scans a QR or unique product barcode to establish the start.
2. The backend returns the final route and the next stop.
3. The user scans a location QR and/or product barcode at a stop.
4. FastAPI resolves the code, validates it against the session and the current stock snapshot, and returns an outcome immediately.
5. The frontend ticks the line live from the response, shows the outcome, and displays the recalculated remaining route.
6. n8n may separately turn the committed result into a spoken instruction, but its success is not required for the tick or route update.

If a user visits a valid later location first, `valid_out_of_order` is a success, not an error. The purpose of the route is to guide the operator, not to reject a physically valid and authorized pick merely because reality differed from the recommendation.

### 6.4 Idempotency and transaction sequence

The server must treat the scan request as a transaction, approximately in this order:

1. Authenticate the user and verify access to the session's deposito.
2. Validate session status and request schema.
3. Look up `(session_id, client_event_id)`. If it already exists, return the stored result without repeating side effects.
4. Resolve the raw code using exact barcode or exact persisted QR lookup.
5. Load the current route version, remito progress, location assignment, and current stock inside the transaction.
6. Classify the outcome.
7. For an accepted pick, atomically verify/decrement stock, update `remito_items`, update the route step, and set the current location.
8. Insert the `picking_events` record with the outcome.
9. Recalculate and persist a new route version from the new current location.
10. Commit and return the complete authoritative response.

The exact route calculation should be kept fast enough to run before commit for demo-size sessions. If a larger heuristic ever needs to run asynchronously, the event and item/stock transaction must commit first and the UI must receive an explicit `route_pending` state; it must never assume a route was updated merely because a scan request returned HTTP success.

The client event ID must be generated per user intention. A deliberate second scan should use a new ID and receive `duplicate_already_picked`; a network retry of the same intention must reuse the old ID and receive the original result. The existing two-second frontend debounce cannot provide this guarantee by itself.

### 6.5 Stock and reservation behavior

The route is a plan, not a stock reservation. For the initial single-worker demo:

- The planner reads stock without changing it.
- A successful pick verifies the current stock in the same transaction that advances picking state.
- If stock changed and the selected location is empty, the event is rejected as `insufficient_stock` and the backend recalculates from remaining eligible candidates.
- Stock must never become negative.

For production concurrency, add reservations before advertising that two users can safely work the same remito or the same stock. Reservation allocation must also exclude `Suelto` from automatic physical steps. A reservation does not turn unlocated stock into a physical location.

## 7. API Boundary and Compact JSON Contracts

These endpoint names and payloads are proposed contracts. They should follow the repository's existing authenticated `/api/v1` convention and existing Spanish identifiers where practical.

### 7.1 Proposed endpoint surface

| Endpoint | Responsibility |
| --- | --- |
| `POST /api/v1/remitos` | Create/import and validate a remito. |
| `GET /api/v1/remitos/{remito_id}` | Return lines, progress, candidate/exception summary, and session references. |
| `POST /api/v1/remitos/{remito_id}/picking-sessions` | Start a session, resolve candidates, and prepare a provisional route. |
| `POST /api/v1/picking-sessions/{session_id}/anchor` | Commit a QR, unique barcode, or manual start anchor. |
| `GET /api/v1/picking-sessions/{session_id}/route` | Return the current route snapshot and remaining work. |
| `POST /api/v1/picking-sessions/{session_id}/scan` | Resolve, classify, and transactionally commit a scan attempt. |
| `POST /api/v1/picking-events/{event_id}/n8n` | Optional authenticated delivery/retry boundary if the backend exposes an explicit outbound relay. |

All picking endpoints must enforce the authenticated user's deposito access and must not accept a client-supplied SKU, location, stock, or coordinate as authoritative when it can be resolved server-side.

### 7.2 Start contract

Request:

```json
POST /api/v1/remitos/501/picking-sessions
{}
```

Response before an anchor is known:

```json
{
  "session_id": 9001,
  "remito_id": 501,
  "status": "awaiting_anchor",
  "route_version": 1,
  "anchor_policy": {
    "qr_allowed": true,
    "barcode_allowed_when_unique": true,
    "manual_selection_allowed": true
  },
  "pre_anchor_route": {
    "status": "provisional",
    "algorithm": "exact_dp",
    "steps": [],
    "exceptions": []
  }
}
```

The real response should include the provisional steps and candidate/exception information. The compact example omits those fields only to keep the contract readable.

Anchor request:

```json
POST /api/v1/picking-sessions/9001/anchor
{
  "client_event_id": "evt-anchor-001",
  "code": "Pasillo1-F2-C3",
  "format": "QR_CODE"
}
```

Successful anchor response:

```json
{
  "session_id": 9001,
  "status": "active",
  "anchor": {
    "type": "qr",
    "ubicacion_id": 77,
    "estante_id": 12,
    "ruta_x": 3,
    "ruta_y": 2,
    "qr_valor": "Pasillo1-F2-C3"
  },
  "route_version": 2,
  "route": { "status": "final", "algorithm": "exact_dp", "steps": [] }
}
```

Ambiguous barcode anchor response:

```json
{
  "session_id": 9001,
  "status": "anchor_required",
  "reason": "ambiguous_product_location",
  "sku": "SKU-A",
  "candidates": [
    { "ubicacion_id": 77, "qr_valor": "Pasillo1-F2-C3", "stock": 4 },
    { "ubicacion_id": 91, "qr_valor": "Pasillo3-F1-C2", "stock": 2 }
  ],
  "next_action": "scan_location_qr_or_select_candidate"
}
```

### 7.3 Route contract

```json
GET /api/v1/picking-sessions/9001/route
```

```json
{
  "session_id": 9001,
  "route_version": 4,
  "status": "active",
  "algorithm": "exact_dp",
  "optimality": "optimal_for_cost_function_and_snapshot",
  "objective": {
    "primary": "walking_distance",
    "total_distance": 12,
    "aisle_changes": 3,
    "distance_unit": "fictional_grid_step",
    "return_to_origin": false
  },
  "current_anchor": {
    "ubicacion_id": 77,
    "ruta_x": 3,
    "ruta_y": 2
  },
  "steps": [
    {
      "sequence": 1,
      "remito_item_id": 11,
      "sku": "SKU-A",
      "ubicacion_id": 91,
      "qr_valor": "Pasillo3-F1-C2",
      "estante_nombre": "Pasillo3",
      "fila": 1,
      "columna": 2,
      "ruta_x": 5,
      "ruta_y": 2,
      "quantity": 2,
      "status": "pending",
      "leg_distance": 2,
      "cumulative_distance": 2
    }
  ],
  "exceptions": []
}
```

The frontend must render the server's `qr_valor` and location identity. It must not reconstruct a QR string from `estante_nombre`, `fila`, and `columna`.

### 7.4 Scan contract

Request:

```json
POST /api/v1/picking-sessions/9001/scan
{
  "client_event_id": "evt-scan-024",
  "code": "7791234567890",
  "format": "EAN_13",
  "quantity": 2
}
```

Response for an accepted in-order scan:

```json
{
  "event_id": 14024,
  "client_event_id": "evt-scan-024",
  "outcome": "correct",
  "accepted": true,
  "quantity_accepted": 2,
  "item": {
    "remito_item_id": 11,
    "sku": "SKU-A",
    "picked_quantity": 2,
    "remaining_quantity": 0,
    "status": "picked"
  },
  "route_version_before": 3,
  "route_version_after": 4,
  "remaining_route": {
    "total_distance": 10,
    "aisle_changes": 2,
    "steps": []
  },
  "message_key": "pick.correct"
}
```

The same response shape should be used for `valid_out_of_order`, with `accepted=true` and a different outcome. Rejected outcomes should include `accepted=false`, a recovery action, and no fabricated route facts.

### 7.5 FastAPI to n8n webhook contract

The webhook is post-commit context delivery, not part of the stock transaction. It should be small, authenticated, and tied to the immutable event ID:

```json
{
  "schema_version": 1,
  "event_id": 14024,
  "client_event_id": "evt-scan-024",
  "session_id": 9001,
  "event_type": "scan_result",
  "outcome": "correct",
  "message_key": "pick.correct",
  "locale": "es-AR",
  "facts": {
    "sku": "SKU-A",
    "picked_quantity": 2,
    "remaining_items": 3,
    "next_qr_valor": "Pasillo3-F1-C2",
    "next_estante_nombre": "Pasillo3",
    "route_version": 4
  }
}
```

The `facts` object is copied from the committed FastAPI response. n8n may format it but must not recompute stock, choose a different location, change `route_version`, or write it back to SQLite.

Use HTTPS and an authenticated mechanism such as a bearer credential or signed request with timestamp/replay protection. Store credentials in the deployment secret store, not in this repository or in workflow parameters.

### 7.6 LLM language contract

n8n may pass the webhook facts to an LLM through a strict structured-output request:

```json
{
  "message_key": "pick.correct",
  "locale": "es-AR",
  "facts": {
    "sku": "SKU-A",
    "picked_quantity": 2,
    "next_estante_nombre": "Pasillo3",
    "next_qr_valor": "Pasillo3-F1-C2"
  },
  "allowed_output": ["message_key", "display_text", "speech_text", "locale"]
}
```

Expected LLM output:

```json
{
  "message_key": "pick.correct",
  "locale": "es-AR",
  "display_text": "Correcto. Siguiente ubicacion: Pasillo3-F1-C2.",
  "speech_text": "Correcto. Siguiente ubicacion: Pasillo3, F1 C2."
}
```

The validator must reject unknown fields, wrong message keys, excessive text, and references to facts not present in the input. The LLM output is presentation data only. It must not contain authoritative coordinates, stock values, location IDs, route decisions, SQL, or commands. The frontend should continue to use the FastAPI route response for navigation even if the language response is late or wrong.

### 7.7 edge-tts response contract

The separate audio service receives only the already-validated speech text:

```json
{
  "text": "Correcto. Siguiente ubicacion: Pasillo3, F1 C2.",
  "locale": "es-AR",
  "voice": "configured-voice",
  "cache_key": "sha256-of-normalized-request"
}
```

Successful response:

```json
{
  "ok": true,
  "audio_url": "<audio-url-from-service>",
  "cached": true
}
```

Failure response:

```json
{
  "ok": false,
  "error_code": "timeout",
  "audio_url": null
}
```

The service should cache by normalized locale, voice, and text. An audio URL is optional presentation output; it is never the authority for a pick or route.

## 8. n8n, LLM, and edge-tts Deployment and Failure Design

### 8.1 Component boundary

```text
Phone camera / SvelteKit scanner
              |
              | authenticated FastAPI request
              v
       FastAPI + aiosqlite/SQLite
       - resolve QR/barcode
       - validate session and stock
       - commit event and pick
       - calculate route
              |
              | after commit: small authenticated HTTPS webhook
              v
             n8n
       - validate event schema
       - map message key and facts
       - call strict-output LLM
       - validate language response
       - call edge-tts service
              |
              v
       audio URL or browser speech fallback
```

There is no n8n-to-SQLite connection in this design. n8n talks to FastAPI over HTTPS if it needs additional server facts, and the LLM never receives database credentials or arbitrary tools.

### 8.2 Critical path and latency

The picking critical path is the camera scan through FastAPI, SQLite transaction, route recalculation, and JSON response. n8n, the LLM, and edge-tts are asynchronous presentation work and must not delay that response.

Initial demo targets to measure during implementation, not claims about the current repository:

- A small exact route and scan transaction should feel immediate on the local/demo deployment.
- External language/audio work should have finite timeouts and should not block the item tick.
- The UI should show the deterministic FastAPI message immediately, then replace or supplement it with LLM text/audio only when the external response arrives.

If the n8n call is made directly from FastAPI after commit, use a bounded background task or a delivery worker. For stronger reliability, add an outbox/delivery status to the event pipeline so process restarts do not lose a committed notification. The scan itself is already complete even when notification delivery fails.

### 8.3 Webhook workflow pattern

The initial n8n workflow should remain linear and observable:

```text
Webhook -> Authenticate/validate -> Transform facts
         -> Strict LLM output -> Validate JSON
         -> edge-tts with timeout -> Respond/log
```

Use the immutable `event_id` as the n8n execution correlation ID. Retries must reuse it so downstream handling can be idempotent. Avoid passing a full database dump or the entire remito when only the outcome and next-step facts are required.

### 8.4 Error and fallback matrix

| Failure | Required behavior |
| --- | --- |
| FastAPI validation or stock conflict | Return a typed scan outcome; do not call the LLM as if the pick succeeded. |
| SQLite busy/transaction failure | Return an error without advancing picking state; use existing bounded busy handling and let the user retry with the same or a new event according to the response. |
| n8n unavailable | Keep the FastAPI pick and route result. Show deterministic local text. Retry notification later if delivery infrastructure exists. |
| LLM timeout or invalid JSON | Use a deterministic template keyed by `message_key`; never use unvalidated LLM facts. |
| edge-tts timeout or service error | Keep display text, attempt browser speech, and show no blocking error for the pick. |
| Audio URL cannot be played | Fall back to browser speech or text; do not repeat the stock scan automatically. |
| Stale route version | FastAPI returns the current route version and asks the UI to refresh; the client must not overwrite a newer route with an old response. |
| Duplicate webhook delivery | Correlate by `event_id`; produce at most one externally visible notification per policy, without touching picking state. |

### 8.5 Security boundary

- Require the existing user authentication and deposito authorization for all picking endpoints.
- Authenticate FastAPI-to-n8n requests separately from operator sessions.
- Use HTTPS for all service-to-service calls.
- Keep webhook and LLM/TTS credentials in environment/deployment secrets.
- Validate request size, event timestamps, and event IDs to limit replay and resource abuse.
- Do not include passwords, bearer tokens, database paths, or credentials in webhook context or LLM prompts.

## 9. End-to-End 90-Second Demo Flow

The demo assumes a future fixture with one deposito, configured shelf route coordinates, several existing products with stock in regular locations, and a remito containing three or four lines. The fixture is not currently present in the repository.

| Time | Operator action | Expected observable behavior |
| --- | --- | --- |
| 0-10 s | Open the picking screen and select the prepared remito. | FastAPI creates a session, resolves candidates, shows lines, and displays a provisional route with an explicit `provisional` label. |
| 10-20 s | Scan a location QR at the employee's actual starting point. | The persisted `qr_valor` resolves to the active shelf cell. The session becomes `active`; the route is recalculated from that shelf and shows distance/aisle counts. |
| 20-35 s | Walk to the first recommended stop and scan its product. | FastAPI returns `correct`; the line is ticked live, stock/picking state commits, and the remaining route gets a new version. |
| 35-47 s | Visit another valid remito location before the recommended next stop and scan it. | FastAPI returns `valid_out_of_order`; the pick is accepted and the remaining route is recalculated from the actual location. |
| 47-57 s | Scan a known product that is not in the remito. | FastAPI returns `not_in_remito`; the UI shows the warning and makes no stock or line change. |
| 57-66 s | Scan a product at a wrong location or scan a location that cannot satisfy the pending step. | FastAPI returns `wrong_location`; the UI shows the expected recovery action and does not tick the line. |
| 66-73 s | Repeat an already accepted scan or retry the same network event. | A repeated event ID returns the original result; a new scan of completed work returns `duplicate_already_picked`; stock is not decremented twice. |
| 73-83 s | Observe the next-step instruction. | The deterministic FastAPI text appears immediately. n8n may return validated structured language and an audio URL from edge-tts. |
| 83-90 s | Pick the remaining lines and show the completion state. | The session/remito becomes `completed`, the final route is empty, and the event/audit view shows accepted and rejected scan outcomes. |

### Anchor branch to demonstrate barcode ambiguity

For an alternate run, scan a product barcode instead of the initial QR:

- If the SKU has one eligible physical location for this remito, the session anchors there and recalculates the route.
- If the SKU has multiple eligible locations, the session remains `awaiting_anchor` and shows candidate persisted QR values or asks for a location QR.
- The barcode anchor identifies the start only; it must not silently pick the requested quantity.

This branch demonstrates why a barcode alone is not always a location identity.

## 10. Scope: Must Build vs Explicitly Not Build

### Must build for the MVP

- Add a versioned domain model for remitos, remito items, picking sessions, route snapshots, and picking events.
- Add nullable shelf route coordinates and seed a small, manually verified demo layout.
- Resolve candidate physical stock per line, including quantity splits, while excluding `Suelto` from route stops.
- Implement Manhattan distance, the aisle-change tie-break, stable deterministic ordering, and a route version/snapshot.
- Implement exact dynamic programming for small demo routes and a bounded deterministic heuristic fallback for larger routes.
- Implement session creation, provisional planning, QR/barcode/manual anchors, and route recalculation from the actual start.
- Implement live scan classification for `correct`, `valid_out_of_order`, `not_in_remito`, `duplicate_already_picked`, and `wrong_location`, plus explicit stock/anchor exceptions.
- Enforce transactions and `(session_id, client_event_id)` idempotency in FastAPI.
- Integrate the picking state into the existing SvelteKit scanner without removing its current QR/product distinction.
- Return server-owned route and QR facts to the UI; never build route labels in the browser.
- Add authenticated, post-commit n8n webhook delivery with strict structured-language and TTS fallback behavior.
- Add route, state-machine, idempotency, stock, QR-authority, and integration tests before calling the demo complete.

### Explicitly do not build in this MVP

- A real GIS, indoor positioning system, GPS solution, SLAM, camera localization, or automatic warehouse surveying.
- A physical geometry engine that knows shelf widths, blocked floor cells, doors, stairs, one-way aisles, congestion, or human walking speed.
- A universally optimal route. The exact result is only optimal for the selected cost function and snapshot; the large-route fallback is best effort.
- A direct n8n or LLM connection to SQLite.
- LLM decisions about candidate locations, coordinates, stock, route order, scan validity, or completion.
- QR regeneration during route calculation or a replacement QR identity system.
- Cross-deposito remitos or routes that cross warehouse authorization boundaries.
- Full WMS capabilities such as replenishment, purchasing, receiving, packing, shipping, returns, wave planning, or labor scheduling.
- Robust multi-worker stock reservation until its lifecycle and conflict policy are explicitly designed. The MVP still needs transactional stock checks.
- A mandatory online TTS dependency. Audio is optional presentation output with browser speech fallback.

## 11. Risks, Assumptions, and Unresolved Decisions

| Topic | MVP assumption or current fact | Risk / decision required before implementation |
| --- | --- | --- |
| Shelf map | Route coordinates are fictional integer points assigned per deposito. | Someone must manually map demo shelves and review that the ordering is plausible. |
| Coordinate meaning | Coordinates represent access points, not shelf centers. | A later physical map may require real distances or graph edges. |
| Origin and endpoint | A configured logical origin is used for provisional planning; no return-to-origin by default. | Decide whether the entrance, staging area, or delivery door is the default origin and whether a final endpoint is required. |
| Aisle axis | `ruta_y` is the default aisle index. | Confirm this for the demo depot or add a per-deposito axis setting. |
| Local orientation | `fila` increases bottom-to-top and `columna` left-to-right when facing the shelf. | Current code stores numbers but does not establish this physical convention; confirm it before printing instructional labels. |
| Existing QR values | Persisted `ubicaciones.qr_valor` values are authoritative. | Resizing or renaming can create new values for new cells; route snapshots must preserve the value used at planning time. |
| `Suelto` | It is unlocated stock and never a physical route stop. | Decide the operator workflow for resolving an item whose only stock is `Suelto`; it should become a visible manual exception. |
| Legacy shelves | `deposito_id` exists and historical active shelves were assigned to the central deposito by migration, but route coordinates do not yet exist. | Unmapped or null-deposito shelves must be excluded until explicitly configured; do not silently assign coordinates. |
| Multiple locations | The planner may split one line across cells. | Confirm whether split picks are acceptable operationally or whether a line should prefer one location when total route cost is equal. |
| Pick stock semantics | A successful pick should produce a clear stock-out movement and update item progress atomically. | Choose the exact `movimientos` extension (`salida`/`picking`) before implementation; do not overload `ajuste` without documenting its meaning. |
| Reservations | No full reservation system is required for a one-operator demo. | Add reservations before supporting concurrent pickers or long-lived sessions. |
| Route threshold | Exact DP is for small routes; heuristic is for larger routes. | Benchmark and configure the exact threshold using real demo sizes. |
| Route changes | A new route version is created after each accepted pick or relevant data change. | Decide how to handle an administrative coordinate/QR change during an active session; safest behavior is to mark the old route stale and recalculate. |
| Barcode anchor | A barcode starts only with exactly one eligible physical location in the remito context. | Confirm whether "eligible" must mean any positive stock or enough stock for the entire requested quantity. The safer default is any positive stock for location identity, followed by quantity validation during picking. |
| User language | Structured language examples use neutral Spanish suitable for an `es-AR` demo. | Confirm supported locales and voice configuration outside the route domain. |
| External services | n8n, LLM, and edge-tts are optional and can fail. | Keep their contracts versioned and make the deterministic FastAPI response sufficient for a complete pick. |
| Security | HTTPS and authenticated webhooks are required. | Choose the production secret mechanism and replay window; do not put credentials in the repository. |

## 12. Recommended Implementation Order and Acceptance Criteria

### 12.1 Recommended implementation order

1. **Freeze the MVP contract.** Confirm origin, aisle axis, local orientation, pick stock semantics, split-line behavior, and the exact meaning of `Suelto` exceptions.
2. **Add schema migrations.** Add shelf route coordinates and the remito/session/route/event tables with foreign keys, indexes, status constraints, and the idempotency uniqueness constraint.
3. **Seed and validate the demo map.** Assign coordinates to a small set of existing active shelves. Verify every route candidate has a coordinate and every QR comes from the persisted database value.
4. **Build candidate resolution.** Reuse current product/location/permission logic, but return per-location physical stock and explicit unlocated/insufficient exceptions.
5. **Implement the pure route engine.** Test Manhattan distance, aisle changes, global allocation, quantity splits, exact DP, heuristic fallback, stable ties, and route snapshots independently of HTTP and Svelte.
6. **Implement remito and session APIs.** Start a session by resolving candidates and preparing a provisional plan. Add QR, unique-barcode, and manual anchors with route recalculation.
7. **Implement transactional scan handling.** Add outcome classification, stock-out movement semantics, event persistence, idempotency, route-version updates, and stale-route handling.
8. **Integrate the existing scanner UI.** Reuse `Scanner.svelte` and the QR/product branching in `+page.svelte`. Add live line status, outcome feedback, current route, and candidate selection only where FastAPI requests it.
9. **Add n8n presentation integration.** Implement the authenticated post-commit webhook, strict LLM schema validation, deterministic template fallback, edge-tts cache/timeout, and browser speech fallback.
10. **Run the 90-second demo and harden it.** Exercise normal, out-of-order, wrong-location, not-in-remito, duplicate, ambiguous-anchor, insufficient-stock, external-timeout, and completion paths.

### 12.2 Acceptance criteria

The implementation should not be accepted until all of the following are demonstrable or covered by automated tests:

- A remito automatically resolves its product lines to eligible physical locations before an employee starts.
- A product with stock only in `Suelto` appears as an explicit unlocated/manual exception and never becomes a route stop.
- A shelf with `ruta_x=1,ruta_y=1` and another with `ruta_x=3,ruta_y=3` produce a Manhattan distance of `4` using `2 + 2 = 4`.
- The same input snapshot produces the same route across repeated runs, including equal-distance and equal-aisle ties.
- The primary route objective is total walking distance; fewer aisle changes are considered only after equal distance; stable ordering resolves the remaining tie.
- A test with multiple candidate locations proves that the chosen combination minimizes the complete remito route rather than choosing the nearest candidate to the current employee.
- A unique eligible product barcode can establish the start; an ambiguous or absent eligible location requests a QR or explicit selection instead of guessing.
- A location QR is resolved by exact persisted `ubicaciones.qr_valor`; route calculation never regenerates QR text.
- A valid in-order scan returns `correct`, ticks the item live, changes stock exactly once, and returns a new remaining route.
- A valid physical scan of a later route step returns `valid_out_of_order`, is accepted, and recalculates from the actual current location.
- `not_in_remito`, `wrong_location`, `duplicate_already_picked`, invalid anchor, and unlocated/insufficient-stock cases are distinguishable and do not create false progress.
- Retrying the same `client_event_id` returns the stored result without a second stock movement, line update, or route transition.
- Stock validation, stock-out movement, item progress, picking event, and route version are atomic; a failed transaction leaves no partial pick.
- A route snapshot includes its version and persisted QR/display facts, while historical events remain explainable after later recalculation.
- The frontend relies on FastAPI for route facts and uses the existing QR/product scanner distinction rather than duplicating location resolution logic.
- A successful pick remains successful if n8n, the LLM, or edge-tts is unavailable. Deterministic text and browser speech provide the fallback path.
- LLM output is schema-validated language only and cannot change coordinates, stock, route order, or SQLite state.
- The 90-second demo visibly completes an end-to-end remito and shows accepted, out-of-order, rejected, duplicate, and audio/fallback behavior without requiring secrets in the repository.
