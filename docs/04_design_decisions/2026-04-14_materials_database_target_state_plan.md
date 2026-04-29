# Materials Database Target-State Plan

- **Status**: Phase 5 complete (raw-first transition done)
- **Date**: 2026-04-14
- **Last updated**: 2026-04-29
- **Source**: `Target report 1.2_R1_Database structure_TUHH.docx`
- **Scope**: `materials` app database structure

Related context: [Property unification](2026-03-25_property_unification_current_state_and_remaining_work.md), [Unified unit handling](2025-02-06_unified_unit_handling.md)

## 1. Target State

Five core capabilities from the source report:

| Capability | Status |
|-----------|--------|
| Recursive material structure | ⏸️ Not started (Phase 1) |
| Separate semantic definitions | ⏸️ Not started (Phase 2) |
| Sample-owned measurements | ✅ Complete |
| Property definitions separate from values | ✅ Complete |
| Raw-first component observations | ✅ Complete |

## 2. Current State

✅ **Complete:**
- `MaterialProperty(PropertyBase)` with domain-owned property architecture
- `MaterialPropertyValue` with per-value unit, basis, method, sources
- `ComponentMeasurement` as canonical raw component storage
- `materials.composition_normalization` derives normalized shares from raw measurements only
- All read surfaces use raw-first normalization path
- Excel export as raw measurement boundary

⏸️ **Not started:**
- Recursive material decomposition (Phase 1)
- Semantic definition/reference-mapping layer (Phase 2)

🗑️ **Removed:**
- `WeightShare` model, admin, forms, views, serializers, tests, and database table
- Legacy backfill and mismatch report commands

🔧 **Retained as settings:**
- `Composition` for group order and `fractions_of` configuration

## 3. Phase Status

| Phase | Status | Description |
|---|---|---|
| 0 - Baseline | Complete | Test coverage protects migration path |
| 3 - Measurement ownership | Complete | `MaterialPropertyValue.sample` authoritative |
| 4a - Shared normalization | Complete | Normalization helper uses raw `ComponentMeasurement` |
| 4b - Consumer migration | Complete | All read surfaces raw-first; legacy write surfaces removed |
| 5 - Compatibility cleanup | Complete | `WeightShare` fully removed; `Composition` retained as settings |
| 1 - Recursive hierarchy | Not started | Future work |
| 2 - Semantic definitions | Not started | Future work |

## 4. Guardrails

- Keep raw source labels intact (use mappings, not rewrites)
- Keep materials-specific semantics explicit (`basis_component`, `analytical_method`)
- `Composition` is settings infrastructure only (group order, `fractions_of`)
- Add hierarchy/semantics additively without blocking raw-first path

## 5. Raw-First Transition Summary

✅ **Complete (2026-04-29):**
- Legacy backfill completed on dev and production
- `ComponentMeasurement` is the only runtime source for normalized shares
- `WeightShare` model, admin, forms, views, serializers, tests, commands removed
- Migration `0016_delete_weightshare.py` drops the table
- `Composition` retained for group order and `fractions_of`

Remaining work: Phase 1 (recursive hierarchy) and Phase 2 (semantic definitions) when concrete consumers exist.

## 6. Future Work

1. **Recursive hierarchy** - Relation model for material decomposition
2. **Semantic definitions** - Reference-mapping layer with governance rules
3. **Unit cleanup** - Review `MaterialProperty.unit` vs `allowed_units` + value-level `unit`

## 7. Definition of Done

| Criterion | Status |
|-----------|--------|
| Hierarchical material representation | ⏸️ Pending Phase 1 |
| Semantic definition nodes and references | ⏸️ Pending Phase 2 |
| Property measurements belong to sample | ✅ Complete |
| Raw component measurements canonical | ✅ Complete |
| Normalized compositions derived on demand | ✅ Complete |
| Workflows use raw measurement paths | ✅ Complete |
| `Composition` as settings infrastructure | ✅ Complete |

_Complete for raw-first transition; remaining work tracked in Phase 1-2._
