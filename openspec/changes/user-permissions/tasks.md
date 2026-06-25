# SDD Tasks: user-permissions

## Phase 1 — Backend auth + permission infrastructure (PR 1)

### 1.1 Migration 009: add `password_hash` and `is_admin` to `usuarios`

- **Skill / Context7**: `SQLite Database Expert`
- **Depends on**: —
- **Files to create/modify**:
  - Create `backend/migrations/009_add_password_and_admin_to_usuarios.sql`
- **Acceptance criteria**:
  - [x] Adds nullable `password_hash TEXT` column.
  - [x] Adds `is_admin BOOLEAN NOT NULL DEFAULT 0` column.
  - [x] Migration is idempotent and registered as version 9.
- **Estimated lines**: 5
- **PR slice**: PR 1

### 1.2 Migration 010: create `usuario_deposito` junction table

- **Skill / Context7**: `SQLite Database Expert`
- **Depends on**: 1.1
- **Files to create/modify**:
  - Create `backend/migrations/010_create_usuario_deposito.sql`
- **Acceptance criteria**:
  - [x] Creates `usuario_deposito` table with FKs to `usuarios(id)` and `depositos(id)`, `ON DELETE CASCADE`, and `role` CHECK constraint (`admin`/`operator`/`viewer`).
  - [x] Adds indexes on `usuario_id` and `deposito_id`.
  - [x] Migration is idempotent and registered as version 10.
- **Estimated lines**: 15
- **PR slice**: PR 1

### 1.3 Migration 011: seed Admin, remove seed operators, clear sessions

- **Skill / Context7**: `SQLite Database Expert`, Context7 `/pyca/bcrypt`
- **Depends on**: 1.2
- **Files to create/modify**:
  - Create `backend/migrations/011_seed_admin_permissions.sql`
- **Acceptance criteria**:
  - [x] Hashes Admin password "Accesaniga@26" with `bcrypt.hashpw(..., bcrypt.gensalt())` and stores decoded ASCII `TEXT`.
  - [x] Sets `Admin` as `is_admin = 1` with the password hash.
  - [x] Deletes `Operario 1` and `Operario 2` (per user decision).
  - [x] Clears `sessions` table to force re-login with the new auth system (per user decision).
- **Estimated lines**: 15
- **PR slice**: PR 1

### 1.4 Register migration 011 in runner

- **Skill / Context7**: `SQLite Database Expert`
- **Depends on**: 1.3
- **Files to create/modify**:
  - Modify `backend/app/core/migrations.py`
- **Acceptance criteria**:
  - [x] Registers version 11 in the `MIGRATIONS` list.
- **Estimated lines**: 3
- **PR slice**: PR 1

### 1.5 Add `bcrypt` dependency

- **Skill / Context7**: Context7 `/pyca/bcrypt`
- **Depends on**: —
- **Files to create/modify**:
  - Modify `backend/requirements.txt`
- **Acceptance criteria**:
  - [x] Adds `bcrypt>=4.0` (or compatible pinned version) to `requirements.txt`.
- **Estimated lines**: 1
- **PR slice**: PR 1

### 1.6 Update `auth_repository` with password hashing and `is_admin` selection

- **Skill / Context7**: `fastapi-templates`, Context7 `/pyca/bcrypt`
- **Depends on**: 1.5
- **Files to create/modify**:
  - Modify `backend/app/repositories/auth_repository.py`
- **Acceptance criteria**:
  - [x] `get_user_by_name` selects `password_hash` and `is_admin`.
  - [x] `get_session` joins `usuarios.is_admin` into the session row.
  - [x] New `hash_password(password: str) -> str` returns a decoded bcrypt hash.
  - [x] New `verify_password(password: str, password_hash: str) -> bool` uses `bcrypt.checkpw` on encoded bytes.
- **Estimated lines**: 40
- **PR slice**: PR 1

### 1.7 Extend `deps.py` with permission helpers

- **Skill / Context7**: `fastapi-templates`
- **Depends on**: 1.6
- **Files to create/modify**:
  - Modify `backend/app/api/v1/deps.py`
