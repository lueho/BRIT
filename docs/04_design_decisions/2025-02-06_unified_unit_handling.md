# Unified Unit Handling

- **Status**: In progress
- **Date**: 2026-02-06
- **Last updated**: 2026-04-14
- **Context**: The project has grown organically, resulting in multiple patterns for storing and referencing units alongside numeric values. This inconsistency blocks cross-module comparisons, unit conversion, and normalized representations. Parts of the original proposal in this document have since been implemented, so this record now distinguishes current state from remaining work.

## Documentation Boundary

- **This ADR covers unit handling only**
  It documents unit-model direction, value-level unit storage, and remaining cleanup around unit representation.

- **The materials roadmap is consolidated elsewhere**
  Use [Materials database target-state plan](2026-04-14_materials_database_target_state_plan.md) as the single authoritative roadmap for the materials module. Use [Property unification current state and remaining work](2026-03-25_property_unification_current_state_and_remaining_work.md) only for the cross-domain property architecture constraints that the materials roadmap must respect.

---

## 1. Current State: Unit Handling Inventory

### 1.1 `utils/properties` — Central infrastructure

| Model | Unit field | Type | Notes |
|---|---|---|---|
| `PropertyBase` (abstract) | `unit` | `CharField(63)` | Free-text string; inherited by all property definitions |
| `Unit` | — (is the unit) | Dedicated model | `unique_together = [owner, name]`; has `dimensionless` flag and optional `reference_quantity` FK |
| `Property` | inherits `unit` CharField | + `allowed_units` M2M → `Unit` | Both a string and a relation to Unit objects |
| `PropertyValue` (abstract) | `unit` | `FK → Unit` | Per-value unit; correct pattern |

**Intention**: `Unit` was designed to be the single source of truth for units. `PropertyValue` correctly uses it. But `PropertyBase.unit` CharField predates the `Unit` model and was never migrated.

### 1.2 `materials` — Two parallel measurement paths

| Model | Unit field | Type | Notes |
|---|---|---|---|
| `MaterialProperty` | inherits `unit` CharField | + `allowed_units` M2M → `Unit` | `__str__` uses CharField; `allowed_units` is populated by importer but not consistently enforced in forms/serialization |
| `MaterialPropertyValue` | `unit` | `FK → Unit` | Per-value unit is now implemented; basis and analytical-method metadata remain materials-specific |
| `ComponentMeasurement` | `unit` | `FK → Unit` | Correct: per-value unit via Unit model |
| `WeightShare` | — (none) | Implicitly dimensionless (fractions) | No unit field needed |

**Current position**: `materials` now has value-level units for both `MaterialPropertyValue` and `ComponentMeasurement`. Remaining materials work is mostly about reducing legacy fallback to definition-level unit labels and keeping read/write paths consistent.

### 1.3 `soilcom` — Waste collection statistics

| Model | Unit field | Type | Notes |
|---|---|---|---|
| `CollectionPropertyValue` | inherits `unit` FK from `PropertyValue` | `FK → Unit` | Correct |
| `AggregatedCollectionPropertyValue` | inherits `unit` FK from `PropertyValue` | `FK → Unit` | Correct |

**Intention**: Correctly implemented. Inherits from `PropertyValue` which uses `FK → Unit`.

### 1.4 `maps` — Region attributes

| Model | Unit field | Type | Notes |
|---|---|---|---|
| `Attribute` | `unit` | `CharField(127)` | Legacy quantitative definition kept during the `RegionProperty` rollout |
| `RegionProperty` | `unit` | `CharField(127)` | Maps-owned quantitative property definition extending `PropertyBase` |
| `RegionAttributeValue` | `unit` | `FK → Unit` | Per-value unit now exists; numeric values point to `RegionProperty` |
| `RegionAttributeTextValue` | — (none) | Categorical, no unit needed | — |

**Current position**: maps already has a value-level `Unit` FK on numeric values and a maps-owned `RegionProperty` definition model. Remaining maps work is compatibility cleanup and further reduction of dependence on legacy definition-level unit strings.

### 1.5 `inventories` — Algorithm parameters

