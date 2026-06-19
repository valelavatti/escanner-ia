# Spec: barcode-scanning

## Capability Summary
Unified QR and barcode scanner using `html5-qrcode` v2.3.8 in a SvelteKit PWA. The scanner auto-detects the code format: `QR_CODE` is treated as a sector/ubicacion anchor; `EAN_13`, `CODE_128`, and `UPC_A` are treated as product barcodes. The scanner lifecycle (start, stop, pause, resume, clear) is managed correctly, with camera release on navigation and debouncing for rapid duplicate scans.

## Requirements

### Functional
1. The scanner MUST support a single `Html5QrcodeScanner` instance configured with `formatsToSupport: [QR_CODE, EAN_13, CODE_128, UPC_A]`.
2. On a successful scan, the callback MUST inspect `result.result.format?.formatName` to determine the code type:
   - If `QR_CODE`, the decoded text MUST be treated as a sector/ubicacion identifier. The system SHALL look it up in the `ubicaciones` table. If found, the location is "anchored" for subsequent product scans. If not found, a clear error message MUST be shown.
   - If `EAN_13`, `CODE_128`, or `UPC_A`, the decoded text MUST be treated as a `codigo_de_barra`. The system SHALL look up the product in the `productos` table.
3. If a product barcode is NOT found in the database, the UI MUST show a clear "Producto no encontrado" message and SHALL provide an option to add the product manually (post-MVP shortcut: link to manual entry).
4. The scanner MUST debounce/throttle duplicate scans of the same code within 2 seconds; repeated scans of the identical code MUST be ignored during the debounce window.
5. When the user navigates away from the scanner page, the component MUST call `scanner.stop()` and/or `scanner.clear()` to release the camera.
6. The scanner SHOULD use `facingMode: "environment"` to prefer the rear camera.
7. The scanner SHOULD expose torch and zoom controls when supported by the device (`showTorchButtonIfSupported: true`, `showZoomSliderIfSupported: true`).
8. If camera permission is denied, the UI MUST show a graceful fallback with guidance text (e.g., "Permita el acceso a la camara en la configuracion de Safari/Chrome") and a button to retry.
9. The scanner MAY support `SCAN_TYPE_FILE` as a fallback for damaged barcodes via photo upload.

### Non-Functional
10. Scan-to-result latency MUST be under 1 second on warehouse WiFi.
11. The scanner UI MUST be full-screen on mobile with large tap targets (minimum 48x48px for control buttons).

## Scenarios

### Scenario 1: Happy Path — Scan Sector QR
**Given** the user is on the scanner page with an active session  
**And** the camera is running with `facingMode: "environment"`  
**When** the user scans a QR code whose text matches ubicacion id `U-001`  
**Then** the callback receives `result.result.format?.formatName === "QR_CODE"`  
**And** the system queries the backend for ubicacion `U-001`  
**And** the location is anchored (displayed on screen)  
**And** the scanner remains active for the next product scan

### Scenario 2: Happy Path — Scan Product Barcode
**Given** the user has already anchored ubicacion `U-001`  
**When** the user scans a barcode `7501234567890` with format `EAN_13`  
**Then** the callback receives `result.result.format?.formatName === "EAN_13"`  
**And** the system queries the backend for product with `codigo_de_barra = 7501234567890`  
**And** the product details (sku, descripcion, stock acumulado) are displayed  
**And** the stock entry form is shown

### Scenario 3: Error Case — Product Not Found
**Given** the user scans a product barcode `9990001112223` with format `UPC_A`  
**And** no product in the database has that barcode  
**When** the scan succeeds  
**Then** the UI shows a clear message "Producto no encontrado"  
**And** the UI presents an option to "Agregar manualmente" (manual entry)

### Scenario 4: Error Case — QR Sector Not Found
**Given** the user scans a QR code with text `SECTOR-X`  
**And** no ubicacion in the database matches `SECTOR-X`  
**When** the scan succeeds  
**Then** the UI shows a clear error message "Ubicacion no registrada"  
**And** the location is NOT anchored

### Scenario 5: Edge Case — Camera Permission Denied
**Given** the user opens the scanner page  
**When** the browser denies camera access  
**Then** the scanner UI shows a fallback panel with text: "Permita el acceso a la camara en la configuracion de su navegador"  
**And** a "Reintentar" button is shown  
**And** tapping "Reintentar" calls `scanner.render(...)` again

### Scenario 6: Edge Case — Navigate Away Releases Camera
**Given** the scanner is active and streaming  
**When** the user navigates to another route (e.g., Visual Map)  
**Then** the SvelteKit component's `onDestroy` (or equivalent cleanup) MUST call `scanner.stop()` followed by `scanner.clear()`  
**And** the camera indicator LED (if present) MUST turn off

### Scenario 7: Edge Case — Rapid Duplicate Scan Debounced
**Given** the user scans barcode `7501234567890` at time T  
**When** the same barcode `7501234567890` is scanned again at time T+0.5s  
**Then** the second scan MUST be ignored  
**And** no duplicate backend request is made  
**When** the same barcode is scanned again at time T+3s  
**Then** the scan is processed normally

### Scenario 8: Edge Case — Torch and Zoom on Supported Device
**Given** the device supports torch and zoom  
**When** the scanner initializes with `showTorchButtonIfSupported: true` and `showZoomSliderIfSupported: true`  
**Then** torch toggle and zoom slider controls are visible  
**And** the user can adjust zoom to improve barcode readability in low light

## Design Notes (from sveltekit-structure skill and Context7 /mebjas/html5-qrcode)
- Implement the scanner in a dedicated SvelteKit route (e.g., `/scanner/+page.svelte`).
- Use `browser` check from `$app/environment` to ensure scanner code only runs client-side.
- Manage scanner lifecycle in `onMount` / `onDestroy` to guarantee `stop()` and `clear()` on unmount.
- Store the last scanned code and timestamp in a Svelte writable store; debounce by comparing `(now - lastScanTime) < 2000 && code === lastCode`.
- Context7-verified APIs:
  - `new Html5QrcodeScanner("reader", { fps: 10, qrbox: 250, formatsToSupport: [...], showTorchButtonIfSupported: true, showZoomSliderIfSupported: true }, false)`
  - Callback signature: `(decodedText, result) => { ... result.result.format?.formatName ... }`
  - `scanner.pause()` / `scanner.resume()` / `scanner.getState()` / `scanner.stop()` / `scanner.clear()`
  - Camera constraint: `{ facingMode: "environment" }`
