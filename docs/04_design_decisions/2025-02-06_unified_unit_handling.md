# Unified Unit Handling

- **Status**: Proposed
- **Date**: 2026-02-06
- **Context**: The project has grown organically, resulting in at least five different patterns for storing and referencing units alongside numeric values. This inconsistency blocks cross-module comparisons, unit conversion, and normalized representations.

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
| `MaterialPropertyValue` | — (none) | Relies on `property.unit` CharField | No per-value unit; same property + different unit = separate `MaterialProperty` records |
| `ComponentMeasurement` | `unit` | `FK → Unit` | ✅ Correct: per-value unit via Unit model |
| `WeightShare` | — (none) | Implicitly dimensionless (fractions) | No unit field needed |

**Intention**: `ComponentMeasurement` follows the correct pattern. `MaterialPropertyValue` inherited a design limitation from `PropertyBase`.

### 1.3 `soilcom` — Waste collection statistics

| Model | Unit field | Type | Notes |
|---|---|---|---|
| `CollectionPropertyValue` | inherits `unit` FK from `PropertyValue` | `FK → Unit` | ✅ Correct |
| `AggregatedCollectionPropertyValue` | inherits `unit` FK from `PropertyValue` | `FK → Unit` | ✅ Correct |

**Intention**: Correctly implemented. Inherits from `PropertyValue` which uses `FK → Unit`.

### 1.4 `maps` — Region attributes

| Model | Unit field | Type | Notes |
|---|---|---|---|
| `Attribute` | `unit` | `CharField(127)` | Free-text string; same pattern as `PropertyBase` |
| `RegionAttributeValue` | — (none) | Relies on `attribute.unit` CharField | No per-value unit |
| `RegionAttributeTextValue` | — (none) | Categorical, no unit needed | — |

**Intention**: `Attribute` is essentially a parallel implementation of `PropertyBase`, also using a CharField for unit.

### 1.5 `inventories` — Algorithm parameters

| Model | Unit field | Type | Notes |
|---|---|---|---|
| `InventoryAlgorithmParameter` | `unit` | `CharField(20)` | Free-text string |
| `InventoryAlgorithmParameterValue` | — (none) | Relies on `parameter.unit` | No per-value unit |
| `InventoryAmountShare` | — (none) | Implicitly Mg/a | No unit field; unit is contextual |

**Intention**: Simple parameter storage; unit is metadata, not used for conversion.

### 1.6 `distributions` — Chart rendering

| Model/Class | Unit field | Type | Notes |
|---|---|---|---|
| `BaseDataSet` | `unit` | Python string attribute | For chart display only |
| `BaseChart` | `unit` | Python string attribute | Raises `UnitMismatchError` on string mismatch |

**Intention**: String-based unit matching for chart safety. Not stored in DB.

### 1.7 `layer_manager` — Result layers

| Model | Unit field | Type | Notes |
|---|---|---|---|
| `LayerAggregatedValue` | `unit` | `CharField(15)` | Free-text string |

### 1.8 `flexibi_nantes` — Growth distributions

- `GrowthShare` has `average`/`standard_deviation` (FloatField) but **no unit field**.
- The serializer hardcodes `"unit": "Mg/a"`.

---

## 2. Summary of Patterns

| Pattern | Where used | Count |
|---|---|---|
| **A. `FK → Unit` on value** | `PropertyValue`, `CollectionPropertyValue`, `AggregatedCollectionPropertyValue`, `ComponentMeasurement` | 4 models |
| **B. `CharField` on definition** | `PropertyBase`→`MaterialProperty`, `Attribute`, `InventoryAlgorithmParameter`, `LayerAggregatedValue` | 4+ models |
| **C. No unit field** | `MaterialPropertyValue` (inherits from definition), `RegionAttributeValue`, `InventoryAlgorithmParameterValue`, `WeightShare`, `InventoryAmountShare`, `GrowthShare` | 6+ models |
| **D. Hardcoded string** | `CompositionDoughnutChartSerializer` (`"%"`), flexibi_nantes serializer (`"Mg/a"`) | 2 serializers |
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
- **Requires PostgreSQL** — ✅ BRIT already uses PostgreSQL.

