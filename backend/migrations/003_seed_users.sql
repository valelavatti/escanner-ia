-- ============================================================
-- Seed default usuarios (Work Unit 2)
-- Only inserts when the table is empty so migrations stay idempotent.
-- ============================================================
INSERT INTO usuarios (nombre)
SELECT nombre FROM (
    SELECT 'Admin' AS nombre
    UNION ALL SELECT 'Operario 1'
    UNION ALL SELECT 'Operario 2'
) WHERE (SELECT COUNT(*) FROM usuarios) = 0;
