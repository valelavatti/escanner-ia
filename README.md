# ASG Scanner

Aplicación interna de control de stock para Accesaniga.

## Stack

- **Backend**: FastAPI + Python 3.11+
- **Frontend**: SvelteKit + Vite + PWA
- **Base de datos**: SQLite (WAL mode)

## Cómo ejecutar

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

El backend expone la API en `http://localhost:8000` y el health check en `GET /api/v1/health`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

La aplicación estará disponible en `http://localhost:5173`.

### Variables de entorno

Copiar `backend/.env.example` a `backend/.env` y ajustar según el entorno.
