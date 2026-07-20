# Coolify Deployment Guide

This guide covers deploying the **ASG Scanner** MVP to a self-hosted **Coolify** instance using the Dockerfiles in this repo.

## Architecture at a glance

```
Internet ──HTTPS──▶ Coolify reverse proxy (80/443)
                        │
                        ▼
                  ┌─────────────┐
                  │  frontend    │ nginx:alpine — serves the built SvelteKit SPA + proxies /api
                  │  port 80     │
                  └──────┬───────┘
                         │ /api/*  (internal Docker network)
                         ▼
                  ┌─────────────┐
                  │  backend     │ python:3.12-slim — FastAPI + uvicorn (2 workers)
                  │  port 8001   │
                  └──────┬──────┘
                         │ volume mounts
                  ┌──────┴──────────────────────┐
                  │                               │
            backend-data                backend-qr
            (SQLite DB)              (generated QR PNGs)
```

Two services, one shared network, no public port on the backend (only the frontend is exposed).

---

## Prerequisites

- A working Coolify instance (v4.x or later).
- A **private GitHub repo** (you mentioned this) with this codebase pushed.
- A **public domain** (or Coolify-provided subdomain) with DNS pointed at your Coolify server. The scanner **needs HTTPS** for the camera, so a domain + Let's Encrypt is mandatory.
- Your Coolify server must have Docker installed and at least **2 GB RAM free** (the backend image is ~400 MB, the frontend is ~30 MB, plus a small running footprint — the SQLite DB and QR cache are on disk).

---

## 1. Create the `SESSION_SECRET`

On your local machine (or anywhere with Python):

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the output. You'll need it as an environment variable in Coolify.

---

## 2. Push the repo to GitHub

```bash
git init   # only if not already a repo
git add .
git commit -m "feat: production deployment assets (Dockerfiles, nginx, compose)"
git remote add origin git@github.com:YOUR_ORG/asg-scanner.git
git push -u origin main
```

**Important:** the repo is **private**. In Coolify, when you add the Git source, use a **GitHub App** or a **Deploy Key** with read access to private repos. See Coolify docs → "Private GitHub Repository".

---

## 3. Create the backend service in Coolify

### 3.1. New Resource → Application

