## Exploration: User Management and Permissions System

### Current State

Auth today is name-only and effectively public: `usuarios` stores just `id` and `nombre`; `sessions` stores server-side Bearer tokens; `get_current_user` returns `{id, nombre}`; and `/usuarios` is an **unprotected** public endpoint used by the login screen. All authenticated users can hit every protected endpoint. The `depositos` table and `estantes.deposito_id` already exist, and all live data is assigned to a single "Depósito Central" (migration 006). The scanner, map, and admin screens fetch all deposits/shelves unconditionally.

### Affected Areas

- `backend/migrations/001_create_tables.sql`, `003_seed_users.sql` — schema changes for passwords, admin flag, and permissions.
- `backend/app/repositories/auth_repository.py` — add password verification and user lookup by credentials.
- `backend/app/repositories/usuario_repository.py` — CRUD for users and user-deposit permissions.
- `backend/app/api/v1/deps.py` — add admin guard and deposito-scoped authorization dependency.
- `backend/app/api/v1/endpoints/auth.py` — switch to username + password login; remove public user list.
- `backend/app/api/v1/endpoints/usuarios.py` — protect and expand with create/update/delete and permission management.
- `backend/app/api/v1/endpoints/estantes.py`, `ubicaciones.py`, `sectores.py`, `movimientos.py`, `productos.py` — filter by permitted deposits; enforce write access.
- `backend/app/repositories/estante_repository.py`, `movimiento_repository.py` — accept a list of allowed `deposito_id`s.
- `frontend/src/routes/login/+page.svelte` — replace name selection with username/password form.
- `frontend/src/routes/admin/` — add a "Usuarios" tab with create/edit user and deposit permissions.
- `frontend/src/lib/api/client.ts` — update login signature; add user management endpoints.
- `frontend/src/routes/scanner/+page.svelte`, `mapa/+page.svelte` — dropdowns and lookups already use `listDepositos`/`listEstantes`, so they inherit backend filtering once APIs are updated.

### Approaches

1. **Role-only (global roles: admin/operator/viewer)**
   - Pros: trivial schema — just add `role` to `usuarios`; fast to implement.
   - Cons: cannot express "Operario 1 sees Depósito A but not B"; fails the stated requirement.
   - Effort: Low

2. **Resource-based: `usuario_deposito` junction with role per deposit + global `is_admin` flag**
   - Pros: satisfies per-deposit permissions; global admin handles user management; single-owner mode is just `is_admin=true`; stays simple for the current one-deposit reality.
   - Cons: slightly more joins than a pure role model; need to enforce filters in every endpoint.
   - Effort: Medium

3. **Fine-grained boolean flags (`can_view`, `can_manage`) per deposit + global roles**
   - Pros: very flexible; avoids overloading the word "admin".
   - Cons: more fields and logic than the current MVP needs; easy to create inconsistent flag combinations.
   - Effort: Medium-High

4. **Add multi-tenant `tenant_id` / `organizacion_id` now**
   - Pros: future SaaS structure is partially in place.
   - Cons: every table, query, migration, and the auth model becomes tenant-aware today; major over-engineering for an internal single-tenant app.
   - Effort: High

### Recommendation

Adopt **Approach 2**: a global `is_admin` flag on `usuarios` plus a `usuario_deposito` junction table with a simple role per deposit (`admin`, `operator`, `viewer`).

- **Password storage**: use `bcrypt`. It is the de-facto standard for Python/FastAPI, has a maintained `bcrypt` wheel, and needs no extra configuration. Avoid `passlib` (unmaintained maintenance mode and extra abstraction) and `argon2` (additional native dependency with no meaningful security gain at this scale).
- **Permission model**: `usuario_deposito(usuario_id, deposito_id, role)` where `role IN ('admin','operator','viewer')`. `admin` on a deposit can manage shelves/locations in that deposit; `operator` can scan and create movements; `viewer` is read-only. A global `usuarios.is_admin` bypasses all checks and is required to create other users.
- **Single-owner mode**: the owner signs up, gets `is_admin=true`, and implicitly has full access to all deposits. No special mode is needed — it is just the global-admin case with one user.
- **Multi-tenant future**: do **not** add `tenant_id` now. Keep the door open by making tenancy a future migration scoped at the `depositos`/`organizaciones` level rather than sprinkling it across every table today. The recommended model already separates users from deposits, so adding a tenant boundary later is a contained migration.

### Data Model Proposal (SQL-ready)

```sql
-- Add password + global admin flag to existing users.
ALTER TABLE usuarios ADD COLUMN password_hash TEXT;
ALTER TABLE usuarios ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0;
ALTER TABLE usuarios ADD COLUMN username TEXT UNIQUE;  -- optional: otherwise use nombre

-- Per-deposit permissions.
CREATE TABLE usuario_deposito (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    deposito_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'operator', 'viewer')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (usuario_id, deposito_id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    FOREIGN KEY (deposito_id) REFERENCES depositos(id) ON DELETE CASCADE
);

CREATE INDEX idx_usuario_deposito_usuario ON usuario_deposito(usuario_id);
CREATE INDEX idx_usuario_deposito_deposito ON usuario_deposito(deposito_id);
```

