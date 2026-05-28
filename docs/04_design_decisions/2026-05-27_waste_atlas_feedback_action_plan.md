---
title: Waste Atlas feedback action plan
status: draft
date: 2026-05-27
---

# Waste Atlas feedback action plan

This file tracks remaining work from the Waste Atlas feedback e-mails, including the Catalonia update from Steffen and the production data check performed on 2026-05-27.

## Current evidence

- Catalonia local V3 import contains 1,894 collection rows for 2024 and 1,894 collection rows for 2020 across 947 catchments.
- Catalonia local V3 2024 collection-system distribution:
  - Biowaste: 501 Bring point, 261 Door to door, 70 Mixed door-to-door and bring point, 115 No separate collection.
  - Residual waste: 612 Bring point, 266 Door to door, 69 Mixed door-to-door and bring point.
- Catalonia local V3 2020 collection-system distribution:
  - Biowaste: 607 Bring point, 127 Door to door, 54 Mixed door-to-door and bring point, 159 No separate collection.
  - Residual waste: 764 Bring point, 129 Door to door, 53 Mixed door-to-door and bring point, 1 No separate collection.
- Catalonia 2024 production amount data exists for biowaste and residual waste.
- Catalonia 2024 connection-rate data exists for 325 biowaste rows after the local V3 import.
- Catalonia 2024 production collection rows contain access/use-control fields.
- Catalonia local V3 import created/retained 801 biowaste impurity CPVs for 2020/2024.
- Catalonia local V3 import created/retained 228 weekly bring-point access-day CPVs for 2024.

## Resolved or low-risk items

- [x] Confirm Catalonia 2024 core production import.
  - Production contains the expected biowaste and residual-waste collection rows across 947 catchments.
  - Production contains 2020 and 2024 amount CPVs for biowaste and residual waste.
  - Production contains 2024 connection-rate CPVs for biowaste.
  - Production collection rows include access/use-control fields.

- [x] Confirm existing route coverage for Catalonia impurity and weekly bring-point access-day pages.
  - `waste-atlas-catalonia-biowaste-impurity-map` already exists.
  - `waste-atlas-catalonia-weekly-bp-access-days-map` already exists.
  - Remaining work is data availability and selector exposure, not base route creation.

- [x] Confirm `PAP total` internal import behavior.
  - The V3 importer maps `PAP total`, `PAP Total + PxG`, and `Door-to-door` to canonical `Door to door` only when the PaP connection rate is absent or at least 95%.
  - Rows below the 95% threshold are mapped to canonical `Mixed door-to-door and bring point`.
  - Remaining work is a display-label decision for Catalonia maps, not an import-mechanics question.

## Remaining Catalonia data decisions and fixes

- [x] Verify `PAP parcial` handling against the updated raw Catalonia workbook.
  - The workbook contains 108 `PAP parcial`/`PAP Parcial` rows across 56 LAU municipalities: 54 biowaste rows and 54 residual-waste rows.
  - Production currently stores all 108 corresponding 2024 Catalonia biowaste/residual rows as canonical `Door to door`.
  - Production currently has no `Mixed door-to-door and bring point` collection-system record.
  - This is a production data mismatch: raw `PAP parcial` values should be repaired to canonical `Mixed door-to-door and bring point` if that canonical system is retained for mixed PAP/BP service.

- [x] Repair production `PAP parcial` rows.
  - Created/published the canonical `Mixed door-to-door and bring point` collection system in production as ID 40.
  - Patched the 108 Catalonia 2024 collection rows identified from workbook `PAP parcial`/`PAP Parcial` values from `Door to door` to `Mixed door-to-door and bring point`.
  - Preserved the existing `BP_Access control/PAP_Use control_2024` import values; production already contains split BP/PAP access/use-control values for the affected rows.
  - Production verification after patch: 108/108 expected rows now use `Mixed door-to-door and bring point`; 0 remain as `Door to door`; no expected rows are missing.

- [x] Import local Catalonia V3 workbook update.
  - Imported workbook `BRIT_Katalonien_2024_SW_V3.xlsx` locally as user `phillipp` with publication status `review`.
  - Loaded 3,788 records from 1,894 workbook rows: 1,894 2024 records and 1,894 2020 records.
  - Import stats: 1,894 created, 1,074 unchanged, 0 skipped, 1,032 CPVs created, 7,370 CPVs unchanged, 0 CPVs skipped, 31 flyers created, 0 warnings.
  - Created missing local reference data needed by the import: `Mixed door-to-door and bring point`, `biowaste impurity rate`, `weekly bring-point access days`, `d/wk`, and 16 exact source-backed frequency labels.

