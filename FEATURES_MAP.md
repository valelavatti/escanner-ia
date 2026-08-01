# InvenTIA — Mapa de Features

## 🗂️ Estructura del Proyecto

```
frontend/src/
├── routes/
│   ├── +page.svelte                    # Home (login redirect)
│   ├── +layout.svelte                  # Layout global (auth bypass para /mockups y /picking)
│   ├── login/
│   │   └── +page.svelte                # Formulario de login
│   ├── scanner/
│   │   ├── +page.svelte                # 📍 SCANNER CON ASISTENTE IA INTEGRADO
│   │   └── ...
│   ├── mockups/
│   │   └── +page.svelte                # 📍 DEMO PÚBLICA 100% FUNCIONAL (sin login)
│   ├── picking/
│   │   ├── +page.svelte                # Picking con remitos (futuro con backend)
│   │   ├── +page.ts                    # Loader (ssr = false)
│   │   └── ...
│   └── ...
│
├── lib/
│   ├── components/
│   │   ├── ChatPanel.svelte            # 📍 ASISTENTE DE VOZ PREMIUM
│   │   ├── Scanner.svelte              # Component de cámara
│   │   ├── ProductCard.svelte          # Card de producto
│   │   ├── picking/
│   │   │   ├── ScanFlash.svelte        # Animación verde/rojo de escaneo
│   │   │   ├── RemitoItemList.svelte   # Lista de items del remito
│   │   │   ├── RoutePanel.svelte       # Panel de ruta optimizada
│   │   │   └── TalkButton.svelte       # Botón inteligente de voz (preguntas + STT)
│   │   └── ...
│   │
│   ├── audio/
│   │   └── speaker.ts                  # 📍 MÓDULO DE AUDIO/TTS
│   │
│   ├── stores/
│   │   ├── session.ts                  # Estado de sesión del usuario
│   │   ├── scanner.ts                  # Estado del scanner actual
│   │   └── picking.ts                  # 📍 PICKING STATE (tipos para backend)
│   │
│   ├── api/
│   │   └── client.ts                   # 📍 TIPOS Y ENDPOINTS (Pydantic-compatible)
│   │
│   └── ...
│
└── app.css                             # Estilos globales
```

---

## 🎯 Donde Está Cada Feature

### 1. **Asistente de Voz (Chat IA)**
**Archivo**: `src/lib/components/ChatPanel.svelte`

**Ubicación en UI**:
- `/scanner` → Botón "Asistente IA" en los controles → abre drawer con ChatPanel
- `/mockups` → Frame derecho del teléfono (demo pública)

**Features**:
- Orb animado (azul → púrpura pensando → celeste hablando)
- Botones Correcto/Incorrecto con flash en pantalla
- Historial de conversación con timestamps
- TTS nativo + waveform animada
- 3 quick chips de preguntas rápidas
- Campo de texto libre
- Badge de status (pensando/escaneando correcto/incorrecto)

**Interactivo en**: `/mockups` (sin login)

---

### 2. **Audio/TTS Nativo**
**Archivo**: `src/lib/audio/speaker.ts`

**Features**:
- Unlock automático en primer click del usuario (CORS requirement)
- Reproducción de Blob (MP3/WAV)
- Fallback a `window.speechSynthesis` si no hay MP3
- Control de volumen
- Estimación de duración de speech

**Usado por**: `ChatPanel.svelte` (línea ~450)

---

### 3. **Scanner con Integración IA**
**Archivo**: `src/routes/scanner/+page.svelte`

**Features actuales**:
- Captura de código QR en tiempo real
- Mostrar producto después del escaneo
- Cambiar ubicación del almacén
- ✨ **NUEVO**: Botón "Asistente IA" que abre ChatPanel
- ✨ **NUEVO**: Context reactivo (SKU, ubicación) pasado al asistente

**Datos reactivos derivados**:
```typescript
let chatContext = $derived({
  sku: scannedProduct?.sku,
  descripcion: scannedProduct?.descripcion,
  ubicacion: `${$anchoredLocation.estante_nombre} F${fila}-C${columna}`,
  deposito: deposito_nombre
});
```

**Acceso**: `/scanner` (requiere login)

---

### 4. **Demo Pública 100% Funcional**
**Archivo**: `src/routes/mockups/+page.svelte`

**Features**:
- Frame de teléfono realista con Dynamic Island
- Simulación de scanner (línea verde animada)
- SKU + ubicación mostrados en el teléfono
- Panel de IA derecha con todo integrado
- Flujos completos: Correcto → verde, Incorrecto → rojo
- Respuestas mock semánticas
- **Sin backend requerido**
- **Sin Gemini API key requerida** (funciona offline)

