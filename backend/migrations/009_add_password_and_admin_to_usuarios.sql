-- Migration 009: Add password hash and global admin flag to usuarios.
ALTER TABLE usuarios ADD COLUMN password_hash TEXT;
ALTER TABLE usuarios ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0;
