# Spec: deposito-permissions

## Capability Summary

Depósito-level access control. Global admins bypass filters; other users only see and act within assigned depósitos.

## Requirements

### Functional

1. `get_current_user` MUST return the authenticated user including the `is_admin` flag.
2. `get_deposito_ids_for_user(db, user)` MUST return `None` when `is_admin` is true, or the list of `deposito_id` values from `usuario_deposito` for that user.
3. `require_deposito_access(user, deposito_id)` MUST return HTTP 403 when `deposito_id` is not in the user's accessible depósito list, unless the user is an admin.
4. List endpoints returning estantes, ubicaciones, or movimientos MUST filter results to the user's accessible depósito IDs when the user is not an admin.
5. Endpoints operating on a specific estante or ubicación MUST verify the resource belongs to an accessible depósito and return HTTP 403 if not.
6. `GET /sectores/lookup` MUST verify the scanned ubicación's estante belongs to an accessible depósito and return HTTP 403 if not.
7. Users with `operator` role MUST be able to create movimientos in their assigned depósitos.
8. Users with `viewer` role MAY view data but MUST receive HTTP 403 on `POST /movimientos`.

## Scenarios

### Scenario: Admin lists all estantes

- **Given** an admin and estantes in Depósito Central and Depósito Norte
- **When** the admin GETs `/estantes`
- **Then** the response contains estantes from both depositos

### Scenario: Operator lists only authorized estantes

- **Given** an operator assigned only to Depósito Central
- **When** the operator GETs `/estantes`
- **Then** the response contains only estantes whose `deposito_id` is Depósito Central

### Scenario: Viewer lists only authorized estantes

- **Given** a viewer assigned only to Depósito Central
- **When** the viewer GETs `/estantes`
- **Then** the response contains only estantes in Depósito Central

### Scenario: Operator scans unauthorized QR

- **Given** an operator assigned to Depósito Central
- **When** the operator calls `/sectores/lookup?qr_valor=X` for a ubicación in Depósito Norte
- **Then** the response status is 403

### Scenario: Viewer cannot create movimiento

- **Given** a viewer assigned to Depósito Central
- **When** the viewer POSTs `/movimientos` with a valid ubicación in Depósito Central
- **Then** the response status is 403

### Scenario: Operator creates authorized movimiento

- **Given** an operator assigned to Depósito Central
- **When** the operator POSTs `/movimientos` with a ubicación in Depósito Central
- **Then** the response status is 201

### Scenario: Operator lists filtered movimientos

- **Given** an operator assigned to Depósito Central and movements exist in both depositos
- **When** the operator GETs `/movimientos`
- **Then** the response contains only movements whose ubicación belongs to Depósito Central

### Scenario: User with no depósitos sees nothing

- **Given** a user with no `usuario_deposito` assignments
- **When** the user GETs `/estantes`, `/movimientos`, or `/sectores/lookup` for any depósito
- **Then** list responses are empty and lookups outside their (empty) set return 403

### Scenario: Admin creates estante anywhere

- **Given** an admin
- **When** the admin POSTs `/estantes` with `deposito_id` set to any existing depósito
- **Then** the response status is 201