- **Acceptance criteria**:
  - [x] `UsuarioResponse` dataclass includes `is_admin: bool`.
  - [x] `get_current_user` returns `UsuarioResponse(id, nombre, is_admin)` from the session row.
  - [x] New `require_admin(user = Depends(get_current_user))` raises `HTTPException(403)` when `not user.is_admin`.
  - [x] New `get_deposito_ids_for_user(db, user) -> Optional[list[int]]` returns `None` for admins, otherwise the user's `deposito_id` list (may be empty).
  - [x] New `require_deposito_access(user, deposito_id, db)` raises `HTTPException(403)` for unauthorized depósitos; `NULL` depósito_id is denied to non-admins.
  - [x] New `require_deposito_role(user, deposito_id, db, allowed_roles: set[str])` checks access and role, raising `HTTPException(403)` on failure.
- **Estimated lines**: 80
- **PR slice**: PR 1

### 1.8 Update auth schemas and `auth.py` endpoints for username/password login

- **Skill / Context7**: `fastapi-templates`
- **Depends on**: 1.7
- **Files to create/modify**:
  - Modify `backend/app/schemas/auth.py`
  - Modify `backend/app/api/v1/endpoints/auth.py`
- **Acceptance criteria**:
  - [x] `LoginRequest` includes `nombre` and `password` fields.
  - [x] `UsuarioResponse` includes `is_admin`.
  - [x] `LoginResponse` includes `token`, `usuario`, `expires_at`.
  - [x] `MeResponse` includes `usuario` and `depositos` (with `deposito_id`, `nombre`, `role`).
  - [x] `POST /auth/login` verifies password with `auth_repository.verify_password`; returns `401 "Usuario o contraseña incorrectos"` for wrong/missing user; returns `401 "Usuario sin contraseña configurada. Contacte al administrador."` for null `password_hash`.
  - [x] `GET /auth/me` returns `usuario` and `depositos` fetched from `usuario_deposito` joined with `depositos`; never exposes `password_hash`.
- **Estimated lines**: 70
- **PR slice**: PR 1

### 1.9 Create `usuario_repository` CRUD and depósito assignment functions

- **Skill / Context7**: `SQLite Database Expert`, `fastapi-templates`
- **Depends on**: 1.2
- **Files to create/modify**:
  - Modify `backend/app/repositories/usuario_repository.py`
- **Acceptance criteria**:
  - [x] `list_usuarios` returns users with their depósito assignments (no `password_hash`).
  - [x] `get_usuario_by_id` returns a single user (no `password_hash`).
  - [x] `create_usuario(db, nombre, password_hash, is_admin) -> int` inserts a new user and returns the id.
  - [x] `update_usuario(db, id, ...)` updates provided fields including optional password re-hash.
  - [x] `delete_usuario(db, id)` hard-deletes the user; `usuario_deposito` rows removed by CASCADE.
  - [x] `count_admins(db) -> int` counts users with `is_admin = 1`.
  - [x] `list_usuario_depositos`, `assign_usuario_deposito`, `remove_usuario_deposito` manage assignments with duplicate checks.
- **Estimated lines**: 100
- **PR slice**: PR 1

### 1.10 Rewrite `usuarios.py` endpoint as admin-only user management CRUD

- **Skill / Context7**: `fastapi-templates`
- **Depends on**: 1.8, 1.9
- **Files to create/modify**:
  - Modify `backend/app/api/v1/endpoints/usuarios.py`
  - Consider adding `backend/app/schemas/usuario.py` if schemas grow beyond auth.py
- **Acceptance criteria**:
  - [x] `GET /usuarios` returns all users with assignments; requires admin; no `password_hash`.
  - [x] `POST /usuarios` creates a user from `{nombre, password, is_admin}`; hashes password; returns `409` on duplicate `nombre`.
  - [x] `PUT /usuarios/{id}` updates any subset of fields; re-hashes password if provided.
  - [x] `DELETE /usuarios/{id}` rejects self-deletion (`400`) and last-admin deletion (`400`); otherwise hard-deletes.
  - [x] `GET /usuarios/{id}/depositos` returns the user's assignments.
  - [x] `POST /usuarios/{id}/depositos` assigns `{deposito_id, role}`; returns `409` on duplicate.
  - [x] `DELETE /usuarios/{id}/depositos/{deposito_id}` removes the assignment.
- **Estimated lines**: 110
- **PR slice**: PR 1

---

## Phase 2 — Backend endpoint filtering (PR 2)

### 2.1 Add `deposito_ids` filtering to `estante_repository`

