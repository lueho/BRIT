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
- `materials.composition_normalization` derives normalized composition output from raw measurements, with persisted `WeightShare` fallback for groups without raw data.
- `SampleDetailView`, `SampleModelSerializer`, `SampleAPISerializer`, `CompositionAPISerializer`, SimuCF reads, and sample/sample-series component lists use the shared raw-first normalization path where currently feasible.
- Excel sample measurement export is covered by tests as a raw `ComponentMeasurement` export boundary.

Still not aligned:

- `BaseMaterial` has aliases but no recursive decomposition relation.
- There is no dedicated semantic definition/reference-mapping layer for materials/components.
- `Composition` still exists as mixed settings/compatibility infrastructure.
- `WeightShare` still exists as persisted normalized compatibility storage, but UI write surfaces are read-only compatibility views after the production backfill.
- Existing datasets have been backfilled on dev and production; post-backfill reports and spot checks should be retained as cleanup evidence.

## 3. Implementation Status by Phase

| Phase | Status | Notes |
|---|---|---|
| Phase 0 - Baseline and safety | Complete enough | Existing tests and regression coverage protect the migration path. |
| Phase 3 - Measurement ownership | Complete | `MaterialPropertyValue.sample` is authoritative; legacy `Sample.properties` was removed. |
| Phase 4a - Shared normalization | Complete enough | Shared helper derives normalized composition output from raw `ComponentMeasurement` rows with structured warning codes and compatibility fallback. |
| Phase 4b - Consumer migration/write constraints | Complete for current wave | Primary read surfaces use the helper where feasible; legacy normalized-composition write surfaces are blocked as read-only compatibility. |
| Phase 5 - Compatibility cleanup prep | In progress | Backfill candidate/apply command, mismatch report, telemetry, export-boundary tests, prod backfill execution, and read-only compatibility writes exist. Cleanup boundary decisions remain. |
| Phase 1 - Recursive hierarchy | Not started | Should be additive and source-facing first. |
| Phase 2 - Semantic definition layer | Not started | Should wait for a concrete consumer and governance rules. |

## 4. Decisions and Guardrails

- **Keep raw source labels intact**
  Do not rewrite imported material/component/property labels into canonical terms. Use links/mappings instead.
- **Do not introduce a universal measurement table**
  Materials-specific semantics such as `basis_component` and `analytical_method` should remain explicit.
- **Treat `Composition` and `WeightShare` separately**
  `Composition` may remain as settings infrastructure for group order and `fractions_of`; `WeightShare` is the superseded normalized-value store.
- **Do not remove compatibility storage prematurely**
  Cleanup requires read/write/import/export coverage, backfilled data, and spot checks.
- **Add hierarchy and semantic definitions only additively**
  Neither should block completion of the raw-first measurement path.

## 5. Remaining Steps to Finish the Current Raw-First Implementation

These are the missing steps before the raw-first component-measurement transition can be considered complete.

1. **Manual data-operation handoff**
   - Run the following reports in the target environment and save the outputs:
     - `python manage.py report_composition_normalization_mismatches --summary-only`
     - `python manage.py report_composition_normalization_mismatches`
     - `python manage.py report_weightshare_backfill_candidates --summary-only`
     - `python manage.py report_weightshare_backfill_candidates`
   - 2026-04-28 dev snapshot summary:
     - normalization mismatches: 0 examined samples, 0 mismatched groups
     - backfill candidates: 31 samples, 87 groups, 223 saved `WeightShare` rows
   - Backfill was successfully tested on dev and then run on production.
   - Retain the detailed report output and spot-check notes as cleanup evidence.
   - Re-run both reports after backfill. The backfill report should return zero candidates; mismatch rows are manual-review items, not automatic fixes.
   - Optional CI/manual gate commands:
     - `python manage.py report_composition_normalization_mismatches --fail-on-mismatch`
     - `python manage.py report_weightshare_backfill_candidates --fail-on-candidates`

2. **Lock down new write paths**
   - Ensure primary UI/API/import workflows for new component observations create `ComponentMeasurement`, not `WeightShare`.
   - Keep `WeightShare` read access only for explicitly bounded compatibility adapters.
   - Legacy normalized-composition UI write surfaces now return read-only responses instead of creating, editing, or deleting `WeightShare` rows.

3. **Finish import/export evidence**
   - Confirm all material import paths write sample-owned `MaterialPropertyValue` and raw `ComponentMeasurement` rows.
   - Keep the Excel export path raw-first and extend tests if additional export modes are added.

4. **Decide the compatibility model boundary**
   - Decide whether `Composition` remains as a settings model for group order and `fractions_of`.
   - Decide whether `WeightShare` should become read-only, hidden behind permissions, archived, or eventually removed.

5. **Perform cleanup only after evidence exists**
   - Retire or narrow compatibility views/API serializers only after backfill and spot checks.
   - Remove code paths only in small PRs with regression tests.

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
- UI/API/import/export workflows use canonical paths, with any remaining compatibility surfaces explicitly bounded
- `Composition`, if retained, is documented and implemented as settings/helper infrastructure
- `WeightShare`, if retained, is legacy normalized-value compatibility storage only
