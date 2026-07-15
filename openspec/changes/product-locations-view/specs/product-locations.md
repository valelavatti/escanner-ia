# Spec: product-locations

## Capability Summary
Lookup all ubicaciones where a product is stored, with per-location stock, total stock, and deposito-permission filtering. Powers the fallback flow when a product is scanned without an anchored location: a tappable card lets the operator pick a location, which is then anchored so the existing stock-entry flow continues.

## Requirements

### Requirement: Product Locations Lookup Endpoint

The system MUST expose `GET /api/v1/productos/{codigo_de_barra}/ubicaciones` returning the product plus every ubicacion where it has stock, filtered by the caller's deposito permissions.

- The endpoint MUST be protected (requires authentication).
- The response MUST contain: `sku`, `descripcion`, `codigo_de_barra`, `stock_total`, and `ubicaciones[]`.
- Each `ubicaciones` entry MUST contain: `ubicacion_id`, `estante_nombre`, `qr_valor`, `fila`, `columna`, `stock`, `deposito_nombre`.
- Regular shelves MUST report `stock` from `ubicaciones.stock_actual` WHERE `producto_id = sku`.
- Suelto MUST appear as an entry when the product has movements there, with `stock` equal to the SUM of `movimientos.cantidad` for that product across Suelto ubicaciones.
- `stock_total` MUST equal the sum of all returned ubicacion `stock` values.
- The endpoint MUST return 404 when no product matches `codigo_de_barra`.
- For admin users, the endpoint MUST return ubicaciones across ALL depositos.
- For non-admin users, the endpoint MUST return only ubicaciones whose estante belongs to one of the user's accessible depositos (reusing `get_deposito_ids_for_user`); an empty permission list MUST yield an empty `ubicaciones` list.

#### Scenario: Happy path — product in two shelves

- GIVEN product SKU "P-1" with barcode "7501234567890" has stock 15 on shelf A and 10 on shelf B
- WHEN a user requests `GET /api/v1/productos/7501234567890/ubicaciones`
- THEN the response status is 200
- AND `stock_total` is 25 and `ubicaciones` contains two entries with stocks 15 and 10

#### Scenario: Product only in Suelto

- GIVEN product "P-2" has no regular shelf assignment but its Suelto movements sum to 5
- WHEN a user requests its ubicaciones
- THEN the response contains one Suelto entry with `stock` 5 and `stock_total` 5

#### Scenario: Product not in any location

- GIVEN product "P-3" exists but has no ubicacion and no Suelto movements
- WHEN a user requests its ubicaciones
- THEN the response status is 200 with `stock_total` 0 and an empty `ubicaciones` array

#### Scenario: Product not found

- GIVEN no product has barcode "0000000000000"
- WHEN a user requests that barcode's ubicaciones
- THEN the response status is 404 with detail "Producto no encontrado"

#### Scenario: Non-admin sees only accessible depositos

- GIVEN user "U" has access only to deposito "D1" and product "P-1" has stock in D1 and D2
- WHEN "U" requests the ubicaciones
- THEN only D1 ubicaciones are returned

#### Scenario: Admin sees all depositos

- GIVEN an admin user requests a product with stock across multiple depositos
- WHEN the request is processed
- THEN ubicaciones from every deposito are returned

#### Scenario: Non-admin with no deposito access

- GIVEN a non-admin user whose accessible deposito list is empty
- WHEN they request a product's ubicaciones
- THEN the response status is 200 with an empty `ubicaciones` array

### Requirement: Product Locations Card (Frontend)

The frontend MUST render a `ProductLocationsCard` when a product is scanned without an anchored location and the lookup returns one or more ubicaciones.

- The card MUST show a product header with SKU, descripcion, and `stock_total`.
- The card MUST render each returned ubicacion as a tappable card.
- Tapping a location card MUST anchor that location and transition into the existing `ProductCard` + `StockInput` flow.
- When `ubicaciones` is empty, the card MUST show "Producto no encontrado en ninguna ubicación" and offer scanning a QR to assign the product.
- The card MUST provide a "Cancelar" button that returns to scanning without anchoring any location.
- Touch targets MUST be at least 48x48px (mobile-first).

#### Scenario: Tap a location anchors it

- GIVEN the card shows two locations with stock 15 and 10
- WHEN the user taps the second location
- THEN that location is anchored and the stock entry form appears

#### Scenario: Cancelar returns to scanning

- GIVEN the card is displayed
- WHEN the user taps "Cancelar"
- THEN the card closes, no location is anchored, and the scanner resumes

#### Scenario: Empty locations

- GIVEN the card receives an empty `ubicaciones` array
- THEN it shows "Producto no encontrado en ninguna ubicación"
