# Materials Database Target-State Plan

- **Status**: In progress
- **Date**: 2026-04-14
- **Last updated**: 2026-04-28
- **Source**: `Target report 1.2_R1_Database structure_TUHH.docx`
- **Scope**: `materials` app database structure and immediate cross-app dependencies

## Documentation Boundary

This document is the single authoritative roadmap for the materials module target state. Use it for sequencing, remaining gaps, and completion criteria.

Related records remain supporting constraints, not parallel materials roadmaps:

- [Property unification current state and remaining work](2026-03-25_property_unification_current_state_and_remaining_work.md)
- [Unified unit handling](2025-02-06_unified_unit_handling.md)

## 1. Target State

The materials module should support the report's five core capabilities:

- **Recursive material structure**
  Materials can be decomposed into sub-materials without forcing every dataset into one fixed granularity.
- **Separate semantic definitions**
  Stored source-facing material/component terms can link to curated definitions and external references without rewriting source labels.
- **Sample-owned measurements**
  Component and property measurements belong directly to a concrete sample and carry unit, basis, method, and provenance where available.
- **Property definitions separate from values**
  `MaterialProperty` defines meaning and allowed units; value rows store actual observations.
- **Raw-first component observations**
  `ComponentMeasurement` is the canonical stored representation for new component data. Normalized compositions are derived on demand, with persisted normalized rows kept only as bounded compatibility storage.

## 2. Current State

Already aligned:

- `MaterialProperty(PropertyBase)` follows BRIT's domain-owned property architecture.
- `MaterialPropertyValue` stores unit, basis, analytical method, sources, and now belongs directly to `Sample`.
- `ComponentMeasurement` stores raw component measurements per sample.
- `materials.composition_normalization` derives normalized composition output from raw `ComponentMeasurement` rows only.
- `SampleDetailView`, `SampleModelSerializer`, `SampleAPISerializer`, `CompositionAPISerializer`, SimuCF reads, and sample/sample-series component lists use the shared raw-first normalization path where currently feasible.
- Excel sample measurement export is covered by tests as a raw `ComponentMeasurement` export boundary.

Still not aligned:

- `BaseMaterial` has aliases but no recursive decomposition relation.
- There is no dedicated semantic definition/reference-mapping layer for materials/components.
- `Composition` still exists as mixed settings/compatibility infrastructure.
- Existing datasets have been backfilled on dev and production; post-backfill reports and spot checks should be retained as cleanup evidence.

## 3. Implementation Status by Phase

| Phase | Status | Notes |
|---|---|---|
| Phase 0 - Baseline and safety | Complete enough | Existing tests and regression coverage protect the migration path. |
| Phase 3 - Measurement ownership | Complete | `MaterialPropertyValue.sample` is authoritative; legacy `Sample.properties` was removed. |
| Phase 4a - Shared normalization | Complete enough | Shared helper derives normalized composition output from raw `ComponentMeasurement` rows with structured warning codes. |
| Phase 4b - Consumer migration/write constraints | Complete | Primary read surfaces use the shared raw-first helper; legacy normalized-composition write surfaces were removed. |
| Phase 5 - Compatibility cleanup | Complete for `WeightShare` | Production backfill was completed; `WeightShare` runtime code, commands, forms, serializers, views, tests, and database table removal migration were removed. |
| Phase 1 - Recursive hierarchy | Not started | Should be additive and source-facing first. |
| Phase 2 - Semantic definition layer | Not started | Should wait for a concrete consumer and governance rules. |

## 4. Decisions and Guardrails

- **Keep raw source labels intact**
  Do not rewrite imported material/component/property labels into canonical terms. Use links/mappings instead.
- **Do not introduce a universal measurement table**
  Materials-specific semantics such as `basis_component` and `analytical_method` should remain explicit.
- **Treat `Composition` as settings infrastructure**
  `Composition` remains for group order and `fractions_of`; normalized values are derived from raw measurements.
- **Add hierarchy and semantic definitions only additively**
  Neither should block completion of the raw-first measurement path.

## 5. Current Raw-First Implementation Status

The raw-first component-measurement transition is complete for `WeightShare` removal:

- The legacy backfill was tested on dev and run on production.
- `ComponentMeasurement` is the only runtime source for normalized component shares.
- `WeightShare` compatibility commands, forms, views, serializers, admin registration, and tests were removed.
- A migration drops the `WeightShare` table.
- `Composition` remains as settings infrastructure for group order and `fractions_of`.

Remaining work belongs to later target-state phases rather than `WeightShare` compatibility cleanup.

## 6. Later Target-State Work

After the raw-first path is stable:

1. **Recursive hierarchy**
   - Add a relation model rather than a single parent FK.
   - Prevent cycles and duplicate sibling relations.
   - Keep it attached to source-facing material records first.

2. **Semantic definitions and references**
   - Define ownership, review permissions, merge/split behavior, and reference vocabulary rules.
   - Add definition/reference models without deleting existing comparable aliases.
   - Backfill comparable chains only after the model has proven useful.

3. **MaterialProperty unit cleanup**
   - Review whether `MaterialProperty.unit` should remain only as a compatibility label while `allowed_units` and value-level `unit` stay authoritative.

## 7. Definition of Done

The materials module is aligned with the report when:

- materials can be represented hierarchically at multiple levels of detail
- stored material records can point to separate semantic definition nodes and external references
- each material property measurement belongs directly to one sample
- raw component measurements are the canonical stored representation for new component observation data
- normalized compositions are derived on demand rather than manually curated as primary truth
- UI/API/import/export workflows use canonical raw measurement paths
- `Composition` is documented and implemented as settings/helper infrastructure