- **Skill / Context7**: `SQLite Database Expert`
- **Depends on**: 1.1
- **Files to create/modify**:
  - Modify `backend/app/repositories/estante_repository.py`
- **Acceptance criteria**:
  - [x] `list_estantes(..., deposito_ids: Optional[list[int]] = None)` adds `e.deposito_id IN (...)` filter when `deposito_ids` is a non-empty list; returns empty list when `deposito_ids == []`.
  - [x] `get_estante_by_id` includes `e.deposito_id` in the returned row.
- **Estimated lines**: 30
- **PR slice**: PR 2

### 2.2 Add `deposito_ids` filtering to `movimiento_repository`

- **Skill / Context7**: `SQLite Database Expert`
- **Depends on**: 1.2
- **Files to create/modify**:
  - Modify `backend/app/repositories/movimiento_repository.py`
- **Acceptance criteria**:
  - [x] `list_movimientos(..., deposito_ids)` joins through `ubicaciones -> estantes` and adds `e.deposito_id IN (...)` to both count and paginated queries.
  - [x] `export_movimientos_csv(..., deposito_ids)` applies the same filter.
  - [x] `get_movimiento_by_id` includes `e.deposito_id` in the returned row.
- **Estimated lines**: 50
- **PR slice**: PR 2

### 2.3 Return `deposito_id` from `ubicacion_repository` lookups

- **Skill / Context7**: `SQLite Database Expert`
- **Depends on**: 1.2
- **Files to create/modify**:
  - Modify `backend/app/repositories/ubicacion_repository.py`
- **Acceptance criteria**:
  - [x] `get_ubicacion_by_qr` returns `e.deposito_id` joined through `estantes`.
  - [x] `get_ubicacion_by_id` returns `e.deposito_id`.
- **Estimated lines**: 20
- **PR slice**: PR 2

### 2.4 Apply permission checks in `estantes.py` endpoints

- **Skill / Context7**: `fastapi-templates`
- **Depends on**: 1.7, 2.1
- **Files to create/modify**:
  - Modify `backend/app/api/v1/endpoints/estantes.py`
- **Acceptance criteria**:
  - [x] `GET /estantes` calls `get_deposito_ids_for_user` and passes the result to `list_estantes`.
  - [x] `GET /estantes/{id}` verifies depósito access after fetch; returns `403` if unauthorized.
  - [x] `POST /estantes` verifies `deposito_id` is accessible and user has `admin` role for that depósito (or global admin).
  - [x] `PUT /estantes/{id}` verifies depósito access.
  - [x] `DELETE /estantes/{id}` verifies depósito access.
  - [x] `GET /estantes/{id}/ubicaciones`, `/qrs`, `/qrs/print` verify depósito access.
  - [x] `GET /depositos` returns only accessible depósitos for non-admins; admins see all.
- **Estimated lines**: 60
- **PR slice**: PR 2

### 2.5 Apply permission checks in `movimientos.py` endpoints

- **Skill / Context7**: `fastapi-templates`
- **Depends on**: 1.7, 2.2
- **Files to create/modify**:
  - Modify `backend/app/api/v1/endpoints/movimientos.py`
- **Acceptance criteria**:
  - [x] `GET /movimientos` filters by user's `deposito_ids`.
  - [x] `GET /movimientos/export` applies the same filter.
  - [x] `GET /movimientos/{id}` verifies the movement's depósito is accessible.
  - [x] `POST /movimientos` loads ubicación (with `deposito_id`), checks `require_deposito_role(..., allowed_roles={"admin", "operator"})`, then creates the movement.
- **Estimated lines**: 50
- **PR slice**: PR 2

### 2.6 Apply depósito access check in `sectores.py` QR lookup

- **Skill / Context7**: `fastapi-templates`
- **Depends on**: 1.7, 2.3
- **Files to create/modify**:
  - Modify `backend/app/api/v1/endpoints/sectores.py`
- **Acceptance criteria**:
  - [x] `GET /sectores/lookup` calls `require_deposito_access` after locating the ubicación and returns `403` for unauthorized depósitos.
- **Estimated lines**: 15
- **PR slice**: PR 2

### 2.7 Apply permission checks in `ubicaciones.py` endpoints

- **Skill / Context7**: `fastapi-templates`
- **Depends on**: 1.7, 2.3
- **Files to create/modify**:
  - Modify `backend/app/api/v1/endpoints/ubicaciones.py`