| Model | Unit field | Type | Notes |
|---|---|---|---|
| `InventoryAlgorithmParameter` | `unit` | `CharField(20)` | Free-text string |
| `InventoryAlgorithmParameterValue` | — (none) | Relies on `parameter.unit` | No per-value unit |
| `InventoryAmountShare` | — (none) | Implicitly Mg/a | No unit field; unit is contextual |
| `GrowthShare` | — (none) | No unit field | Serializer hardcodes `"unit": "Mg/a"` |

---

## 2. Summary of Patterns

| Pattern | Where used | Count |
|---|---|---|
| **A. `FK → Unit` on value** | `PropertyValue`, `CollectionPropertyValue`, `AggregatedCollectionPropertyValue`, `MaterialPropertyValue`, `ComponentMeasurement`, `RegionAttributeValue` | several active models |
| **B. `CharField` on definition** | `PropertyBase` descendants such as `MaterialProperty`, legacy `Attribute`, `RegionProperty`, `InventoryAlgorithmParameter`, `LayerAggregatedValue` | still widely used |
| **C. No unit field** | `WeightShare`, `InventoryAmountShare`, `GrowthShare`, categorical value models, and value models that still inherit unit implicitly from their definitions | still present in selected places |
| **D. Hardcoded string** | `CompositionDoughnutChartSerializer` (`"%"`), greenhouse serializer (`"Mg/a"`) | 2 serializers |
| **E. Python string matching** | `BaseChart.add_dataset()`, `UnitMismatchError` | 1 module |

---

## 3. Third-Party Package Evaluation

### `pint` (Python library, 2.7k GitHub stars)
- **Mature**: actively maintained since 2012, used in scientific Python ecosystem.
- Handles unit parsing, conversion, dimensional analysis.
- Supports custom unit definitions.
- Pure Python, no DB dependency.

### `django-pint-field` (Django integration for pint)
- **Actively maintained**: latest release 2025.10.2, Django 4.2+ / Python 3.11+.
- Uses PostgreSQL composite fields to store magnitude + unit + base-unit value.
- Supports Django ORM lookups (`__gte`, `__lte`, `__range`) across different units.
- Built-in aggregation (`PintAvg`, `PintSum`, etc.).
- DRF integration included.
- **Requires PostgreSQL** — BRIT already uses PostgreSQL.

### Verdict

`django-pint-field` remains a strong candidate **for greenfield fields** where cross-unit comparison and conversion matter. However, adopting it project-wide would require significant migration effort and would be overkill for:
- Domain-specific string labels like `"% of households"` (soilcom properties)
- Hardcoded contextual units (chart rendering)
- Algorithm parameters where unit is just metadata

**Recommendation**: Continue using `pint` as a **conversion/validation utility** behind the existing `Unit` model, rather than replacing the entire storage layer with `django-pint-field`. This direction is already partially implemented through `Unit.symbol`, `Unit.pint_unit`, and `Unit.convert()`.

---

## 4. Current Direction and Remaining Roadmap

### 4.1 Guiding Principles

1. **Single source of truth**: All units are `Unit` model instances. No more CharFields for units.
2. **Per-value unit**: Every numeric value record stores which `Unit` it was recorded in.
3. **Conversion via `pint`**: The `Unit` model gets a `pint_unit` property that maps to `pint.Unit` for conversion.
4. **Incremental migration**: Fix one model at a time; no big-bang rewrite.

### 4.2 Implemented foundation

The following parts of the original proposal are already implemented in the current codebase:

- **Materials value-level units**
  - `MaterialPropertyValue.unit` now exists as `FK → Unit`
- **Unit model strengthening**
  - `Unit.symbol` now exists
  - `Unit.pint_unit` and `Unit.convert()` now exist
- **Maps numeric value-level units**
  - `RegionAttributeValue.unit` now exists as `FK → Unit`
  - maps numeric values now point to `RegionProperty` instead of the older `Attribute` path

These changes mean the main remaining unit-handling work is no longer the initial introduction of per-value units in `materials`, but rather consistency cleanup and further migration away from legacy definition-level strings.

### 4.3 Remaining roadmap — definition-level unit cleanup

The major unfinished part is that `PropertyBase.unit` and several related domain definitions still use CharFields instead of `Unit` references.

Remaining goals:

