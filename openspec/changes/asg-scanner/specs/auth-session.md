# Spec: auth-session

## Capability Summary
Simple session-based login for audit/tracking purposes only. Not a security boundary. Every stock movement records which user performed it.

## Requirements

### Functional
1. The system MUST allow a user to log in by providing only a `nombre` (name). No password SHALL be required.
2. The backend MUST create a server-side session upon successful login and return a session identifier to the client.
3. The session MUST be stored server-side (e.g., in-memory or SQLite-backed session store) and attached to every subsequent authenticated request.
4. The backend MUST reject any request that requires authentication when no valid session is present, returning HTTP 401 Unauthorized.
5. The session MUST include the user's `id` and `nombre` so that audit records can reference the acting user.
6. The system SHOULD support session expiry after a configurable idle period (default: 8 hours).
7. The system MAY allow explicit logout, which MUST invalidate the server-side session immediately.

### Non-Functional
8. Session creation latency MUST be under 200 ms on warehouse WiFi.
9. The login UI MUST be the first screen shown to unauthenticated users.

## Scenarios

### Scenario 1: Happy Path — User Logs In
**Given** the user is on the login screen  
**When** the user enters a valid name "Juan Perez" and taps "Ingresar"  
**Then** the backend creates a session for "Juan Perez"  
**And** the client stores the session identifier  
**And** the user is redirected to the scanner screen

### Scenario 2: Edge Case — Empty Name
**Given** the user is on the login screen  
**When** the user submits an empty name  
**Then** the frontend MUST block submission with a validation message  
**And** no request is sent to the backend

### Scenario 3: Error Case — Unauthenticated User Tries to Scan
**Given** a user without an active session  
**When** the user navigates directly to the scanner page or sends a scan request  
**Then** the backend MUST return HTTP 401 Unauthorized  
**And** the frontend MUST redirect the user to the login screen

### Scenario 4: Edge Case — Session Expiry
**Given** a user has an active session that has exceeded the idle timeout (e.g., 8 hours)  
**When** the user attempts to save a stock movement  
**Then** the backend MUST return HTTP 401 Unauthorized  
**And** the frontend MUST redirect to the login screen  
**And** any unsaved form data SHOULD be preserved after re-authentication (if feasible)

### Scenario 5: Happy Path — Logout
**Given** a user has an active session  
**When** the user taps "Cerrar sesion"  
**Then** the backend MUST invalidate the session  
**And** the client MUST clear the session identifier  
**And** the user is redirected to the login screen

## Design Notes (from fastapi-templates skill)
- Use FastAPI dependency injection with `Depends(get_current_user)` to enforce session checks on protected routes.
- Session store can be a simple in-memory dict for MVP; migrate to SQLite-backed sessions if multi-process deployment is needed.
- Return Pydantic `UserSession` schema from login endpoint containing `session_id`, `user_id`, and `nombre`.