### Verdict

`django-pint-field` is a strong candidate **for new fields** where cross-unit comparison and conversion matter, particularly `ComponentMeasurement` and `MaterialPropertyValue`. However, adopting it project-wide would require significant migration effort and would be overkill for:
- Domain-specific string labels like `"% of households"` (soilcom properties)
- Hardcoded contextual units (chart rendering)
- Algorithm parameters where unit is just metadata

**Recommendation**: Use `pint` as a **conversion/validation utility** behind the existing `Unit` model, rather than replacing the entire storage layer with `django-pint-field`. This keeps migration scope manageable while gaining conversion capabilities.

---

## 4. Proposed Unified Architecture

### 4.1 Guiding Principles

1. **Single source of truth**: All units are `Unit` model instances. No more CharFields for units.
2. **Per-value unit**: Every numeric value record stores which `Unit` it was recorded in.
3. **Conversion via `pint`**: The `Unit` model gets a `pint_unit` property that maps to `pint.Unit` for conversion.
4. **Incremental migration**: Fix one model at a time; no big-bang rewrite.

### 4.2 Phase 1 (Immediate) — Fix materials value-level unit handling

Add per-value unit storage to `MaterialPropertyValue` and stop deriving value units from `MaterialProperty.unit`.

```python
class MaterialPropertyValue(UserCreatedObject):
    property = models.ForeignKey(MaterialProperty, on_delete=models.PROTECT)
    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        default=get_default_unit_pk,
        help_text="Unit for this specific measurement.",
    )
    average = models.DecimalField(max_digits=20, decimal_places=10)
    standard_deviation = models.DecimalField(max_digits=20, decimal_places=10)
```

**Data migration**:
- Populate `MaterialPropertyValue.unit` from the existing `MaterialProperty.unit` string by resolving/creating `Unit` objects.
- Add migrated units to `MaterialProperty.allowed_units` to preserve compatibility.
- Fallback to default "No unit" only when source data is blank/unresolvable.

**Application changes in the same phase**:
- Update serializers/templates to use `value.unit` instead of `property.unit`.
- Update forms to expose/select `MaterialPropertyValue.unit`.
- Enforce that selected value unit is in `property.allowed_units` (or explicitly auto-add according to a documented policy).
- Update importer `get_or_create` keys for `MaterialPropertyValue` to include `unit`.
- Define explicit import semantics for percent-like units (`%`, `%DM`, `%FM`) to avoid ambiguous scaling between `20` and `0.2`:
  - Store percent-like measurements as **percent points** exactly as provided (`20` stays `20`, `0.2` stays `0.2`).
  - Accept `%` suffixes in numeric cells only for percent-like units (`"20%"` + `%` is valid and stored as `20`).
  - Reject `%`-suffixed values when the declared unit is non-percent (to avoid silent mis-scaling).

**Impact**:
- Fixes current correctness issue in materials without requiring cross-module rewrites.
- Enables normalized representations for materials as the next step.

### 4.3 Phase 2 — Strengthen the `Unit` model

Add a `symbol` field to `Unit` for `pint` integration:

```python
# utils/properties/models.py

class Unit(NamedUserCreatedObject):
    dimensionless = models.BooleanField(default=False, null=True)
    symbol = models.CharField(
        max_length=63,
        blank=True,
        help_text="Pint-compatible unit symbol (e.g. 'kg', 'mg/L', 'percent').",
    )
    reference_quantity = models.ForeignKey(...)

    @cached_property
    def pint_unit(self):
        """Return a pint.Unit for conversion, or None if not mappable."""
        if not self.symbol:
            return None
        try:
            return ureg.Unit(self.symbol)
        except pint.UndefinedUnitError:
            return None

    def convert(self, value, target_unit):
        """Convert a numeric value from this unit to target_unit."""
        if self.pint_unit is None or target_unit.pint_unit is None:
            raise UnitConversionError(f"Cannot convert {self} → {target_unit}")
        quantity = ureg.Quantity(value, self.pint_unit)
        return quantity.to(target_unit.pint_unit).magnitude
```

Add a project-level `pint` registry with custom unit definitions:

