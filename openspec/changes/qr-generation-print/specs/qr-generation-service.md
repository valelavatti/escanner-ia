# QR Generation Service Specification

## Purpose

Generate, resize, cache, and return individual QR PNG files from the existing `ubicaciones.qr_valor` strings.

## Requirements

### Requirement: QR Image Generation

The system MUST generate a square PNG QR image for any given `qr_valor` string.

The system SHALL use `qrcode[pil]==8.0` and produce the QR with `qrcode.make(qr_valor)`.

The generated image SHALL be resized to the requested pixel size using Pillow with `Image.Resampling.NEAREST` so the QR modules stay sharp.

The generation logic SHALL run in a non-blocking worker thread via `asyncio.to_thread()` because the application uses async route handlers.

#### Scenario: Generate a single QR at default size

- GIVEN the service receives `qr_valor` "Pasillo 3-F1-C1" and size 200
- WHEN the QR image is produced
- THEN a valid 200×200 PNG file is returned or persisted
- AND the file encodes the exact `qr_valor` string

#### Scenario: Generate a QR with special characters

- GIVEN the service receives a `qr_valor` containing spaces and hyphens, e.g. "Pasillo 3-F1-C1"
- WHEN the QR image is produced
- THEN the generated image encodes the full string without truncation or corruption

---

### Requirement: Disk Cache

The system MUST cache each generated QR PNG on disk.

The cache path SHALL be `{qr_cache_dir}/{sanitized_qr_valor}_{size}.png`.

The cache key MUST include both the `qr_valor` and the `size`; different sizes for the same value SHALL produce separate cache files.

The service SHALL return the existing cached file when the same `qr_valor` and size are requested again.

#### Scenario: Cache hit reuses existing file

- GIVEN a PNG already exists for `qr_valor` "A-F1-C1" at size 200
- WHEN the same `qr_valor` and size are requested
- THEN the existing cached file is returned
- AND no new QR image is generated

#### Scenario: Different size produces separate cache entry

- GIVEN a cached PNG exists for `qr_valor` "A-F1-C1" at size 200
- WHEN the same `qr_valor` is requested at size 300
- THEN a new PNG is generated and cached at the 300px path
- AND the original 200px PNG remains unchanged

---

### Requirement: Cache Directory Management

The system MUST create the configured cache directory automatically during application startup if it does not exist.

The default cache directory SHALL be `./qr_cache/`.

The directory MUST be created before any QR generation request is served.

#### Scenario: Missing cache directory is created on startup

- GIVEN the configured cache directory does not exist
- WHEN the application finishes its startup/lifespan event
- THEN the directory exists and is writable

#### Scenario: Concurrent requests for the same uncached QR

- GIVEN two requests arrive for the same `qr_valor` and size before the cache file exists
- WHEN both requests are handled concurrently
- THEN both requests receive a valid PNG file
- AND the cache ends in a consistent state with a single file for that key

---

### Requirement: Batch Generation

The system SHALL support generating many QRs concurrently for a single estante.

The service SHOULD use `asyncio.gather()` together with `asyncio.to_thread()` when generating up to 35 QRs in one batch.

#### Scenario: Generate all QRs for a large estante

- GIVEN an estante with 35 ubicaciones and no cached QR files
- WHEN all 35 QRs are requested for printing
- THEN all 35 PNG files are generated and cached
- AND the total wall-clock time is materially shorter than sequential generation
