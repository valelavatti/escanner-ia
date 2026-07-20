# Spec: user-management

## Capability Summary

Admin-only CRUD for users, password management, and depósito/role assignments.

## Requirements

### Functional

1. All `/api/v1/usuarios/*` endpoints MUST be accessible only to users with `is_admin = true`; non-admin access MUST return HTTP 403.
2. `GET /api/v1/usuarios` MUST list all users with `id`, `nombre`, `is_admin`, and assigned `depositos` with roles; it MUST NOT include `password_hash`.
3. `POST /api/v1/usuarios` MUST create a user from `{nombre, password, is_admin}` and return the created user without `password_hash`.
4. The system MUST reject creating a user with a duplicate `nombre` with HTTP 409.
5. `PUT /api/v1/usuarios/{id}` MUST update any provided fields; if `password` is provided, the system MUST re-hash it with bcrypt; otherwise the existing hash MUST be preserved.
6. `DELETE /api/v1/usuarios/{id}` MUST hard-delete the user; `usuario_deposito` rows MUST be removed via `ON DELETE CASCADE`.
7. The system MUST reject deleting the authenticated user themselves with HTTP 400 and message `"No puede eliminarse a sí mismo"`.
8. The system MUST reject deleting the last remaining admin with HTTP 400 and message `"Debe existir al menos un administrador"`.
9. `POST /api/v1/usuarios/{id}/depositos` MUST assign `{deposito_id, role}` to the user, where `role` is one of `admin`, `operator`, or `viewer`. Duplicate assignment for the same depósito MUST return HTTP 409.
10. `DELETE /api/v1/usuarios/{id}/depositos/{deposito_id}` MUST remove that depósito access.
11. `GET /api/v1/usuarios/{id}/depositos` MUST return the user's depósito assignments.
12. `password_hash` MUST NOT appear in any response.

## Scenarios

### Scenario: Admin creates user

- **Given** an authenticated admin
- **When** the admin POSTs `/usuarios` with `{nombre: "Nuevo", password: "secret", is_admin: false}`
- **Then** the response status is 201 and contains the new user with `id`, `nombre`, `is_admin`, and no `password_hash`

### Scenario: Duplicate user name

- **Given** a user named "Nuevo" already exists
- **When** the admin POSTs `/usuarios` with `{nombre: "Nuevo", password: "secret", is_admin: false}`
- **Then** the response status is 409

### Scenario: Admin updates password

- **Given** a user exists with an old bcrypt hash
- **When** the admin PUTs `/usuarios/{id}` with `{password: "newsecret"}`
- **Then** the stored `password_hash` is updated
- **And** the user's existing sessions remain valid

### Scenario: Admin deletes user

- **Given** an admin and a non-admin user "Borrable" assigned to Depósito Central
- **When** the admin DELETEs `/usuarios/{id}`
- **Then** the response status is 200, the user is removed, and all `usuario_deposito` rows for that user are removed

### Scenario: Admin cannot delete self

- **Given** an authenticated admin with id 1
- **When** the admin DELETEs `/usuarios/1`
- **Then** the response status is 400 with detail `"No puede eliminarse a sí mismo"`

### Scenario: Cannot delete last admin

- **Given** only one admin remains in the system
- **When** the admin DELETEs that user's id
- **Then** the response status is 400 with detail `"Debe existir al menos un administrador"`

### Scenario: Non-admin blocked

- **Given** an authenticated operator
- **When** the operator GETs `/usuarios`
- **Then** the response status is 403

### Scenario: Admin assigns depósito

- **Given** a user and a depósito "Depósito Central"
- **When** the admin POSTs `/usuarios/{id}/depositos` with `{deposito_id: 1, role: "operator"}`
- **Then** the response status is 201 and contains the assignment

### Scenario: Duplicate depósito assignment

- **Given** the user is already assigned to depósito 1
- **When** the admin POSTs `/usuarios/{id}/depositos` with `{deposito_id: 1, role: "viewer"}`
- **Then** the response status is 409

### Scenario: Remove depósito access

- **Given** a user assigned to depósito 1
- **When** the admin DELETEs `/usuarios/{id}/depositos/1`
- **Then** the response status is 200 and the assignment no longer exists

### Scenario: password_hash never exposed

- **Given** an authenticated admin
- **When** calling any `/usuarios/*` endpoint
- **Then** no response body contains `password_hash`