```python
# utils/properties/units.py

import pint

ureg = pint.UnitRegistry()

# Custom units for the BRIT domain
ureg.define("percent = 0.01 * count = %")
ureg.define("permille = 0.001 * count = ‰")
ureg.define("dry_matter_basis = [] = DM")
```

### 4.4 Phase 3 (Deferred) — Migrate `PropertyBase.unit` CharField → FK to Unit

Replace the inherited CharField with an FK:

```python
class PropertyBase(NamedUserCreatedObject):
    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        default=get_default_unit_pk,
        help_text="Default display unit for this property.",
    )
    class Meta:
        abstract = True
```

**Data migration**: For each existing `MaterialProperty` and `Property`, look up or create a `Unit` matching the current CharField value, then update the FK.

**Risk note**: In this codebase this phase is **high risk** because it affects `utils/properties` and downstream consumers (especially `soilcom`) that currently assume string-based property units in tests/forms.

**Impact**: `MaterialProperty`, `Property` (base), and all inheritors switch from string to FK. The `allowed_units` M2M remains and gains real purpose: it defines which units are valid for values of this property.

### 4.5 Phase 4 — Unify `maps.Attribute` with `Property`

`Attribute` + `RegionAttributeValue` is a parallel implementation of `Property` + `PropertyValue`. Options:

- **Option A**: Make `Attribute` extend `PropertyBase` (now with FK unit) and `RegionAttributeValue` extend `PropertyValue`. This unifies the models without breaking the maps app.
- **Option B**: Replace `Attribute`/`RegionAttributeValue` with `Property`/a concrete `PropertyValue` subclass. More disruptive but eliminates duplication.

Recommended: **Option A** — least disruptive, achieves unit consistency.

### 4.6 Phase 5 — Address remaining CharField units

| Model | Action |
|---|---|
| `InventoryAlgorithmParameter.unit` | Replace with `FK → Unit` |
| `LayerAggregatedValue.unit` | Replace with `FK → Unit` |
| Hardcoded strings in serializers | Replace with `unit.name` lookups |
| `BaseChart`/`BaseDataSet.unit` | Change to accept `Unit` instances; compare by `pk` instead of string equality |

### 4.7 Phase 6 — Conversion & Normalization API

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
| **1. Materials value-unit correction** | `materials` app (`MaterialPropertyValue.unit`, serializer/template/importer/form updates) | Medium | None (reuses existing `Unit` model) |
| **2. Unit model + pint** | `utils/properties` only | Low | Add `pint` to dependencies |
| **3. PropertyBase.unit → FK** | All `PropertyBase` inheritors | High | Phases 1-2; data migration for `MaterialProperty`, `Property`; compatibility updates in `soilcom` and related tests/forms |
| **4. Attribute → PropertyBase** | `maps` app | Medium | Phase 3 |
| **5. Remaining CharFields** | `inventories`, `layer_manager` | Low | Phase 2 |
| **6. Conversion API** | `utils/properties` | Low | Phases 1-3 |

Each phase is independently deployable with its own migration and can be tested in isolation.

---

## 6. What NOT to do

- **Don't adopt `django-pint-field` wholesale**. It replaces the entire field type with a PostgreSQL composite, which is invasive and doesn't fit domain-specific units like `"% of households"` or `"kg/(cap.*a)"`. Use `pint` as a library behind the `Unit` model instead.
- **Don't merge `Composition`/`WeightShare` into this effort**. That's a separate architectural concern (measurement unification). Unit handling should be fixed first as a prerequisite.
- **Don't remove `allowed_units` M2M**. It will become useful once `PropertyBase.unit` is an FK — it defines valid units for a property definition.
- **Don't keep rendering/serializing material property value units from `property.unit`** once Phase 1 is implemented; use `value.unit` consistently.
- **Don't leave percent import semantics implicit**; document and test whether incoming `%` values are expected as `20` or `0.2`.

---

## 7. Dependency Addition

Add to `pyproject.toml`:

```toml
"pint>=0.23",
```

`pint` is a pure Python library with no binary dependencies, well-established (2.7k stars, maintained since 2012), and used extensively in the scientific Python ecosystem.
