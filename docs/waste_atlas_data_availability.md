# Waste Atlas — Data Availability by Country

| Data field | Map | DE (2022) | SE (2023) | DK (2023) | NL (2023) | BE (2022) | IT |
|---|---|---|---|---|---|---|---|
| **Collections in DB** | — | 2,060 | 508 | 113 | 355 | 106 | 0 |
| **Orga level** (NUTS/LAU regions) | Karte 1 | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| **Collection system** | Karte 2 | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| **Connection rate** | Karte 3 | ✅ | ✅ | ❌ | ❌ | ✅ | — |
| **Sorting method** | Karte 4 / Map 34 | ❌ | ❌ | ❌ | ❌ | ❌ | — |
| **Paper bags** | Karte 5 | ✅ (DE) | — | — | — | — | — |
| **Plastic bags** | Karte 6 | ✅ (DE) | — | — | — | — | — |
| **Collection support** | Karte 7 | ✅ (DE) | — | — | — | — | — |
| **Fee system** | Karte 8/9 | ✅ | ❌ | ⚠️ trivial | ❌ | ✅ | — |
| **Frequency type** | Karte 10 | ✅ | ❌ | ✅ | ❌ | ✅ | — |
| **Biowaste amount** (collected) | Karte 18 | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| **Residual waste amount** | Karte 17 | ✅ (DE) | ✅ | ❌ | ❌ | ✅ | — |
| **Waste ratio** (bio/residual) | Karte 19 | ✅ (DE) | ✅ | ❌ | ❌ | ✅ | — |
| **Green waste** | Karte 15–16 | ✅ (DE) | ❌ | ❌ | ❌ | ✅ | — |
| **Organic collection amount** (treated) | Karte 27 | — | ✅ | ✅ | ❌ | ❌ | — |
| **Organic waste ratio** | Karte 28 | — | ✅ | ✅ | ❌ | ❌ | — |
| **Min bin size** | Karte 21 | ⚠️ sparse | ❌ | ❌ | ❌ | ❌ | — |
| **Required bin capacity** | Karte 22 | ⚠️ sparse | ❌ | ❌ | ❌ | ❌ | — |

## Legend

- **✅** — Data available (substantial coverage)
- **❌** — All null / no data
- **⚠️** — Trivial (e.g., 99% single value) or very sparse (<5%)
- **—** — Not applicable / country has no collections

## Notes by Country

### Germany (DE, 2022)
- Most complete dataset — all map types supported
- Green waste maps available (Karte 15–16)
- Connection rate: very sparse (only 6 records)
- Min bin size / required bin capacity: extremely sparse (1–2 records)

### Sweden (SE, 2023)
- Rich collection amount data for "treated" waste (organic maps 27–28)
- Connection rate available (229/508)
- No frequency data at all
- No sorting method data yet (Map 34 will show "no data" until imported)

### Denmark (DK, 2023)
- "Waste treated" CPVs enable organic amount/ratio maps (Karte 27–28)
- Frequency type available (Fixed / Fixed-Seasonal / Fixed-Flexible)
- Connection rate: all null
- Sorting method: all null
- Fee system: trivial (112/113 = Flat fee)

### Netherlands (NL, 2023)
- Only Biowaste category (no Food waste, Residual, Green)
- Collection amount (specific/total waste collected) available
- No fee system, frequency, or connection rate data
- No "waste treated" (organic) data

### Belgium (BE, 2022)
- Richest non-German dataset — all 4 waste categories present
- Fee system: diverse (Flat fee, No fee, PAYT)
- Frequency and connection rate available
- Green waste data available (Karte 15–16 possible)
- Residual waste amount and waste ratio possible
- **Most underexploited** — only orga-level map currently linked

### Italy (IT)
- No collections in database yet
- Country-specific orga-level map exists but has no data to display
