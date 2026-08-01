# InvenTIA — Demo Guide

## ✅ Estado Actual

La feature de **Asistente de Voz con IA** está completamente implementada en el frontend, accesible sin login para demo.

---

## 🎯 Cómo Acceder a la Demo

### URL Pública (sin login requerido):
```
http://localhost:5173/mockups
```

O si está en producción:
```
https://tu-dominio.com/mockups
```

**No necesita credenciales. Es completamente funcional sin backend.**

---

## 📂 Estructura de Archivos

### Ubicación de la Feature de Voz:

| Archivo | Ubicación | Propósito |
|---|---|---|
| **ChatPanel.svelte** | `frontend/src/lib/components/` | Componente de IA con botones Correcto/Incorrecto |
| **Speaker.ts** | `frontend/src/lib/audio/` | Módulo de audio/TTS nativo |
| **Picking store** | `frontend/src/lib/stores/picking.ts` | Estado del remito (para integración futura) |
| **API types** | `frontend/src/lib/api/client.ts` | Tipos Pydantic + endpoints picking |
| **Demo interactiva** | `frontend/src/routes/mockups/+page.svelte` | Página pública 100% funcional |
| **Scanner integrado** | `frontend/src/routes/scanner/+page.svelte` | Botón "Asistente IA" → abre ChatPanel |
| **Picking flow** | `frontend/src/routes/picking/+page.svelte` | Para integración con backend (FASE 2) |

---

## 🎬 Flujos Disponibles en `/mockups`

### 1️⃣ **Estado Inicial**
- Frame de teléfono con simulación de scanner (línea verde animada)
- SKU activo mostrado: `LPT-0042-A` (Laptop Acer)
- Ubicación: `Estante B3 · F2-C4`
- Orb azul de IA con icono de micrófono
- Badge "DEMO" en la esquina superior derecha

### 2️⃣ **Flujo "Correcto" (Escaneo Exitoso)**
1. Haz clic en el botón **"✓ Correcto"**
2. El frame del teléfono muestra:
   - Border verde brillante (500ms)
   - Checkmark animado al centro
3. La IA responde:
   - Badge verde: "✓ Escaneo correcto"
   - Mensaje: "Escaneo ok. Stock actualizado. Próximo: SKU MON-1190-C en EST-C1 F1-C2."
   - Orb indica TTS con animación de onda sonora

### 3️⃣ **Flujo "Incorrecto" (Mala Colocación)**
1. Haz clic en el botón **"✗ Incorrecto"**
2. El frame del teléfono muestra:
   - Border rojo oscuro (2.2s)
   - X roja al centro
   - Orb cambia a púrpura (pensando)
3. La IA responde:
   - Badge rojo: "⊠ Escaneo incorrecto"
   - Mensaje: "Producto equivocado. Comprobá que el código de barras no esté dañado y que el lector haya capturado el QR completo."

### 4️⃣ **Preguntas Rápidas**
Debajo del campo de texto hay 3 chips pre-cargados:
- **"¿Qué me falta?"** → respuesta sobre items pendientes del remito
- **"¿Dónde está el siguiente?"** → ubicación del próximo producto
- **"¿Cuánto stock hay?"** → disponibilidad en el almacén

Haz clic en cualquiera para ver la respuesta del asistente.

### 5️⃣ **Campo de Texto Libre**
- Escribe cualquier pregunta en español
- El asistente responde:
  - **Con `VITE_GEMINI_API_KEY` configurada**: usa Gemini 2.0 Flash en tiempo real
  - **Sin API key**: responde con un banco de respuestas mock semánticas

### 6️⃣ **Control de Audio**
- Icono de micrófono en el header del orb (esquina superior derecha)
- Haz clic para mutearse (TTS silenciado)
- El toggle cambia el color del icono

---

## 🎨 Elementos Visuales Explicados

### El Orb (Centro derecha del panel)
- **Azul sólido**: listo y esperando input
- **Púrpura con 3 puntos**: pensando (AI procesando)
- **Celeste con waveform**: hablando (TTS activo)

### Los Botones de Outcome
- **"Correcto"** (verde): registro exitoso del escaneo
- **"Incorrecto"** (rojo): error o mala colocación
- Cuando haces clic, disparan una animación en el teléfono + respuesta del asistente

