# Exploration: ASG Scanner for "escanner productos"

## Interpretation of "ASG Scanner"

Given the project name **"escanner productos"** (Spanish for "product scanner"), the most probable interpretation is:

> **An application for scanning products labeled with an "ASG" prefix/code** — likely a barcode/QR scanner for inventory, price checking, or product verification of ASG-branded or ASG-coded items.

### Why this interpretation is most likely

| Factor | Evidence |
|--------|----------|
| Project name | "escanner productos" = product scanner |
| Language context | Spanish naming suggests a Spanish-speaking market/team |
| Empty project | Greenfield — no existing AWS or cloud infrastructure code |
| "ASG" as prefix | Common in retail/manufacturing for product line codes (e.g., ASG-12345) |

### Alternative interpretations considered and ruled out

| Interpretation | Likelihood | Reasoning |
|----------------|------------|-----------|
| **AWS Auto Scaling Group scanner** | Very Low | No cloud infrastructure context; project name is clearly product-focused |
| **Amazon Security Group scanner** | Very Low | Same as above — no AWS/cloud signals |
| **ASG = "Asociación de Supermercados" scanner** | Low-Med | Possible regional retail association, but less likely than a brand code |
| **ASG = generic product code prefix** | **High** | Common pattern in inventory systems |

---

## Suggested Technology Stack

Since the project is empty, we have full freedom to choose. The best choice depends on **how the scanner will be used** (desktop vs. mobile vs. web).

### Option A: Electron + React + TypeScript (Desktop)

**Best for:** Warehouse/inventory desktop stations with USB barcode scanners or webcam scanning.

- **Frontend:** React 18+ with TypeScript
- **Desktop shell:** Electron (cross-platform: Windows, macOS, Linux)
- **Barcode scanning:** `quagga2` or `html5-qrcode` (camera) + USB HID listener for physical scanners
- **Data storage:** SQLite (embedded, no server needed) or JSON flat files
- **Build tool:** Vite
- **UI library:** Tailwind CSS + shadcn/ui or Material UI

**Pros:**
- Native desktop feel with web tech
- Easy USB scanner integration
- Works offline
- Single installer for end users

**Cons:**
- Larger bundle size than pure web
- No mobile support

**Effort:** Medium

---

### Option B: React + TypeScript PWA (Web)

**Best for:** Cross-device access, bring-your-own-device scenarios.

- **Frontend:** React 18+ with TypeScript, built as PWA
- **Barcode scanning:** `html5-qrcode` (uses device camera)
- **Data storage:** IndexedDB (via Dexie.js) for offline-first
- **Backend (optional):** Node.js + Express + PostgreSQL (if multi-user/sync needed)
- **Build tool:** Vite + PWA plugin
- **UI library:** Tailwind CSS

**Pros:**
- Works on any device with a camera
- No installation required
- Easy to deploy and update
- Can work offline as PWA

**Cons:**
- Camera scanning is slower than dedicated hardware
- Requires browser permissions
- Less reliable for high-volume scanning

**Effort:** Low-Medium

---

### Option C: Python + Tkinter/PyQt (Desktop Utility)

**Best for:** Quick prototype or internal tool.

- **Language:** Python 3.11+
- **GUI:** Tkinter (built-in) or PyQt6
- **Barcode scanning:** OpenCV + `pyzbar`
- **Data storage:** SQLite via `sqlite3`
- **Packaging:** PyInstaller

**Pros:**
- Fastest to prototype
- Good for image processing pipelines
- Single-file executable output

**Cons:**
- Harder to maintain UI than web-based
- Less modern look and feel
- Harder to find React/JS developers to extend

**Effort:** Low

---

### Option D: Flutter (Cross-Platform Mobile + Desktop)

**Best for:** Mobile-first with possible desktop expansion.

- **Framework:** Flutter 3.x (Dart)
- **Barcode scanning:** `mobile_scanner` package
- **Data storage:** `sqflite` (SQLite for Flutter)
- **State management:** Riverpod or Bloc