**Acceso**: `/mockups` (público, sin login)

---

### 5. **Picking Flow (Fase 2 — Backend)**
**Archivos**: 
- `src/routes/picking/+page.svelte`
- `src/routes/picking/+page.ts`
- `src/lib/components/picking/*.svelte`

**Propósito**: Futura integración con backend cuando endpoints de picking estén listos.

**Componentes**:
- `ScanFlash.svelte` → Flash de resultado (verde/rojo)
- `RemitoItemList.svelte` → Checklist de items
- `RoutePanel.svelte` → Ruta optimizada al siguiente item
- `TalkButton.svelte` → Chat con preguntas rápidas

**Estado**: Esqueleto, esperando backend

---

### 6. **Tipos y API Client**
**Archivo**: `src/lib/api/client.ts`

**Tipos agregados**:
```typescript
type PickingOutcome = 'ancla' | 'correcto' | 'fuera_de_orden' | ...
interface RemitoState { remito_id, items[], ruta, ... }
interface ScanResponse { outcome, accepted, display_text, speech_text, ... }
interface AskResponse { respuesta, fuente }
```

**Endpoints agregados**:
```typescript
listPickingRemitos()              // GET /picking/remitos
getPickingRemito(id)              // GET /picking/remitos/{id}
startPickingRemito(id)            // POST /picking/remitos/{id}/start
scanPickingCode(id, code, clientEventId)  // POST /picking/remitos/{id}/scan
finishPickingRemito(id)           // POST /picking/remitos/{id}/finish
askPickingAssistant(id, pregunta) // POST /picking/remitos/{id}/ask
getTtsAudio(text)                 // POST /tts → Blob
```

**Estado**: Tipos definidos, endpoints listos para backend

---

### 7. **Picking Store (State Management)**
**Archivo**: `src/lib/stores/picking.ts`

**State**:
```typescript
export const pickedRemito = writable<RemitoState | null>(null);
export const currentRoute = derived(pickedRemito, ...);
export const nextStop = derived(pickedRemito, ...);
```

**Propósito**: Sincronizar estado del remito en tiempo real

---

## 📊 Matriz de Integración

| Feature | Implementado | Demo Funcional | Backend Ready | Notas |
|---|---|---|---|---|
| Asistente de Voz | ✅ | ✅ `/mockups` | ⏳ Endpoints listos | Orb + botones + TTS |
| Chat con IA | ✅ | ✅ Mock responses | ⏳ Necesita n8n | Responde preguntas |
| Scanner integrado | ✅ | ✅ | ✅ | Botón "Asistente IA" |
| ScanFlash (verde/rojo) | ✅ | ✅ `/mockups` | ⏳ Picking endpoints | Animación del resultado |
| TTS Nativo | ✅ | ✅ | ✅ | Usa `speechSynthesis` |
| Quick questions | ✅ | ✅ | ⏳ Respuestas reales | Mock responses funcional |
| Picking flow completo | ⏳ Esqueleto | ❌ | ❌ | Depende del backend |

---

## 🚀 Para Ver la Demo Ahora

```bash
# En desarrollo
npm run dev  # En frontend/

# Ir a
http://localhost:5173/mockups
```

**Sin login, sin backend, completamente funcional.**

---

## 🔌 Para Conectar con Backend

1. Implementar endpoints en `backend/app/api/v1/endpoints/picking.py`:
   - `GET /picking/remitos`
   - `POST /picking/remitos/{id}/start`
   - `POST /picking/remitos/{id}/scan`
   - `POST /picking/remitos/{id}/ask` (llamar n8n)
   - `POST /tts` (edge-tts)

2. En `ChatPanel.svelte` (línea ~620), descomentar:
   ```typescript
   // const response = await askPickingAssistant(remitoId, userMessage);
   ```

3. Configurar en `.env`:
   ```
   VITE_GEMINI_API_KEY=sk-...  # Opcional, para Gemini en tiempo real
   ```

---

## 📝 Responsabilidades

| Componente | Quién lo construye |
|---|---|
| Frontend (todo) | ✅ Completado |
| Tipos Pydantic | ✅ Definidas en `client.ts` |
| Endpoints `/picking/*` | ⏳ Backend team |
| n8n workflow para chat | ⏳ Backend team |
| Edge-TTS o similar | ⏳ Backend team |

