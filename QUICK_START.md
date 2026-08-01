# ⚡ Quick Start — InvenTIA Demo

## 🎯 Acceso Inmediato

**URL Demo (sin login, sin backend):**
```
http://localhost:5173/mockups
```

**Listo para mostrar en 5 segundos** ✨

---

## 🎬 Qué Ver

### 1. La Interfaz
- **Izquierda**: Frame del teléfono con scanner simulado
- **Derecha**: Panel de chat del asistente de voz (IA)
- **Botones principales**:
  - ✓ **Correcto** (verde) → Escaneo exitoso
  - ✗ **Incorrecto** (rojo) → Error de colocación

### 2. Prueba los Botones
1. **Haz clic en "Correcto"**:
   - Frame del teléfono se pone verde
   - Checkmark animado
   - IA responde con confirmación

2. **Haz clic en "Incorrecto"**:
   - Frame del teléfono se pone rojo
   - X roja animada
   - IA proporciona diagnóstico

### 3. Prueba las Preguntas Rápidas
Debajo del campo de texto hay 3 botones:
- "¿Qué me falta?"
- "¿Dónde está el siguiente?"
- "¿Cuánto stock hay?"

Haz clic en cualquiera para ver la respuesta del asistente.

### 4. Escribe una Pregunta
En el campo de texto escribe algo como:
- "¿Dónde está el siguiente producto?"
- "¿Cuál es el stock disponible?"
- "¿Necesito algo más?"

El asistente responde con contexto del remito actual.

---

## 🎨 Visual Elements (Lo que Deberías Ver)

- **Orb azul**: IA lista y esperando
- **Orb púrpura con 3 puntos**: IA pensando
- **Orb celeste con onda sonora**: IA hablando (TTS)
- **Border verde en teléfono**: Escaneo correcto
- **Border rojo en teléfono**: Error
- **Bubble verde**: Confirmación
- **Bubble rojo**: Error/diagnóstico
- **Bubble azul**: Tu pregunta
- **Badge "DEMO"**: Modo de demostración

---

## 📱 Responsive Design

- **Desktop (1200+ px)**: Layout lado a lado (teléfono | chat)
- **Tablet/Mobile**: Stack vertical (teléfono arriba, chat abajo)

---

## 🔄 Flujo Completo en 30 Segundos

1. Abre `/mockups`
2. Haz clic en **"Correcto"** → ve el flash verde
3. Haz clic en **"¿Qué me falta?"** → respuesta del asistente
4. Escribe una pregunta → respuesta contextualizada
5. Haz clic en **"Incorrecto"** → ve el diagnóstico rojo

**¡Listo! Ya viste todo el flujo de la IA en tiempo real.**

---

## 🎙️ Audio (Opcional)

Si tienes micrófono y altavoz activados:
- Cada respuesta del asistente se **vocaliza** automáticamente
- Toggle mute en el icono del micrófono (esquina superior derecha del orb)

Si no tienes audio:
- Solo verás el texto (funciona igual, sin sonido)

---

## 📂 Dónde Está Todo

| Qué Quieres Ver | Dónde Ir |
|---|---|
| Demo interactiva | `http://localhost:5173/mockups` |
| Scanner con IA integrada | `http://localhost:5173/scanner` (requiere login) |
| Código del asistente | `frontend/src/lib/components/ChatPanel.svelte` |
| Módulo de audio | `frontend/src/lib/audio/speaker.ts` |
| Demo data hardcoded | `frontend/src/routes/mockups/+page.svelte` |

---

## 🚀 Para Mostrar a Otros

**Comparte esta URL:**
```
http://localhost:5173/mockups
```

No necesitan acceso, no necesitan credenciales, no necesita backend.

**Perfecto para:**
- Demo en presentación
- Validación con stakeholders
- Testing visual
- Capturas de pantalla

---

## ✅ Checklist de Demo

- [ ] Abre `/mockups` sin login
- [ ] Pantalla carga rápido (sin errores)
- [ ] Frame del teléfono visible izquierda
- [ ] Panel de IA visible derecha
- [ ] Haz clic "Correcto" → flash verde
- [ ] Haz clic "Incorrecto" → flash rojo
- [ ] Haz clic pregunta rápida → respuesta
- [ ] Escribe pregunta → respuesta diferente
- [ ] Orb cambia de color (azul → púrpura → celeste)
- [ ] TTS suena (si audio está activado)

---

## 🔧 Si Algo No Funciona

### "Página en blanco"
→ Abre la consola del navegador (F12) → mira si hay errores
→ Reinicia el dev server: `npm run dev`

### "No se escucha audio"
→ Comprueba que el micrófono esté activo en el navegador
→ Intenta hacer clic en el icono del micrófono para unmutear
→ El audio es opcional, el texto funciona sin él

### "Los botones no responden"
→ Abre console (F12) → busca errores JavaScript
→ Actualiza la página (Ctrl+Shift+R hard refresh)

---

## 📞 Contacto

Si encuentras un bug o tienes dudas:
1. Lee `DEMO_GUIDE.md` (más detallado)
2. Lee `FEATURES_MAP.md` (architecture)
3. Abre un issue con screenshot

---

## 🎉 ¡Listo!

Disfruta la demo. La feature está lista para mostrar y el backend está listo para conectar.

👉 **Abre esto ahora**: `http://localhost:5173/mockups`