**Pros:**
- True native performance on mobile
- Single codebase for iOS, Android, Windows, macOS, Linux
- Excellent camera integration

**Cons:**
- Dart is less common than JS/TS or Python
- Desktop support is newer/less mature
- Larger app size

**Effort:** Medium

---

## Recommendation

**Primary recommendation: Option A (Electron + React + TypeScript)** if the use case is a fixed workstation with a USB barcode scanner.

**Alternative recommendation: Option B (React PWA)** if users will scan with their phones or tablets.

If the user confirms mobile is the target, switch to **Option D (Flutter)** or **Option B (PWA)**.

---

## Key Features and Requirements

Based on the "product scanner" concept, an ASG scanner should likely include:

### Core Features (MVP)
1. **Barcode/QR Scanning**
   - Support for common formats: Code 128, EAN-13, UPC-A, QR Code, Data Matrix
   - Input via camera (webcam/phone camera) or USB HID barcode scanner

2. **Product Lookup**
   - Parse scanned code and match against product database
   - Display product name, description, price, stock level
   - Handle "ASG" prefix stripping/validation if codes are prefixed

3. **Manual Entry**
   - Type code manually if barcode is damaged
   - Search by product name or partial code

4. **Data Storage**
   - Local product database (SQLite or IndexedDB)
   - Import products from CSV/Excel
   - Export scan history to CSV/Excel

5. **Scan History**
   - Log of all scanned items with timestamps
   - Filter and search history

### Extended Features (Post-MVP)
6. **Inventory Management**
   - Adjust stock quantities on scan
   - Track inbound/outbound movements

7. **Multi-user / Sync**
   - User accounts
   - Cloud sync of scan data (if multi-device)

8. **Label Printing**
   - Print barcode labels for unlabeled products

9. **Integration**
   - REST API to connect with ERP/WMS systems
   - Webhook support for real-time notifications

---

## Open Questions for the User

Before proceeding to proposal, these ambiguities need clarification:

1. **What does "ASG" stand for?**
   - Is it a brand name, a product line prefix, or something else?
   - Should the scanner validate/filter codes that start with "ASG"?

2. **What is the target platform?**
   - Desktop (Windows PC with USB scanner)?
   - Mobile (phone/tablet camera)?
   - Web (browser-based)?
   - All of the above?

3. **What happens after a scan?**
   - Just display product info?
   - Update inventory/stock?
   - Log the scan for later review?
   - Generate a report?

4. **Is there an existing product database?**
   - Do you already have product data (CSV, Excel, database)?
   - Or do we need to build the product catalog too?

5. **Offline vs. online?**
   - Must it work without internet?
   - Is a backend server acceptable?

6. **Language/locale requirements?**
   - Spanish UI (given project name)?
   - Any specific regional formatting for prices, dates?

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Ambiguous "ASG" meaning** | High | High | Clarify with user before spec phase |
| **Wrong platform choice** | Medium | High | Ask target platform before committing to stack |
| **Barcode scanning reliability** | Medium | Medium | Test `html5-qrcode` / `quagga2` early; have manual entry fallback |
| **No existing product data** | Medium | Medium | Plan for CSV import as core MVP feature |
| **Scope creep (inventory, ERP sync)** | High | Medium | Lock MVP scope early; defer advanced features |
| **Camera permission issues (web)** | Medium | Low | PWA best practices; clear user guidance |

---

## Current State

The project is **completely empty**. Only `.atl/` and `openspec/` configuration directories exist. There is no source code, no dependencies, no tests, and no established architecture. This is a greenfield project with no technical debt or legacy constraints.

---

## Ready for Proposal

**Status: No — pending user clarification.**

The concept is clear enough to form a proposal, but the following blockers should be resolved first:

1. Confirm "ASG" meaning and whether it's a filter/prefix for scanned codes
2. Confirm target platform (desktop web, mobile, or both)
3. Confirm primary action after scan (display, log, update inventory)

Once these 3 questions are answered, we can proceed to `sdd-propose`.
