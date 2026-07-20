# QR Print Endpoints Specification

## Purpose

Expose authenticated HTTP endpoints that serve individual QR images, bundle an estante's QRs as a ZIP, and render printable A4 sheets.

## Requirements

### Requirement: Single QR Image Endpoint

The system MUST expose `GET /api/v1/ubicaciones/{id}/qr.png?size={px}`.

The endpoint SHALL require authentication.

The endpoint SHALL return the PNG image for the ubicacion's `qr_valor` with `Content-Type: image/png`.

The `size` query parameter SHALL default to the configured default size and MUST be constrained to a range of 50–1000 pixels.

#### Scenario: Request a single ubicacion QR

- GIVEN an active ubicacion with `qr_valor` "A-F1-C1"
- WHEN an authenticated client calls `GET /api/v1/ubicaciones/{id}/qr.png?size=200`
- THEN the response status is 200
- AND the response body is a valid PNG image encoding "A-F1-C1"
- AND the response header `Content-Type` is `image/png`

#### Scenario: Invalid ubicacion ID

- GIVEN a `ubicacion_id` that does not exist
- WHEN an authenticated client requests its QR
- THEN the response status is 404
- AND the response body explains that the ubicacion was not found

#### Scenario: Size parameter out of range

- GIVEN an authenticated client requests `GET /api/v1/ubicaciones/{id}/qr.png?size=20`
- WHEN the request is validated
- THEN the response status is 422
- AND the error indicates the allowed size range

#### Scenario: Unauthenticated request

- GIVEN a client without a valid authentication token
- WHEN it requests `GET /api/v1/ubicaciones/{id}/qr.png`
- THEN the response status is 401

---

### Requirement: Estante QR Bundle Endpoint

The system MUST expose `GET /api/v1/estantes/{id}/qrs`.

The endpoint SHALL require authentication and return a ZIP archive with `Content-Type: application/zip`.

Each entry in the ZIP SHALL be named `{qr_valor}.png` and contain the QR image for one ubicacion.

#### Scenario: Download all QRs for an estante

- GIVEN an estante with 8 ubicaciones
- WHEN an authenticated client calls `GET /api/v1/estantes/{id}/qrs`
- THEN the response status is 200
- AND the response body is a valid ZIP archive
- AND the ZIP contains exactly 8 PNG files named by their `qr_valor`

#### Scenario: Invalid estante ID for bundle

- GIVEN an `estante_id` that does not exist
- WHEN an authenticated client requests the QR bundle
- THEN the response status is 404

---

### Requirement: Printable A4 Sheet Endpoint

The system MUST expose `GET /api/v1/estantes/{id}/qrs/print?per_page={n}&size={px}`.

The endpoint SHALL require authentication and return a PNG image suitable for A4 printing at 300 DPI (2480×3508 pixels per page).

The `per_page` parameter SHALL control how many QR codes fit on each A4 page and MUST accept only the values 1, 2, 4, 6, 8, or 9, defaulting to 4.

The `size` parameter SHALL follow the same 50–1000 pixel range as the single-QR endpoint.

If the estante has more ubicaciones than `per_page`, the response SHALL contain all QRs across multiple A4 pages or a single tall image with page boundaries.

#### Scenario: Print a small estante with four QRs per page

- GIVEN an estante with 4 ubicaciones
- WHEN an authenticated client calls `GET /api/v1/estantes/{id}/qrs/print?per_page=4&size=200`
- THEN the response status is 200
- AND the body is a PNG with at least one A4 page containing all 4 QRs in a 2×2 grid

#### Scenario: Print a large estante across multiple pages

- GIVEN an estante with 35 ubicaciones
- WHEN an authenticated client calls `GET /api/v1/estantes/{id}/qrs/print?per_page=4&size=200`
- THEN the response is a PNG containing all 35 QRs
- AND the layout spans multiple A4 pages or a tall image with clear page separations

#### Scenario: Invalid `per_page` value

- GIVEN an authenticated client requests `GET /api/v1/estantes/{id}/qrs/print?per_page=5`
- WHEN the request is validated
- THEN the response status is 422
- AND the error lists the allowed values

#### Scenario: Soft-deleted estante

- GIVEN an estante that has been soft-deleted
- WHEN an authenticated client requests its print sheet
- THEN the response status is 404