- **Acceptance criteria**:
  - [x] `PUT /ubicaciones/{id}/assign` verifies depósito access and write role (`admin`/`operator`).
  - [x] `DELETE /ubicaciones/{id}/assign` verifies depósito access and write role.
  - [x] `GET /ubicaciones/{id}/qr.png` verifies depósito access.
- **Estimated lines**: 30
- **PR slice**: PR 2

### 2.8 Restrict product import to global admins

- **Skill / Context7**: `fastapi-templates`
- **Depends on**: 1.7
- **Files to create/modify**:
  - Modify `backend/app/api/v1/endpoints/import_.py`
- **Acceptance criteria**:
  - [x] `POST /import/excel` uses `require_admin`; non-admins receive `403`.
- **Estimated lines**: 10
- **PR slice**: PR 2

---

## Phase 3 — Frontend permission-aware UI (PR 3)

### 3.1 Extend session store with `is_admin` and `depositos`

- **Skill / Context7**: `sveltekit-structure`
- **Depends on**: —
- **Files to create/modify**:
  - Modify `frontend/src/lib/stores/session.ts`
- **Acceptance criteria**:
  - [ ] `UsuarioSession` includes `is_admin: boolean`.
  - [ ] `DepositoAssignment` type added with `deposito_id`, `nombre`, `role`.
  - [ ] `UserSession` includes `usuario`, `depositos`, `token`, `expires_at`.
  - [ ] `setSession` signature accepts `depositos` and stores them in the store/localStorage.
  - [ ] Existing login flow using the old signature is updated or shimmed.
- **Estimated lines**: 30
- **PR slice**: PR 3

### 3.2 Update API client for new auth contract and user management

- **Skill / Context7**: `sveltekit-structure`
- **Depends on**: 3.1
- **Files to create/modify**:
  - Modify `frontend/src/lib/api/client.ts`
- **Acceptance criteria**:
  - [ ] `login(nombre, password)` sends both fields.
  - [ ] `me()` returns `usuario` (with `is_admin`) and `depositos`.
  - [ ] Adds `listUsuarios`, `createUsuario`, `updateUsuario`, `deleteUsuario`.
  - [ ] Adds `listUsuarioDepositos`, `assignUsuarioDeposito`, `removeUsuarioDeposito`.
  - [ ] New TypeScript types for `Usuario`, `UsuarioCreate`, `UsuarioUpdate`, `DepositoAssignment`, `AssignDepositoRequest`.
- **Estimated lines**: 90
- **PR slice**: PR 3

### 3.3 Rewrite login page with username + password form

- **Skill / Context7**: `sveltekit-structure`, `Frontend Responsive Design Standards`
- **Depends on**: 3.2
- **Files to create/modify**:
  - Modify `frontend/src/routes/login/+page.svelte`
- **Acceptance criteria**:
  - [ ] Removes public user list and `listUsuarios` call from login flow.
  - [ ] Shows username and password inputs.
  - [ ] Calls `login(nombre, password)` and then `me()` to populate `depositos`.
  - [ ] Stores full session including `depositos` and redirects to `/`.
  - [ ] Displays backend error messages clearly.
  - [ ] Touch targets and inputs remain mobile-friendly (min 48px).
- **Estimated lines**: 70
- **PR slice**: PR 3

### 3.4 Update home page with conditional admin navigation

- **Skill / Context7**: `sveltekit-structure`, `Frontend Responsive Design Standards`
- **Depends on**: 3.1
- **Files to create/modify**:
  - Modify `frontend/src/routes/+page.svelte`
- **Acceptance criteria**:
  - [ ] `Gestionar usuarios` link visible only when `$sessionStore.usuario.is_admin`.
  - [ ] `Importar productos` link visible only when `$sessionStore.usuario.is_admin`.
  - [ ] `Escanear`, `Ver mapa`, `Historial`, and `Gestionar estantes` remain visible for all authenticated users.
- **Estimated lines**: 20
- **PR slice**: PR 3

### 3.5 Guard admin routes in layouts

- **Skill / Context7**: `sveltekit-structure`
- **Depends on**: 3.1
- **Files to create/modify**:
  - Modify `frontend/src/routes/+layout.svelte`
  - Modify `frontend/src/routes/admin/+layout.svelte`
