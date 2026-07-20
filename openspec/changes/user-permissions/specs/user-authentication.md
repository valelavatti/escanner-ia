# Spec: user-authentication

## Capability Summary

Username + password authentication using bcrypt. Replaces the previous name-only login while preserving the existing server-side session token contract.

## Requirements

### Functional

1. The system MUST accept `POST /api/v1/auth/login` with body `{nombre: string, password: string}`.
2. The system MUST verify the password against the stored `password_hash` using `bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))`.
3. If the user does not exist OR the password does not match, the system MUST return HTTP 401 with the identical message `"Usuario o contraseña incorrectos"` and MUST NOT reveal which field failed.
4. If the user exists but has no `password_hash` (legacy user), the system MUST return HTTP 401 with message `"Usuario sin contraseña configurada. Contacte al administrador."`
5. On successful verification, the system MUST create a server-side session token, update `last_login_at`, and return `{token, usuario: {id, nombre, is_admin}, expires_at}`.
6. `GET /api/v1/auth/me` MUST return the current user's `id`, `nombre`, `is_admin`, and a list of assigned `depositos` with their roles.
7. `POST /api/v1/auth/logout` MUST invalidate the current session as before.
8. The system MUST NOT include `password_hash` in any response.

### Non-Functional

9. Password hashing MUST use `bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())`.
10. Login latency SHOULD be under 300 ms on warehouse WiFi.

## Scenarios

### Scenario: Happy path — valid credentials

- **Given** a user exists with `nombre` "Operario 1" and a valid `password_hash`
- **When** the client POSTs `/auth/login` with `{nombre: "Operario 1", password: "correct"}`
- **Then** the response status is 200 and contains a `token`, `expires_at`, and `usuario` with `id`, `nombre`, and `is_admin`
- **And** `password_hash` is not present in the response

### Scenario: Wrong password

- **Given** a user exists with `nombre` "Operario 1" and password "correct"
- **When** the client POSTs `/auth/login` with `{nombre: "Operario 1", password: "wrong"}`
- **Then** the response status is 401 with detail `"Usuario o contraseña incorrectos"`

### Scenario: Nonexistent user

- **Given** no user named "Fantasma" exists
- **When** the client POSTs `/auth/login` with `{nombre: "Fantasma", password: "any"}`
- **Then** the response status is 401 with detail `"Usuario o contraseña incorrectos"`

### Scenario: Legacy user without password hash

- **Given** a user exists with `nombre` "Legacy" and `password_hash` is NULL
- **When** the client POSTs `/auth/login` with any password
- **Then** the response status is 401 with detail `"Usuario sin contraseña configurada. Contacte al administrador."`

### Scenario: /me returns permissions

- **Given** an authenticated admin with access to Depósito Central as `admin`
- **When** the client GETs `/auth/me`
- **Then** the response contains `is_admin: true` and a `depositos` array including `{deposito_id, nombre, role}`

### Scenario: password_hash never exposed

- **Given** an authenticated user
- **When** the client calls `/auth/login`, `/auth/me`, or `/auth/logout`
- **Then** no response body contains a `password_hash` field
