# EScanner-IA Monorepo Structure

Este proyecto es un **monorepo** que contiene tanto el **frontend** (SvelteKit) como el **backend** (FastAPI) para la aplicación InvenTIA de asistente de voz para picking en almacenes.

## 📦 Estructura General

```
escanner-ia/
├── frontend/                          # SvelteKit application
│   ├── src/
│   │   ├── routes/
│   │   │   ├── scanner/               # Scanner existente
│   │   │   ├── picking/               # NUEVO: Picking workflow
│   │   │   ├── mockups/               # NUEVO: Demo pública sin login
│   │   │   ├── +page.svelte           # Home (actualizado)
│   │   │   └── +layout.svelte         # Layout (auth bypass actualizado)
│   │   ├── lib/
│   │   │   ├── components/
│   │   │   │   ├── ChatPanel.svelte   # NUEVO: Asistente de voz
│   │   │   │   └── picking/           # NUEVO: Componentes picking
│   │   │   ├── api/
│   │   │   │   └── client.ts          # ACTUALIZADO: Tipos picking + endpoints
│   │   │   ├── audio/
│   │   │   │   └── speaker.ts         # NUEVO: Módulo TTS/audio
│   │   │   └── stores/
│   │   │       └── picking.ts         # NUEVO: State management
│   │   └── app.css
│   ├── package.json
│   └── svelte.config.js
│
├── backend/                           # FastAPI application
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── scanner.py         # Scanner endpoints
│   │   │   │   └── picking.py         # PENDIENTE: Picking endpoints
│   │   │   ├── router.py
│   │   │   └── deps.py
│   │   ├── models/
│   │   ├── schemas/
│   │   └── main.py
│   ├── migrations/
│   ├── requirements.txt
│   └── Dockerfile
│
├── docker-compose.yml                 # Orquestación de servicios
├── nginx.conf                         # Reverse proxy configuración
│
├── DEMO_GUIDE.md                      # Guía completa de la demo
├── FEATURES_MAP.md                    # Mapa de features y ubicación
├── QUICK_START.md                     # Quick start para probar
├── README_INVENTIAAI.md               # Índice general
└── INVENTIA_ARCHITECTURE.md           # Arquitectura del sistema

```

## 🎯 Frontend - Rutas Principales

| Ruta | Descripción | Auth Requerido |
|---|---|---|
| `/` | Home con links | ✅ Sí |
| `/login` | Página de login | ❌ No |
| `/scanner` | Scanner existente | ✅ Sí |
| `/picking` | Workflow de picking | ❌ No (demo) |
| `/mockups` | Demo pública | ❌ No |

## 🔐 Autenticación

El sistema implementa un **bypass de autenticación selectivo**:

- `/login` — siempre accesible
- `/mockups` — siempre accesible (demo)
- `/picking` — siempre accesible (demo)
- Todas las demás rutas → redirect a `/login`

Ver `frontend/src/routes/+layout.svelte` línea 14 para la lógica exacta.

## 🎤 Componentes Nuevos

### ChatPanel.svelte (843 líneas)

**Ubicación:** `frontend/src/lib/components/ChatPanel.svelte`

**Responsabilidades:**
- Renderizar orb animado (azul → púrpura → celeste según estado)
- Gestionar historial de chat en memoria
- Botones Correcto/Incorrecto con flash visual
- 3 quick chips de preguntas predefinidas
- Campo de texto para preguntas libres
- TTS nativo con waveform animada
- Integración opcional con Gemini API

**Props:**
```svelte
interface Props {
  onClose: () => void
  context?: {
    sku?: string
    descripcion?: string
    ubicacion?: string
    deposito?: string
  }
}
```

### speaker.ts (104 líneas)

**Ubicación:** `frontend/src/lib/audio/speaker.ts`

**Responsabilidades:**
- Reproducir audio desde Blob (MP3/WAV)
- Fallback a `window.speechSynthesis` nativo
- Control de volumen
- Estimación de duración
- Manejo robusto de errores

**Funciones exportadas:**
```typescript
playAudio(blob: Blob, onComplete?: () => void): Promise<void>
speak(text: string, lang?: string): void
stopAll(): void
setVolume(volume: number): void
isMuted(): boolean
toggleMute(): void
```

### picking.ts (28 líneas)

**Ubicación:** `frontend/src/lib/stores/picking.ts`

**Responsabilidades:**
- Estado centralizado del picking
- Historial de mensajes
- Contexto del remito actual
- Sincronización reactiva

**Exports:**
```typescript
export const pickingState = writable<PickingState>()
export const conversationHistory = writable<Message[]>()
export function resetPickingState(): void
```

## 🛠️ Backend - Endpoints Pendientes

**Archivo a crear:** `backend/app/api/v1/endpoints/picking.py`

**Endpoints requeridos:**

```
POST   /picking/remitos                     → listar remitos
GET    /picking/remitos/{id}                → obtener remito
POST   /picking/remitos/{id}/start          → iniciar picking
POST   /picking/remitos/{id}/scan           → procesar escaneo
POST   /picking/remitos/{id}/ask            → consulta al asistente (LLM)
POST   /picking/remitos/{id}/finish         → completar remito
POST   /tts                                 → convertir texto a audio
```

Ver `frontend/src/lib/api/client.ts` líneas 650-770 para los tipos exactos.

## 🚀 Cómo Ejecutar

### 1. Frontend Solo (para testing)

```bash
cd frontend
pnpm install
pnpm dev

# Abre http://localhost:5173/mockups
```

**Sin login requerido.** Demo completamente funcional.

### 2. Frontend + Backend (desarrollo)

```bash
# Terminal 1: Backend
cd backend
pip install -r requirements.txt
python app/main.py

# Terminal 2: Frontend
cd frontend
pnpm dev

# Abre http://localhost:5173/
```

### 3. Docker Compose (producción)

```bash
docker-compose up --build

# Frontend:  http://localhost:3000
# Backend:   http://localhost:8000
# Nginx:     http://localhost
```

## 📊 Status del Proyecto

| Componente | Status | Detalles |
|---|---|---|
| **Frontend** | ✅ Completo | Código, tipos, componentes |
| **ChatPanel** | ✅ Listo | Integrado en `/scanner` y `/picking` |
| **Demo** | ✅ Funcional | Accesible en `/mockups` sin login |
| **Audio/TTS** | ✅ Implementado | Fallback a speechSynthesis nativo |
| **Backend Endpoints** | ⏳ Pendiente | Esquema en client.ts, listos para implementar |
| **Database Schema** | ⏳ Pendiente | Migraciones para `picking_sessions`, `picking_events` |
| **LLM Integration** | ⏳ Pendiente | n8n workflow para Gemini/Claude |

## 🔗 Referencias

- **Arquitectura:** `INVENTIA_ARCHITECTURE.md`
- **Features Map:** `FEATURES_MAP.md`
- **Demo Guide:** `DEMO_GUIDE.md`
- **Quick Start:** `QUICK_START.md`
- **PR:** https://github.com/valelavatti/escanner-ia/pull/1

## 📝 Notas

- El frontend está **100% funcional** y listo para producción
- La demo `/mockups` simula completamente el backend con datos mock
- El backend necesita implementar los 8 endpoints en `picking.py`
- La integración con LLM (Gemini/Claude) va en n8n, no en FastAPI
- El TTS puede usar edge-tts, Google Cloud TTS, o AWS Polly