### Bubbles del Chat
- **Verde oscuro**: confirmación de escaneo correcto
- **Rojo oscuro**: error o escaneo incorrecto
- **Azul**: pregunta del operario
- **Gris**: respuesta del asistente

### Timestamps
- Cada mensaje lleva hora (formato 24h)
- Ejemplo: `05:22 p.m.`

---

## 🔧 Integración en `/scanner`

El asistente **ya está integrado** en la pantalla del scanner. Para usarlo:

1. Accede a `/scanner` (requiere login)
2. Busca el botón **"Asistente IA"** (violeta, ocupa columna completa)
3. Haz clic → se abre el ChatPanel
4. Mismo flujo que en `/mockups`, pero contexto reactivo del scanner actual

---

## 🚀 Próximas Fases (Backend Required)

### Fase 2: Integración Real
Una vez el backend esté listo, el flujo será:

1. **POST `/picking/remitos/{id}/scan`**
   - Envía: `raw_code` + `client_event_id`
   - Recibe: `ScanResponse` con `outcome` (correcto/incorrecto/etc)
   - El frontend renderiza el resultado

2. **POST `/picking/remitos/{id}/ask`**
   - Envía: `pregunta` en español
   - Recibe: respuesta del asistente desde n8n + LLM

3. **GET `/tts` (audio blob)**
   - Envía: texto a vocalizar
   - Recibe: MP3 para reproducción inmediata

### Cambios Necesarios:
- Remover `// DEMO` comments en ChatPanel.svelte
- Desactivar banco de respuestas mock
- Conectar a `/picking/*` endpoints reales
- Configurar `VITE_GEMINI_API_KEY` para Gemini en tiempo real

---

## 🧪 Testing Checklist

- [x] Demo accesible sin login en `/mockups`
- [x] Botón "Correcto" → flash verde + respuesta
- [x] Botón "Incorrecto" → flash rojo + diagnóstico
- [x] Chips de preguntas rápidas → respuestas mock semánticas
- [x] Campo de texto libre → respuestas mock
- [x] TTS nativo con botón mute/unmute
- [x] Animación de onda sonora en el orb
- [x] Frame del teléfono con contexto del scanner
- [x] Timestamps en cada mensaje
- [x] Responsive en mobile (frame se adapta)

---

## 📱 Mobile-First Design

La interfaz está optimizada para **operarios en el depósito**:

- **Pantalla del teléfono izquierda**: frame realista con Dynamic Island, mostrando el código QR a escanear
- **Panel de IA derecha**: grande, readable desde 50cm, botones grandes thumb-friendly
- **Diseño responsivo**: en mobile, el layout se apila verticalmente (scanner arriba, chat abajo)

---

## 🎤 Experiencia de Voz

### Simulada en `/mockups`:
- Los botones Correcto/Incorrecto simulan la captura de voz del operario
- Las respuestas del asistente suenan naturales gracias a `window.speechSynthesis` (o API externa si está configurada)

### Real en Producción:
- El operario dirá "Correcto" o "Incorrecto" (STT → botones automáticos)
- El asistente responde con voz natural (TTS)
- Los botones quedan como fallback táctil

---

## 🔐 Autenticación

- **`/mockups`**: Sin login (pública)
- **`/scanner`**: Con login (requiere sesión válida)
- **`/picking`**: Sin login (para demo sin backend)

El layout automáticamente redirige a `/login` excepto para estas 3 rutas.

---

## 📊 Responsables de Cada Componente

| Componente | Creado por | Status |
|---|---|---|
| ChatPanel orb + botones | Frontend | ✅ Completo |
| Speaker/TTS | Frontend | ✅ Completo |
| Mock responses | Frontend | ✅ Completo |
| Frame del teléfono | Frontend | ✅ Completo |
| Picking store (types) | Frontend | ✅ Esqueleto |
| API client types | Frontend | ✅ Esqueleto |
| Backend endpoints | **Backend** | ⏳ Pendiente |

---

## 🎯 URL Rápida para Mostrar

```
👉 http://localhost:5173/mockups 👈
```

Sin login, totalmente funcional, lista para demostración.
