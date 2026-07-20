# Delta for scanner (permission-aware scanning)

## ADDED Requirements

### Requirement: Depósito permission check on sector QR lookup

When the scanner decodes a `QR_CODE`, the system MUST look up the ubicación and then verify the current user has access to that ubicación's depósito. If access is denied, the backend MUST return HTTP 403 and the scanner UI MUST show a red flash with the text `"No tenés permiso para este depósito"`.

#### Scenario: Authorized QR scan

- **Given** an operator assigned to Depósito Central
- **When** the operator scans a QR code for a ubicación in Depósito Central
- **Then** `/sectores/lookup` returns 200
- **And** the scanner shows a green flash and anchors the location

#### Scenario: Unauthorized QR scan

- **Given** an operator assigned to Depósito Central
- **When** the operator scans a QR code for a ubicación in Depósito Norte
- **Then** `/sectores/lookup` returns 403
- **And** the scanner shows a red flash `"No tenés permiso para este depósito"`
- **And** the location is NOT anchored

### Requirement: Depósito permission check on stock save

Before creating a movimiento, the system MUST verify the anchored ubicación's depósito is accessible to the current user. If not, the backend MUST return HTTP 403 and the scanner UI MUST show a red flash.

#### Scenario: Authorized save

- **Given** an operator has anchored a ubicación in Depósito Central
- **When** the operator saves a stock movement
- **Then** `POST /movimientos` returns 201
- **And** the scanner shows a green flash

#### Scenario: Unauthorized save

- **Given** an operator has anchored a ubicación (e.g., via stale client state) in Depósito Norte to which they do not have access
- **When** the operator saves a stock movement
- **Then** `POST /movimientos` returns 403
- **And** the scanner shows a red flash

#### Scenario: Viewer cannot save

- **Given** a viewer assigned to Depósito Central
- **When** the viewer attempts to save a stock movement
- **Then** `POST /movimientos` returns 403 before any stock logic runs

### Requirement: Permission-aware manual location selector

The manual location selector MUST only list estantes from depósitos the user can access. Within those estantes, only ubicaciones belonging to accessible depósitos MAY be selected.

#### Scenario: Manual selector filters unauthorized depósitos

- **Given** an operator assigned only to Depósito Central
- **When** the operator opens the manual location selector
- **Then** the depósito dropdown contains only Depósito Central
- **And** the estante list contains only estantes in Depósito Central

### Requirement: Display assigned depósitos

The scanner page SHOULD display the names of the current user's assigned depósitos.

#### Scenario: Operator sees assigned depósitos

- **Given** an operator assigned to Depósito Central
- **When** the operator opens the scanner page
- **Then** the page shows "Depósito Central" as an assigned depósito

## MODIFIED Requirements

### Requirement: QR and barcode scan handling

On a successful scan, the callback MUST inspect `result.result.format?.formatName` to determine the code type:

- If `QR_CODE`, the decoded text MUST be treated as a sector/ubicacion identifier. The system SHALL look it up in the `ubicaciones` table. If the ubicación is not found, a clear error message MUST be shown and the location MUST NOT be anchored. If the ubicación is found, the system SHALL verify the current user has access to the ubicación's depósito. If access is denied, the UI MUST show a red flash `"No tenés permiso para este depósito"` and the location MUST NOT be anchored. If access is allowed, the location is anchored.
- If `EAN_13`, `CODE_128`, or `UPC_A`, the decoded text MUST be treated as a `codigo_de_barra`. The system SHALL look up the product in the `productos` table.

(Previously: QR lookup anchored any found ubicación without checking depósito access.)

#### Scenario: Scan sector QR in authorized depósito

- **Given** the user is on the scanner page with an active session
- **And** the user is assigned to Depósito Central
- **When** the user scans a QR code whose text matches ubicacion id `U-001` in Depósito Central
- **Then** the system queries `/sectores/lookup` and receives 200
- **And** the location is anchored and displayed

#### Scenario: Scan sector QR in unauthorized depósito

- **Given** the user is on the scanner page with an active session
- **And** the user is assigned to Depósito Central
- **When** the user scans a QR code whose text matches ubicacion id `U-002` in Depósito Norte
- **Then** `/sectores/lookup` returns 403
- **And** the UI shows a red flash `"No tenés permiso para este depósito"`
- **And** the location is NOT anchored

### Requirement: Save stock movement

When a product barcode is scanned and a ubicación is anchored, the user MUST be able to enter a stock quantity. Upon saving, the backend MUST:

1. Verify the current user has access to the anchored ubicación's depósito; if not, return HTTP 403.
2. Verify the user is not a `viewer`; if the user is a viewer, return HTTP 403.
3. Read the current `stock_actual` for the product at the anchored `ubicacion`.
4. Calculate `stock_nuevo = stock_anterior + cantidad` for an "alta" (addition), or `stock_nuevo = cantidad` for an "ajuste" (adjustment).
5. Insert a `movimientos` record with `tipo`, `usuario_id`, `producto_id`, `ubicacion_id`, `cantidad`, `stock_anterior`, `stock_nuevo`, and `timestamp`.
6. Update `ubicaciones.stock_actual` to `stock_nuevo`.

(Previously: stock save did not check depósito access or viewer role.)

#### Scenario: Operator saves movement in authorized depósito

- **Given** an operator has anchored ubicación `U-001` in Depósito Central
- **And** product `P-100` has `stock_actual = 10` at `U-001`
- **When** the user scans product `P-100`, enters quantity `5`, and taps "Guardar" with movement type "alta"
- **Then** the backend verifies depósito access
- **And** creates a `movimientos` record with `cantidad = 5`, `stock_anterior = 10`, `stock_nuevo = 15`, `tipo = "alta"`
- **And** updates `ubicaciones.stock_actual` to `15`
- **And** returns HTTP 201

#### Scenario: Viewer save blocked

- **Given** a viewer has anchored ubicación `U-001` in Depósito Central
- **When** the viewer taps "Guardar"
- **Then** the backend returns HTTP 403 before recording any movement
