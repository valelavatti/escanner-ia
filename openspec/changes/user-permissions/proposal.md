# Proposal: User Permissions

## Intent

Replace the current name-only login with username + password authentication and enforce depot-based access control, so operators only see and act on data from the warehouses they are assigned to.

## Scope

### In Scope
- Schema migration: add `password_hash`, `is_admin` to `usuarios`; create `usuario_deposito` junction table.
- Data migration: seed existing users (Admin → global admin; Operario 1/2 → operators on Depósito Central).
- Replace name-only login with bcrypt username + password login; keep existing session token system.
- Admin user-management CRUD: create/edit/delete users, set passwords, assign depósitos with roles (`admin`/`operator`/`viewer`).
- Permission enforcement: all list endpoints filter by accessible depósitos; scanner `/sectores/lookup` checks depósito access.
- Frontend: new login page with password, `/admin/usuarios` page, permission-aware navigation hiding admin links for non-admins.
- Password security: bcrypt hashing, never return `password_hash` in responses.

### Out of Scope
- Password reset via email, multi-tenant `organizacion_id`, custom roles.
- Audit trail for user-management actions, self-service password change.
- Two-factor authentication, configurable session timeout.

## Capabilities

### New Capabilities
- `user-authentication`: bcrypt username/password login; replaces name-only selection; session token contract unchanged.
- `user-management`: admin-only CRUD for users, password setting, and depósito/role assignment.
- `deposito-permissions`: `usuario_deposito` junction table, repository-level filtering, and endpoint access guards.

### Modified Capabilities
- `scanner`: `/sectores/lookup` must validate that the scanned ubicación's depósito is accessible to the current user.

## Approach

Use the approved exploration model: bcrypt for passwords, a `usuario_deposito` junction with roles, and a global `is_admin` flag. Centralize permission helpers in `deps.py` (`require_admin`, `get_deposito_ids_for_user`, `require_deposito_access`). Repositories accept an optional `deposito_ids` list (`None` for global admins). All list/filter endpoints apply the depósito filter; the scanner rejects QR lookups outside the user's depósitos.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/migrations/` | New | Migration adding columns, junction table, and seed data. |
| `backend/app/api/v1/deps.py` | Modified | Add admin and depósito access helpers; extend `get_current_user`. |
| `backend/app/api/v1/endpoints/auth.py` | Modified | Switch login to username + password with bcrypt verification. |
| `backend/app/api/v1/endpoints/usuarios.py` | Modified | Protect with admin guard; add CRUD endpoints. |
| `backend/app/repositories/*` | Modified | Accept `deposito_ids` filter on list operations. |
| `backend/app/api/v1/endpoints/sectores.py` | Modified | Enforce depósito access on QR lookup. |
| `frontend/src/routes/login/` | Modified | New username/password form; remove public user list. |
| `frontend/src/routes/admin/usuarios/` | New | User-management UI. |
| `frontend/src/routes/+layout.svelte` | Modified | Hide admin navigation for non-admin users. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Permission leak from incomplete endpoint filtering | Medium | Centralize filtering in repositories; audit every list endpoint during implementation. |
| Existing sessions remain valid after deploy | Low | Optionally clear `sessions` table on deploy; tokens expire within 8 hours. |
| Operator UX friction from password login | Medium | Admin sets passwords before deploy; brief staff training. |
| Scanner anchors to unauthorized depósito | Low | Enforce depósito access in `/sectores/lookup`. |
| Zero test coverage for permission logic | Medium | Add minimal integration tests for auth and permission guards. |

## Rollback Plan

1. Revert the migration (`password_hash` and `is_admin` are nullable; `usuario_deposito` can be dropped).
2. Restore the previous name-only login code.
3. Existing productos, estantes, ubicaciones, and movimientos data remain untouched.

## Dependencies

- `bcrypt` Python library for password hashing.

## Success Criteria

- [ ] Admin can log in with username + password and manage users/roles.
- [ ] Operator/viewer only sees estantes, ubicaciones, movimientos, and scanner results from assigned depósitos.
- [ ] Non-admin users cannot access `/usuarios/*` endpoints or admin UI.
- [ ] Password hashes are never exposed in API responses.
- [ ] Existing product data and audit trail remain intact.