- keep `Unit` as the single conversion authority
- continue storing actual recorded units on value rows
- progressively reduce dependence on definition-level free-text unit labels
- preserve deployable, app-by-app migrations rather than forcing a big-bang rewrite

### 4.4 Remaining roadmap — import and display consistency

Even with value-level units in place, read/write paths must remain consistent.

Remaining work includes:

- ensure serializers, templates, and read helpers consistently prefer `value.unit` where available
- continue using `Unit.resolve_legacy_label()` only as a compatibility bridge, not as the long-term primary representation
- keep import semantics for percent-like units explicit and tested
- keep importer uniqueness and reconciliation logic sensitive to per-value units

### 4.5 Remaining roadmap — broader cleanup beyond materials

| Model | Action |
|---|---|
| `PropertyBase.unit` descendants | decide whether to migrate to `FK → Unit` or keep as compatibility labels |
| legacy maps `Attribute.unit` | retire after `RegionProperty` rollout is complete |
| `InventoryAlgorithmParameter.unit` | replace with `FK → Unit` if conversion or validation becomes important |
| `LayerAggregatedValue.unit` | replace with `FK → Unit` if it needs shared conversion behavior |
| Hardcoded strings in serializers | replace with `unit.name` lookups or explicit compatibility helpers where appropriate |
| `BaseChart`/`BaseDataSet.unit` | evaluate whether these should accept `Unit` instances instead of relying only on string equality |

### 4.6 Conversion and normalization helpers

Once all units flow through the `Unit` model, add utility functions:

```python
# utils/properties/conversion.py

def normalize_value(value, from_unit, to_unit):
    """Convert a numeric value between Unit instances."""
    return from_unit.convert(value, to_unit)

def values_in_common_unit(queryset, unit_field="unit", value_field="average"):
    """Convert all values in a queryset to a common base unit."""
    ...
```

This enables:
- Cross-unit comparisons in views and reports
- Normalized representations (e.g., all weights in kg)
- Aggregation of measurements recorded in different units

---

## 5. Migration Strategy

| Phase | Scope | Risk | Dependencies |
|---|---|---|---|
| **Implemented: materials value-level units** | `materials` app (`MaterialPropertyValue.unit`, serializer/template/importer/form updates) | Completed | Reused existing `Unit` model |
| **Implemented: Unit model + pint foundation** | `utils/properties` | Completed | `pint` integration and conversion helpers now exist |
| **Implemented: maps value-level units** | `maps` app (`RegionAttributeValue.unit`, `RegionProperty`) | Completed / in rollout cleanup | Legacy `Attribute` compatibility remains |
| **Remaining: definition-level unit cleanup** | `PropertyBase` inheritors and compatibility layers | High | Depends on downstream consumers no longer relying on string labels |
| **Remaining: other CharField unit domains** | `inventories`, `layer_manager`, remaining serializer/chart paths | Medium | Can proceed incrementally |
| **Remaining: broader conversion/query API** | `utils/properties` | Low-Medium | Depends on how many consumers need shared conversion workflows |

Each phase is independently deployable with its own migration and can be tested in isolation.

---

## 6. What NOT to do

- **Don't adopt `django-pint-field` wholesale**. It replaces the entire field type with a PostgreSQL composite, which is invasive and doesn't fit domain-specific units like `"% of households"` or `"kg/(cap.*a)"`. Use `pint` as a library behind the `Unit` model instead.
- **Don't merge `Composition`/`WeightShare` into this effort**. That's a separate architectural concern from unit handling and should stay tracked in the materials roadmap rather than in this ADR.
- **Don't remove `allowed_units` M2M**. It remains useful regardless of whether `PropertyBase.unit` eventually becomes an FK, because it defines which units are valid for a property definition.
- **Don't keep rendering or serializing material property value units from `property.unit`** where a value-level `unit` exists; use `value.unit` consistently.
- **Don't leave percent import semantics implicit**; document and test whether incoming `%` values are expected as `20` or `0.2`.

---

## 7. Dependency Note

`pint` is already part of the implemented direction behind the `Unit` model. If this document is used to guide future environment or dependency refactors, keep `pint` available in project dependencies.

`pint` is a pure Python library with no binary dependencies, well-established, and used extensively in the scientific Python ecosystem.