- [ ] Decide Catalonia display labels for canonical collection systems.
  - Decide whether `Door to door` should be displayed as `PAP total` on Catalonia-specific maps.
  - Decide whether `Mixed door-to-door and bring point` should be displayed as `PAP parcial`.
  - Keep internal canonical labels unchanged unless a separate data-quality issue is found.

- [x] Import or repair Catalonia impurity data locally.
  - V3 source columns provide 2020 and 2024 impurity coverage.
  - Local verification after import: 801 `biowaste impurity rate` CPVs across 2020 and 2024.

- [x] Import weekly bring-point access-day data locally.
  - V3 workbook includes `BP_Weekly_access_days_2024`.
  - Local verification after import: 228 `weekly bring-point access days` CPVs for 2024 using unit `d/wk`.

## Remaining Catalonia map implementation

- [x] Add a Catalonia biowaste collection-system map.
  - Show biowaste-specific collection system per catchment.
  - Use Catalonia-specific labels expected by the feedback: `No separate collection`, `PAP parcial`, `PAP total`, `Bring point`.

- [x] Add a Catalonia residual-waste collection-system map.
  - Show residual-waste-specific collection system per catchment.
  - Use the same Catalonia-specific labels as the biowaste map.

- [x] Add a combined Catalonia biowaste/residual collection-system map.
  - Show combinations of biowaste and residual-waste systems.
  - Include combinations over `No separate collection`, `PAP parcial`, `PAP total`, and `Bring point`.
  - Keep legend labels concise enough for export.

- [x] Add a Catalonia collection-system plus access/use-control map.
  - Only classify catchments where biowaste and residual waste use the same system.
  - Render all other combinations grey as `Other combination`.
  - Required classes:
    - `Bring point + access control`
    - `Bring point + no access control`
    - `PAP + use control`
    - `PAP + no use control`
    - `Other combination`
  - Decide how `PAP parcial` should be handled with `BP_Access control/PAP_Use control_2024`; if not feasible in the first implementation, classify it as `Other combination`.

- [x] Expose new code-only Catalonia collection-system maps in the Waste Atlas selector.
  - Add selector entries for the new stream-specific and combined collection-system maps.

- [ ] Expose data-dependent Catalonia maps in the Waste Atlas selector when ready.
  - Add selector entry for Catalonia impurity map once data is present.
  - Add selector entry for weekly bring-point access days only if retained.

## Remaining broader Waste Atlas corrections

- [ ] Complete South Tyrol data correction checks.
  - Validate collection-point count maps.
  - Validate split residual, biowaste, and ratio maps.
  - Confirm amount and system maps use the intended data and labels.

- [ ] Review and adjust collection-point count legend bins.
  - Confirm requested bins and labels.
  - Ensure export labels remain concise and readable.

- [ ] Review and adjust bin-size legend bins.
  - Confirm requested bin thresholds.
  - Ensure bin labels are consistent across country-specific maps.

- [ ] Review collection-frequency and collection-count legend labels.
  - Remove ambiguous wording.
  - Keep on-screen labels explanatory and export labels concise.

- [ ] Review combined fee-system maps.
  - Confirm category logic.
  - Simplify legend labels where needed.

- [ ] Perform a final label and terminology audit.
  - Align `Door to door`, `PAP total`, `PAP parcial`, `Bring point`, `No separate collection`, and `Mixed door-to-door and bring point` usage.
  - Decide where internal canonical labels should be translated to country-specific display labels.

## Validation required after implementation

- [x] Add regression coverage for the new Catalonia collection-system endpoints and map routes.
- [x] Add regression coverage for the Catalonia system plus access/use-control endpoint and map route.
- [x] Run targeted Django tests inside Docker with `--settings=brit.settings.testrunner`.
- [x] Validate JavaScript syntax for changed Waste Atlas source and minified assets if JavaScript changes are needed.
  - No JavaScript changes were needed for the code-only Catalonia map additions.
- [ ] Visually inspect representative Catalonia exports after implementation.
