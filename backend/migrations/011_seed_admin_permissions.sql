-- Migration 011: Set Admin password and permissions, remove seed operators, clear sessions.
-- Password for Admin is "Accesaniga@26" (bcrypt hashed).
UPDATE usuarios
SET password_hash = '$2b$12$ERLVL9jjMuVPnGonPU9cU.kjLCMkJU4zBjw1v/MoMlawsh.jy/VSC',
    is_admin = 1
WHERE nombre = 'Admin';

-- Operario 1 and Operario 2 were seed users; the admin will create new users via the UI.
DELETE FROM usuarios WHERE nombre IN ('Operario 1', 'Operario 2');

-- Force all existing sessions to re-login with the new auth system.
DELETE FROM sessions;