### Permission Checking Architecture

Enforce authorization in **two layers**:

1. **Dependency layer (`backend/app/api/v1/deps.py`)**
   - `require_admin(user)` — global admin guard for user-management endpoints.
   - `get_deposito_ids_for_user(db, user)` — returns the set of allowed `deposito_id`s (or `None` when `is_admin`).
   - `require_deposito_access(user, deposito_id)` — raises 403 if the user cannot access the requested deposit.

2. **Repository layer**
   - `list_estantes`, `list_movimientos`, etc., accept an optional `deposito_ids: list[int] | None` parameter. `None` means global admin (no filter); a list filters every query that joins through `estantes.deposito_id`.

Endpoint-specific rules:

- `GET /estantes`, `/depositos`, `/movimientos`, `/productos/.../stock-total` — filter to accessible deposits.
- `POST /estantes`, `PUT /estantes/{id}`, `DELETE /estantes/{id}` — require `admin` role on the target deposit (or global admin).
- `POST /movimientos`, `PUT /ubicaciones/{id}/assign` — require `operator` or `admin` on the target deposit.
- `GET /sectores/lookup` — reject QR values whose `deposito_id` is not accessible (return 404 to avoid information leakage).
- `/usuarios/*` — global admin only.

### Migration Strategy

1. **Schema migration**: add `password_hash`, `is_admin`, and `usuario_deposito`. Keep `password_hash` nullable temporarily.
2. **Data migration**:
   - Set `Admin.is_admin = true`.
   - Grant `Admin` full access to all existing and future deposits (global admin covers this without rows, or insert explicit rows for clarity).
   - Grant `Operario 1` and `Operario 2` `operator` role on Depósito Central.
3. **Password bootstrap**: because there are no existing passwords, assign a deterministic temporary password (e.g., from an env var) and force change on first login, OR have the admin set passwords for the operators before the feature is considered live.
4. **Frontend/login**: switch the login page to username + password; remove public `/usuarios` list.
5. **Backfill guard**: after a grace period (or immediately in the same release), make `password_hash NOT NULL`.

### Single-Owner Mode Analysis

Single-owner mode requires no special-case code. A shop owner creates one user with `is_admin=true`. Because global admins bypass permission checks, that user owns every deposit, estante, and user-management function. The app behaves exactly like today's MVP but with authentication. If the owner later hires staff, they create non-admin users and grant per-deposit roles.

### Multi-Tenant Future Analysis

**Do not add `tenant_id` now.** The current app is explicitly internal/single-tenant. Adding tenancy prematurely would force every repository query, migration, and endpoint to carry a tenant filter, and it would complicate the audit trail (`movimientos`) and product catalog. The recommended model keeps a clean separation between users and deposits, so a future tenant migration can be done by either:

- Adding `organizaciones` and a nullable `depositos.organizacion_id`, or
- Scoping users to an organization via `usuarios.organizacion_id` and filtering joins.

Both options are additive and do not require rewriting the current permission logic.

### Risks

- **Permission leak from incomplete filtering**: the biggest risk. Any endpoint that forgets to apply `deposito_ids` filtering exposes data across deposits. Mitigation: centralize filtering in repositories and add a lightweight integration test for each protected endpoint.
- **Existing sessions invalidated**: switching login to password auth invalidates current Bearer tokens only when the session expires naturally; existing tokens still work until expiry. Consider clearing `sessions` table during deployment if a hard cutover is acceptable.
- **No automated tests**: the project has zero backend/frontend tests. Manual regression is required, and permission logic is exactly the kind of feature that needs test coverage. Add tests as part of the implementation phase.
- **Password migration UX**: operators currently tap a name to log in. They will need password setup/training. Plan an admin step to set initial passwords.
- **Scanner edge cases**: a user could scan a QR from a deposit they do not own. `/sectores/lookup` must verify deposit access before returning the location, or return a generic 404.

### Effort Estimate (rough)

- **Migrations**: 2 new migrations (schema + data/backfill).
- **New tables**: 1 (`usuario_deposito`).
- **Backend repositories**: update `auth_repository`, `usuario_repository`, `estante_repository`, `movimiento_repository`, and add a permission helper.
- **Backend endpoints**: add ~5 endpoints (create/update/delete user, set password, manage user-deposit permissions); update ~8 existing endpoints with filtering/enforcement.
- **Frontend pages**: rebuild login, add user-management page under `/admin/usuarios`, minor updates to scanner/mapa to remove "Todos" deposit option for non-admins.
- **Timeline**: ~1–2 weeks for a single developer, assuming no test coverage is added; ~2–3 weeks with tests.

### Ready for Proposal

**Yes.** The codebase already has deposits and session auth, so the change is additive rather than architectural. The recommended path is the `usuario_deposito` junction with global `is_admin`, bcrypt passwords, and repository-level deposit filtering. The next step is a formal SDD proposal defining the exact endpoint shapes, frontend flows, and the password-bootstrap UX.