- **Acceptance criteria**:
  - [ ] Root layout still redirects unauthenticated users to `/login`.
  - [ ] Admin layout (or root layout) redirects non-admin users away from `/admin/*` routes.
  - [ ] Adds `Usuarios` tab to admin navigation for admins.
- **Estimated lines**: 30
- **PR slice**: PR 3

### 3.6 Create `/admin/usuarios` user-management page

- **Skill / Context7**: `sveltekit-structure`, `Frontend Responsive Design Standards`
- **Depends on**: 3.2, 3.5
- **Files to create/modify**:
  - Create `frontend/src/routes/admin/usuarios/+page.svelte`
- **Acceptance criteria**:
  - [ ] Visible only to admins (client-side guard).
  - [ ] Lists users with `id`, `nombre`, `is_admin` badge, and depósito count.
  - [ ] Create-user form with `nombre`, `password`, `is_admin`.
  - [ ] Edit-user modal to change `nombre`, reset password, toggle `is_admin`.
  - [ ] Delete user with confirmation; blocks self-delete and last-admin-delete client-side.
  - [ ] Per-user depósito management: list assignments, add assignment (`deposito_id`, `role` dropdown), remove assignment.
  - [ ] Mobile-first layout, readable forms, touch-friendly controls.
- **Estimated lines**: 220
- **PR slice**: PR 3

### 3.7 Update scanner page for permission-aware location selector and 403 handling

- **Skill / Context7**: `sveltekit-structure`, `Frontend Responsive Design Standards`
- **Depends on**: 3.1, 3.2
- **Files to create/modify**:
  - Modify `frontend/src/routes/scanner/+page.svelte`
- **Acceptance criteria**:
  - [ ] Manual location modal's depósito dropdown shows only depósitos from `$sessionStore.depositos`.
  - [ ] Estante list is filtered by the selected accessible depósito.
  - [ ] QR scan handles `403` from `lookupSector` with red flash `"No tenés permiso para este depósito"` and does not anchor the location.
  - [ ] `createMovimiento` `403` shows a red flash.
  - [ ] Displays the names of the user's assigned depósitos near the status area.
- **Estimated lines**: 90
- **PR slice**: PR 3

### 3.8 Update estantes admin page to respect accessible depósitos

- **Skill / Context7**: `sveltekit-structure`, `Frontend Responsive Design Standards`
- **Depends on**: 3.1, 3.2
- **Files to create/modify**:
  - Modify `frontend/src/routes/admin/estantes/+page.svelte`
- **Acceptance criteria**:
  - [ ] Depósito filter dropdown shows only accessible depósitos (`$sessionStore.depositos`).
  - [ ] Create estante modal's depósito dropdown shows only accessible depósitos.
  - [ ] Default depósito for non-admins is the first accessible depósito, not hard-coded Depósito Central.
  - [ ] List remains filtered server-side; client does not leak unauthorized depósitos in dropdowns.
- **Estimated lines**: 40
- **PR slice**: PR 3

---

## Review Workload Forecast

- **Total estimated lines**: ~700–1,100 lines (backend ~400–600, frontend ~300–500).
- **Chained PRs recommended**: Yes.
- **400-line budget risk**: Medium. PR 3 is forecast at ~300–500 lines and could exceed the 400-line review budget depending on UI detail.
- **PRs that exceed 400 lines (if any)**: None are forecast to exceed 400 lines, but PR 3 is the closest to the threshold.
- **Decision needed before apply**: Yes — confirm the chained PR split, decide whether to truncate existing sessions on deploy, and confirm the temporary seeded passwords will be rotated before production use.

---

## Skill & Documentation Resolution

| Technology | Source | Used in tasks |
|------------|--------|---------------|
| FastAPI backend | `fastapi-templates` skill | 1.6, 1.7, 1.8, 1.10, 2.4, 2.5, 2.6, 2.7, 2.8 |
| SQLite schema/queries | `SQLite Database Expert` skill | 1.1, 1.2, 1.3, 1.4, 1.9, 2.1, 2.2, 2.3 |
| SvelteKit frontend | `sveltekit-structure` skill | 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8 |
| Responsive/mobile-first UI | `Frontend Responsive Design Standards` skill | 3.3, 3.4, 3.6, 3.7, 3.8 |
| bcrypt API | Context7 `/pyca/bcrypt` | 1.3, 1.5, 1.6 |
