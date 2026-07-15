# Delta for barcode-scanning

## ADDED Requirements

### Requirement: Product Scan Without Anchored Location

When a product barcode is scanned and no location is anchored, the scanner MUST fetch the product's locations and present a `ProductLocationsCard` for selection instead of blocking with a red flash.

- The scanner MUST call the product-locations endpoint using the scanned barcode.
- If the product has one or more locations, the scanner MUST show `ProductLocationsCard`.
- If the product has no locations, the scanner MUST show the message "No está en ninguna ubicación. Escaneá un QR de sector para asignarlo." and remain ready to scan a QR.
- If the product-locations endpoint returns 404, the scanner MUST show a red flash with a "Producto no encontrado" message.
- Selecting a location from the card MUST anchor it and continue into the existing `ProductCard` + `StockInput` flow.
- The 2-second debounce on duplicate scans MUST still apply to this fallback flow.
- The existing QR-first flow (scan QR → anchor location → scan product → ProductCard + StockInput) MUST remain unchanged.

#### Scenario: Product scanned with anchored location — unchanged

- GIVEN a location is anchored and the user scans a product barcode
- WHEN the scan is processed
- THEN the existing flow runs (ProductCard + StockInput) without invoking the locations fallback

#### Scenario: Product scanned without anchored location, multiple locations

- GIVEN no location is anchored and the user scans a product present in 3 locations
- WHEN the scan is processed
- THEN the `ProductLocationsCard` appears listing all 3 locations
- AND WHEN the user taps the second location
- THEN that location is anchored and the stock entry form appears

#### Scenario: Product scanned without anchored location, no locations

- GIVEN no location is anchored and the scanned product has zero locations
- WHEN the scan is processed
- THEN the scanner shows "No está en ninguna ubicación. Escaneá un QR de sector para asignarlo."
- AND remains ready to scan a QR to anchor

#### Scenario: Product not in database

- GIVEN no location is anchored and the scanned barcode matches no product
- WHEN the lookup returns 404
- THEN a red flash shows "Producto no encontrado"

#### Scenario: Debounced duplicate scan

- GIVEN the user scans the same product barcode twice within 2 seconds without an anchored location
- WHEN the second scan arrives
- THEN it is ignored and no duplicate fetch is performed

#### Scenario: Cancel from locations card

- GIVEN the `ProductLocationsCard` is shown after a scan without anchored location
- WHEN the user taps "Cancelar"
- THEN the card closes, no location is anchored, and scanning resumes

## REMOVED Requirements

### Requirement: Block Product Scan Without Anchored Location

(Reason: Replaced by the fallback locations flow above — scanning a product without an anchored location now shows available locations instead of a blocking red flash.)

The previous behavior: scanning a product barcode while no location was anchored MUST block the scan with a red flash "Escaneá un QR de sector primero".
