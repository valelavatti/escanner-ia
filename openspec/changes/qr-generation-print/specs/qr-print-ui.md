# QR Print UI Specification

## Purpose

Provide warehouse staff with a print interface on the estante admin page to generate and print QR labels at selectable sizes and page densities.

## Requirements

### Requirement: Print Button

The system MUST add an "Imprimir QRs" button to the estante detail view, alongside the existing ubicaciones grid.

The button SHALL be visible only when the selected estante has at least one active ubicacion.

#### Scenario: Open print interface from estante detail

- GIVEN the user is viewing the detail of an estante with ubicaciones
- WHEN the page renders
- THEN an "Imprimir QRs" button is displayed
- AND the button uses the same visual style as other primary actions on the page

---

### Requirement: Print Configuration Modal

The system MUST open a modal when the user clicks "Imprimir QRs".

The modal SHALL contain:

- A dropdown for "QRs por página" with options 1, 2, 4, 6, 8, and 9, defaulting to 4.
- A dropdown for "Tamaño del QR" with options Small (150 px), Medium (200 px), and Large (300 px), defaulting to Medium.
- A small visual preview of how the A4 sheet will be arranged.
- A "Generar e imprimir" button.
- A "Descargar ZIP" button.

#### Scenario: Configure print options

- GIVEN the print modal is open
- WHEN the user selects 1 QR por página and Large size
- THEN the preview updates to show one large QR per A4 page

#### Scenario: Configure nine small QRs per page

- GIVEN the print modal is open
- WHEN the user selects 9 QRs por página and Small size
- THEN the preview updates to show a 3×3 grid of small QRs per A4 page

---

### Requirement: Generate and Print

The system MUST call the printable A4 endpoint when the user clicks "Generar e imprimir".

The result SHALL be opened in a new browser tab via `window.open()`.

The browser print dialog SHOULD be triggered automatically after the sheet loads.

The modal SHALL show a loading state while the request is in progress.

#### Scenario: Generate A4 sheet for the selected estante

- GIVEN the user chose per_page=4 and size=Medium
- WHEN the user clicks "Generar e imprimir"
- THEN the UI shows a loading indicator
- AND a new tab opens with the generated A4 PNG
- AND the browser print dialog appears

#### Scenario: Loading state during generation

- GIVEN the user clicked "Generar e imprimir" for an estante with 35 ubicaciones
- WHEN the backend is still generating the sheet
- THEN the "Generar e imprimir" button is disabled
- AND a loading indicator is visible

---

### Requirement: Download ZIP

The system MUST call the estante QR bundle endpoint when the user clicks "Descargar ZIP".

The browser SHALL download the ZIP file containing all QR PNGs for the estante.

#### Scenario: Download all QRs

- GIVEN the print modal is open for an estante with 8 ubicaciones
- WHEN the user clicks "Descargar ZIP"
- THEN the browser downloads a ZIP file
- AND the ZIP contains one PNG per ubicacion

---

### Requirement: Mobile-Friendly Layout

The print modal SHALL be usable on mobile devices.

On narrow viewports, the modal SHOULD slide up from the bottom of the screen.

All interactive targets in the modal SHALL be at least 48×48 pixels.

#### Scenario: Open modal on a phone

- GIVEN the user is on a viewport narrower than 640 px
- WHEN the "Imprimir QRs" button is clicked
- THEN the modal appears anchored to the bottom of the screen
- AND all dropdowns and buttons are easy to tap

---

### Requirement: Error Handling

The system MUST display a clear error message if generating or downloading fails.

Errors to handle include network errors, 404 responses (estante or ubicacion no longer exists), and 401 responses (session expired).

#### Scenario: Estante deleted while modal is open

- GIVEN the print modal is open
- AND the estante is soft-deleted before the user clicks "Generar e imprimir"
- WHEN the user triggers generation
- THEN the backend returns 404
- AND the UI shows an error message explaining that the estante no longer exists

#### Scenario: Session expires before print request

- GIVEN the user's session has expired
- WHEN the user clicks "Generar e imprimir"
- THEN the backend returns 401
- AND the UI prompts the user to log in again