| Field | Value |
|-------|-------|
| Type | Application (Docker Image) |
| Source | Private Repository (GitHub) |
| Repository | `YOUR_ORG/asg-scanner` |
| Branch | `main` |
| **Build Pack** | **Dockerfile** |
| **Dockerfile Location** | `backend/Dockerfile` |
| Port | `8001` (internal — don't expose publicly) |
| Healthcheck Path | `/api/v1/health` |

### 3.2. Domain for the backend

**Don't assign a public domain to the backend.** The frontend will reach it over the internal Docker network. You only need a public domain for the frontend.

If Coolify forces a domain, use a dummy internal one like `backend.internal` and the frontend will resolve it via Coolify's service discovery (Coolify injects the service name as a hostname in the same project).

### 3.3. Environment variables (backend)

| Key | Value | Notes |
|-----|-------|-------|
| `DB_PATH` | `/app/data/app.db` | Persists via volume |
| `QR_CACHE_DIR` | `/app/qr_cache/` | Persists via volume |
| `QR_DEFAULT_SIZE` | `200` | Pixels |
| `SESSION_SECRET` | *(the token from step 1)* | **Required** — change from default! |
| `CORS_ORIGINS` | `https://your-frontend-domain.example.com` | Must match the frontend's public URL exactly. You can add multiple comma-separated. |

### 3.4. Persistent volumes (backend)

| Mount | Container path | Purpose |
|-------|---------------|---------|
| `escanner-backend-data` | `/app/data` | SQLite file (`app.db`) |
| `escanner-backend-qr` | `/app/qr_cache` | Cached QR PNGs |

In Coolify → "Storages" tab, add these two named volumes with the paths above.

> **Why volumes?** The QR cache is regenerated on first request but the SQLite DB holds every movimiento, every session, every user. Losing it means re-importing all 1862 products from the Excel and losing the audit trail.

---

## 4. Create the frontend service in Coolify

### 4.1. New Resource → Application

| Field | Value |
|-------|-------|
| Type | Application (Docker Image) |
| Source | Same private repository |
| Branch | `main` |
| **Build Pack** | **Dockerfile** |
| **Dockerfile Location** | `frontend/Dockerfile` |
| Port | `80` (nginx serves on 80) |
| Healthcheck Path | `/` |

### 4.2. Public domain (REQUIRED)

Assign your domain here — e.g. `scan.yourdomain.com`. Coolify will request a Let's Encrypt cert automatically.

> **Why HTTPS is non-negotiable:** `getUserMedia()` (the browser camera API) is only served over HTTPS or `localhost`. Without HTTPS, the scanner silently fails on every phone.

### 4.3. No environment variables needed

The frontend is **pure static** (SvelteKit `adapter-static` produces a SPA). All API calls go to relative `/api/*` paths, which nginx proxies to the backend service. **No `VITE_API_BASE_URL` to set** — the Vite proxy is dev-only; in production the browser hits the same origin and nginx routes `/api/*` internally.

### 4.4. No volumes needed

The frontend is fully static. Deploys overwrite the previous image.

---

## 5. First deploy

1. Click **Deploy** on the frontend service first.
2. Wait until it's healthy (the healthcheck hits `wget /`).
3. Click **Deploy** on the backend service.
4. The frontend will start failing healthchecks until the backend is up — that's fine, it retries.
5. Once the backend is up, hit `https://your-frontend-domain/` in a browser.

### Smoke test the deployment

```bash
# From any machine with curl
curl -I https://your-frontend-domain/
# Should return 200 with the Coolify-served HTML

# The frontend's nginx proxies /api to the backend
curl -I https://your-frontend-domain/api/v1/health
# Should return 200 OK {"status":"ok"}
```

---

## 6. First-time setup after deploy

1. **Open the app** on your phone (HTTPS, so the camera works).
2. **Log in as Admin** with password `Accesaniga@26`.
3. **Change the Admin password** immediately: `/admin/usuarios` → Admin → edit → new password.
4. **Import the product catalog**: `/admin/import` → upload `Productos Sotano.xlsx`.
5. **Create the warehouse structure** (optional — the import works on the seeded "Depósito Central"):
   - `/admin/depositos` → create any additional warehouses
   - `/admin/estantes` → create shelves (Pasillo 1, Estante 1, etc.)
6. **Create operator users**: `/admin/usuarios` → create user → assign deposito + role (operator or viewer).

---

## 7. Updating the deployment

When you push new commits to `main`:

1. Coolify's webhook (if configured) auto-rebuilds. Otherwise click **Redeploy** in the Coolify UI.
2. Rebuilds are incremental — only the layer that changed re-builds (Docker layer cache).
3. After a frontend redeploy, users see the new version on next page load (the new image replaces the old).
4. After a backend redeploy, there's a brief downtime (~5 s) while the container restarts. The SQLite DB and QR cache survive via volumes.

If you want **zero-downtime** deploys, run **two backend replicas** behind a reverse proxy — but for a 1–5 user internal tool, the ~5 s restart is fine.

---

## 8. Backups

**Critical:** back up the `escanner-backend-data` volume regularly — it contains the entire database.

In Coolify, you can:
- Use a **scheduled backup** (Coolify Pro / self-hosted) to snapshot the volume.
- OR use a cron job inside the backend container:
  ```cron
  0 3 * * * cp /app/data/app.db /app/data/app.db.$(date +\%F).bak && find /app/data -name "*.bak" -mtime +30 -delete
  ```

To restore: stop the backend container, `cp` the backup file into the volume mount, restart.

---

## 9. Common gotchas

| Symptom | Cause | Fix |
|---------|-------|-----|
| Login works on desktop but scanner says "Permiso de cámara denegado" on phone | You accessed the app over HTTP (not HTTPS) or mixed-content | Ensure the **public** domain has a valid Let's Encrypt cert. Coolify auto-provisions this — check the "SSL/TLS" tab. |
| "Error de conexión" everywhere | Frontend is up but backend is down or the nginx `proxy_pass` can't reach the backend service | Check that the backend service name in nginx.conf (`backend:8001`) matches the Coolify service name. Coolify service DNS is automatic within a project. |
| "500 Internal Server Error" on the first POST after a fresh deploy | The backend volume wasn't mounted — the app.db was created inside the container and is lost on restart | Mount the `escanner-backend-data` volume to `/app/data` in Coolify. |
| "Session invalid" after every redeploy | `SESSION_SECRET` is being regenerated by Coolify each time | Set it as a fixed env var (not a generated one) in Coolify. |
| Backend container restarts every 30 s | The healthcheck is failing | Hit `/api/v1/health` from inside the container (`docker exec ... curl http://127.0.0.1:8001/api/v1/health`). If it 200s but Coolify marks it unhealthy, adjust the healthcheck `start_period` in `docker-compose.yml` (already 15 s, bump to 30 s if your DB has 1862 products and the migration takes a moment). |

---

## 10. Environment reference (single source of truth)

| Variable | Where | Default in repo | Production value |
|----------|-------|-----------------|------------------|
| `DB_PATH` | backend | `./app.db` | `/app/data/app.db` |
| `QR_CACHE_DIR` | backend | `./qr_cache/` | `/app/qr_cache/` |
| `QR_DEFAULT_SIZE` | backend | `200` | `200` |
| `SESSION_SECRET` | backend | `changeme` | **MUST be changed** — generate with `secrets.token_urlsafe(32)` |
| `CORS_ORIGINS` | backend | `http://localhost:5173` | `https://your-frontend-domain.example.com` |

The frontend has **no env vars at runtime** — it's a pure static SPA + nginx.

---

## Quick reference: file map

| File | Role |
|------|------|
| `backend/Dockerfile` | Multi-stage Python (builder + slim runtime, non-root user) |
| `backend/.dockerignore` | Excludes caches, tests, IDE files from the build context |
| `frontend/Dockerfile` | Multi-stage Node (builder + nginx:alpine runtime) |
| `frontend/nginx.conf` | SPA fallback + `/api` proxy to backend + security headers + gzip |
| `frontend/.dockerignore` | Excludes node_modules, build output, env files |
| `.dockerignore` (root) | Excludes the local SQLite DB, QR cache, the Excel file, docs |
| `docker-compose.yml` | Local stack mirror — same env vars, same volumes, same healthchecks |

The local `docker-compose.yml` is **deliberately a mirror** of the Coolify setup. If it works locally with `docker compose up`, it will work on Coolify.
