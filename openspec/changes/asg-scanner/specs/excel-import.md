# Spec: excel-import

## Capability Summary
Admin uploads an Excel file (.xlsx) containing the product catalog. The backend parses it with pandas + openpyxl, validates required columns, handles duplicates and existing barcodes, and inserts products into the SQLite database.

## Requirements

### Functional
1. The backend MUST expose a `POST /api/v1/products/import` endpoint that accepts a multipart `.xlsx` file upload.
2. The uploaded file MUST contain at minimum the columns: `sku`, `descripcion`, `codigo_de_barra`.
3. If any required column is missing, the backend MUST return a clear error response listing exactly which columns are missing; no partial import SHALL occur.
4. The backend MUST skip empty rows silently without aborting the import.
5. The backend MUST handle duplicate SKUs within the same Excel file according to the chosen strategy (see Requirement 6).
6. The import endpoint MUST support a `duplicate_strategy` query parameter with values:
   - `error` (default): abort import and return a list of duplicate SKUs.
   - `skip`: skip duplicate SKUs, import the rest.
   - `overwrite`: update existing product rows with the new Excel data.
7. If a `codigo_de_barra` in the Excel already exists in the database under a different `sku`, the backend MUST return an error listing the conflicting barcodes; no partial import SHALL occur.
8. The backend MUST validate that `sku` and `codigo_de_barra` are non-empty strings for every row; rows failing validation MUST be collected and returned in the error response.
9. On success, the backend MUST return the count of products imported and/or updated.

### Non-Functional
10. The endpoint MUST use pandas vectorized operations; row-by-row iteration (`iterrows`) SHALL NOT be used.
11. The import MUST run inside a SQLite transaction so that any error rolls back all changes.
12. Memory usage for large catalogs SHOULD be checked with `df.memory_usage(deep=True)`.

## Scenarios

### Scenario 1: Happy Path — Correct Excel Import
**Given** an Excel file with columns `sku`, `descripcion`, `codigo_de_barra` and 150 valid rows  
**When** the admin uploads the file with default `duplicate_strategy=error`  
**Then** the backend parses the file with pandas  
**And** inserts all 150 products into the database  
**And** returns HTTP 200 with `{ "imported": 150, "updated": 0, "skipped": 0 }`

### Scenario 2: Error Case — Missing Columns
**Given** an Excel file with columns `sku`, `descripcion` (missing `codigo_de_barra`)  
**When** the admin uploads the file  
**Then** the backend returns HTTP 400 Bad Request  
**And** the error body contains `{ "missing_columns": ["codigo_de_barra"] }`  
**And** zero rows are written to the database

### Scenario 3: Edge Case — Empty Rows in Excel
**Given** an Excel file with 150 valid rows and 10 completely empty rows interspersed  
**When** the admin uploads the file  
**Then** the backend skips the 10 empty rows  
**And** imports the 150 valid rows  
**And** returns `{ "imported": 150, "updated": 0, "skipped": 0 }`

### Scenario 4: Error Case — Duplicate SKUs with Strategy `error`
**Given** an Excel file where SKU "ABC-123" appears twice  
**When** the admin uploads with `duplicate_strategy=error`  
**Then** the backend returns HTTP 400  
**And** the error body contains `{ "duplicate_skus": ["ABC-123"] }`  
**And** zero rows are written to the database

### Scenario 5: Edge Case — Duplicate SKUs with Strategy `skip`
**Given** an Excel file where SKU "ABC-123" appears twice  
**And** "ABC-123" already exists in the database  
**When** the admin uploads with `duplicate_strategy=skip`  
**Then** the backend skips the duplicate SKU  
**And** imports all other rows  
**And** returns `{ "imported": N, "updated": 0, "skipped": 1 }`

### Scenario 6: Edge Case — Duplicate SKUs with Strategy `overwrite`
**Given** an Excel file where SKU "ABC-123" has a new description  
**And** "ABC-123" already exists in the database  
**When** the admin uploads with `duplicate_strategy=overwrite`  
**Then** the backend updates the existing product row  
**And** imports all other rows  
**And** returns `{ "imported": N, "updated": 1, "skipped": 0 }`

### Scenario 7: Error Case — Barcode Already Exists for Different SKU
**Given** an Excel file with SKU "NEW-001" and barcode "7501234567890"  
**And** the database already has SKU "OLD-001" with barcode "7501234567890"  
**When** the admin uploads the file  
**Then** the backend returns HTTP 400  
**And** the error body contains `{ "barcode_conflicts": [{ "sku": "NEW-001", "barcode": "7501234567890", "existing_sku": "OLD-001" }] }`  
**And** zero rows are written to the database

## Design Notes (from fastapi-templates and pandas-pro skills)
- Use FastAPI `UploadFile` with `pandas.read_excel(..., engine="openpyxl")`.
- Validate columns with `set(required_columns).issubset(df.columns)`.
- Drop empty rows with `df.dropna(how="all", inplace=True)`.
- Detect duplicates with `df[df.duplicated(subset=["sku"], keep=False)]`.
- Check barcode conflicts via a vectorized merge against the existing DB records.
- Wrap all DB writes in a single `conn.execute("BEGIN")` / `commit()` transaction.
