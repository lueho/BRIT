# Materials Database Target-State Plan

- **Status**: In progress
- **Date**: 2026-04-14
- **Last updated**: 2026-04-27
- **Source**: `Target report 1.2_R1_Database structure_TUHH.docx`
- **Scope**: `materials` app database structure and its immediate cross-app dependencies

## Documentation Boundary

- **This document is the single authoritative roadmap for the materials module**
  It owns the sequencing, target state, gaps, implementation strategy, and definition of done for materials-related schema and workflow changes.

- **Related ADRs remain supporting architecture records, not parallel roadmap documents**
  Use [Property unification current state and remaining work](2026-03-25_property_unification_current_state_and_remaining_work.md) for cross-domain property-architecture constraints and [Unified unit handling](2025-02-06_unified_unit_handling.md) for unit-handling constraints that this roadmap must respect.

## 1. Context

The referenced report describes the intended target state of the BRIT materials data model for CLOSECYCLE. The key architectural ideas are:

- separate the stored material record from its semantic definition
- support recursive material decomposition at varying levels of detail
- store measurements together with sampling and provenance context
- separate property definitions from measured values, with explicit unit and basis handling
- treat raw measurements as the primary representation and derive normalized compositions on demand

The current BRIT codebase already implements parts of this target state, but not all of it:

- `MaterialProperty(PropertyBase)` already follows the current BRIT direction of domain-owned concrete property tables
- `MaterialPropertyValue` already stores unit, basis, analytical method, and sources
- `ComponentMeasurement` already stores raw component measurements per sample
- the shared `materials.composition_normalization` helpers now derive normalized read output from raw component measurements with persisted-composition fallback
- `SampleDetailView`, `SampleModelSerializer`, and `SampleAPISerializer` already consume that shared normalized output
- `Sample` and `SampleSeries` already carry much of the sampling context
- `BaseMaterial` supports comparable aliases for components, but not a real recursive hierarchy
- there is no separate semantic definition layer for materials/components yet
- legacy normalized composition storage (`Composition` + `WeightShare`) is still an active first-class structure
- `MaterialPropertyValue` now belongs directly to `Sample` through `MaterialPropertyValue.sample`

This document translates the report into a repo-specific implementation plan that fits the current BRIT architecture.

## 2. Target State to Reach

The report implies five concrete capabilities for the `materials` database structure.

### 2.1 Recursive structural representation

BRIT should be able to represent materials at different levels of detail without forcing every dataset into one fixed granularity.

Target outcome:

- a material can be decomposed into sub-materials recursively
- detailed and aggregated datasets can coexist
- the structure supports aggregation and comparison across levels

### 2.2 Separate semantic definition and reference mapping

BRIT should distinguish between:

- the stored material term used by a source dataset
- the semantic definition that explains what that term means
- mappings to equivalent/internal/external reference concepts

Target outcome:

- raw source naming stays unchanged
- equivalent concepts can be aligned without rewriting source data
- external reference mappings are stored explicitly

### 2.3 Measurement context and provenance

Each measurement should remain interpretable because its context is explicit.

Target outcome:

- each value belongs to a concrete sample
- the sample links back to sample series, timing, and material
- analytical method and source provenance are attached at the value level where available
- sample-level context remains available for campaign-wide provenance

### 2.4 Property definitions with unit and basis control

Property definitions and measurement values should remain separate.

Target outcome:

- property definition controls meaning and allowed units
- value record stores observed number, actual unit, method, source, and basis
- comparisons across datasets remain explicit instead of relying on hidden assumptions

### 2.5 Raw-first storage with derived normalization

The report is explicit that the old normalized-composition-first approach should no longer be the primary storage model.

Target outcome:

- raw component measurements are the canonical persisted representation
- normalized representations are derived in BRIT when needed
- legacy normalized structures may remain temporarily for compatibility
- normalization no longer blocks ingestion of incomplete raw datasets

## 3. Current State in BRIT

### 3.1 Already aligned with the report

- **Domain-owned property definitions**
  - `MaterialProperty(PropertyBase)` already follows the current BRIT direction of domain-owned concrete property tables
  - `MaterialPropertyValue` already stores unit, basis, analytical method, and sources
  - `ComponentMeasurement` already stores raw component measurements per sample
  - `materials.composition_normalization` now provides a shared derived composition read path built from `ComponentMeasurement`
  - `SampleDetailView`, `SampleModelSerializer`, and `SampleAPISerializer` already use the shared normalized output
  - `Sample` and `SampleSeries` already carry much of the sampling context
  - `BaseMaterial` supports comparable aliases for components, but not a real recursive hierarchy
  - there is no separate semantic definition layer for materials/components yet
  - legacy normalized composition storage (`Composition` + `WeightShare`) is still an active first-class structure
  - `MaterialPropertyValue` now belongs directly to `Sample` through `MaterialPropertyValue.sample`, and the legacy `Sample.properties` path has been removed from the schema

### 3.2 Not yet aligned with the report

- **No recursive material hierarchy**
  - `BaseMaterial` has no parent/child decomposition relation
- **No separate semantic definition layer**
  - there is no dedicated model for semantic definitions or external reference mappings
- **Legacy normalized composition storage is still primary in many code paths**
  - `Composition` and `WeightShare` remain central to forms, model helpers, tests, and compatibility APIs
- **Derived normalization is shared for important reads, but raw-first is not yet the write contract**
  - `get_sample_normalized_compositions()` is now the canonical read helper for sample detail and sample serializers
  - creation/editing workflows can still create or mutate `WeightShare` rows directly
  - `Composition` is still created automatically for new samples and still mixes display/settings responsibility with persisted normalized value responsibility

## 4. Gap Summary

| Report goal | Current BRIT state | Gap to close |
|---|---|---|
| Recursive material decomposition | No explicit material hierarchy | Add recursive decomposition model and update queries/UI |
| Stored material separate from semantic definition | Alias-only canonical mapping on material/property terms | Add dedicated semantic definition and reference-mapping models |
| Measurement belongs to sample with provenance | `ComponentMeasurement` and `MaterialPropertyValue` now both belong directly to `Sample` | Preserve direct sample ownership as the canonical path and avoid reintroducing indirection in later phases |
| Property definition separated from value | Largely present already | Harden unit/basis authority and reduce legacy fallback behavior over time |
| Raw-first storage, normalized on demand | Shared derived normalization exists for sample detail and sample serializers, but persisted normalized structures still dominate write forms, model helpers, and compatibility APIs | Finish read-consumer migration, define the write contract, and shift normalized compositions to compatibility/settings status |

## 5. Critical Review and Refinements

The original plan is directionally correct, but several risks need sharper boundaries before more schema work is attempted.

### 5.1 The largest remaining risk is no longer read derivation

Phase 4a has already changed the read architecture: normalized composition output is now produced by shared helpers rather than by one view-local implementation.

The remaining architectural risk is write-side ambiguity:

- `ComponentMeasurement` is the intended raw observation store
- `Composition` still stores per-sample group settings such as order and `fractions_of`
- `WeightShare` still stores normalized values and is still created or edited by legacy workflows
- new samples still receive a default persisted composition through `add_default_composition`

Refinement:

- treat `Composition` and `WeightShare` separately from now on
- preserve `Composition` as a possible settings model until a replacement exists
- make `WeightShare` the primary compatibility target because it stores the superseded normalized values
- do not describe Phase 4 as complete until new component-level writes prefer `ComponentMeasurement` and only legacy compatibility workflows write `WeightShare`

### 5.2 The normalization helper is useful, but not yet a complete analytical contract

The current shared helper provides a necessary bridge, but it still encodes assumptions that should remain visible:

- it can assign a missing fraction to `Other`
- it chooses a reference component when multiple bases are present
- it has special handling for percent-of-dry-matter style measurements
- it may fall back to persisted normalized values when raw values cannot be normalized

Refinement:

- keep warnings as part of the public read contract
- avoid silently treating derived output as laboratory truth when assumptions were needed
- before deeper analytical reuse, consider stable warning identifiers or structured warning metadata so exports and QA tooling do not need to parse prose strings
- do not block the current UI/API migration on that enhancement unless a concrete consumer needs it

### 5.3 Semantic definitions are valuable, but still premature as a default next step

The semantic definition layer remains justified by the report, but it would add governance and curation overhead.

Refinement:

- do not introduce `MaterialDefinition` only because it appears in the target report
- first prove a consumer that needs more than `comparable_component` and `comparable_property`
- define ownership, review permissions, external reference vocabulary rules, and merge/split behavior before adding definition nodes

### 5.4 Recursive hierarchy should be additive and source-facing first

Recursive decomposition is useful, but it should not become an early dependency of the raw-measurement work.

Refinement:

- introduce hierarchy only after the raw-first read/write contract is stable, unless a concrete dataset requires it earlier
- use a relation model rather than a single parent FK
- prevent cycles and duplicate sibling relations in the first implementation
- keep hierarchy attached to stored source-facing material records first; only bridge to semantic definitions later if Phase 2 has a real consumer

### 5.5 Cleanup must be driven by usage evidence, not by model dislike

`Composition` and `WeightShare` are legacy-heavy but still support existing workflows and tests.

Refinement:

- do not remove either model until a usage inventory proves that all primary read/write/import/export paths use the raw-first path
- consider renaming or conceptually documenting `Composition` as settings if it remains
- disable or narrow new `WeightShare` writes before planning deletion
- produce a mismatch report between raw-derived and persisted normalized compositions before any destructive cleanup

## 6. Recommended BRIT Implementation Strategy

### 6.1 Preserve the current BRIT architecture direction

The plan should stay consistent with the existing BRIT property architecture.

Keep:

- `utils.properties` as the shared behavior layer
- `MaterialProperty` as the materials-owned concrete property table
- materials-specific fields such as `basis_component` and `analytical_method`

Do not attempt:

- a universal concrete property table for all domains
- a generic cross-domain measurement table that hides materials-specific semantics

### 6.2 Prefer additive migrations before destructive cleanup

The safest route is:

- introduce new models and read paths first
- backfill data
- switch forms/views/importers/serializers to the new path
- only then retire superseded schema pieces

### 6.3 Keep raw source labels intact

The report explicitly values storing data as found. That means:

- raw imported material/component/property names should remain unchanged
- semantic harmonization should happen through separate links, not by overwriting imported labels

### 6.4 Treat legacy normalized composition as compatibility, not truth

`Composition` and `WeightShare` can remain temporarily, but the long-term direction should be:

- write raw measurements first
- derive normalized compositions when needed for analysis or export
- progressively reduce direct write dependencies on normalized-only models

### 6.5 Adopt already-decided property architecture as a constraint, not a separate roadmap

This roadmap should treat the cross-domain property decision as settled input.

For materials work, that means:

- keep `MaterialProperty` as the materials-owned concrete property table
- keep `utils.properties` as the shared behavior layer for forms, serializers, measurement helpers, and abstract contracts
- do not treat the generic `Property` table as the long-term target for materials definitions
- do not collapse materials-specific semantics such as `basis_component` and `analytical_method` into an overly generic cross-domain value model

### 6.6 Adopt already-decided unit direction as a constraint, not a separate roadmap

This roadmap should also treat unit handling as an architectural constraint that is already partially implemented.

For materials work, that means:

- `MaterialPropertyValue.unit` is already the authoritative value-level unit field
- `allowed_units` remains the intended validation boundary for property-specific unit choice
- `MaterialProperty.unit` should be treated as a compatibility or display label unless and until a broader definition-level migration is justified
- future materials read and write paths should prefer value-level unit behavior instead of reintroducing dependence on definition-level unit strings

## 7. Phased Delivery Plan

## Phase 0 - Baseline and migration safety

Goal: make later schema changes low-risk and observable.

Phase status: complete enough for the ownership migration slice; the baseline inventory, focused regression coverage, and dev-database preservation checks were completed before and during Phase 3 rollout.

Deliverables:

- inventory all write paths that touch:
  - `Sample.properties`
  - `Composition`
  - `WeightShare`
  - `ComponentMeasurement`
  - `MaterialPropertyValue`
- inventory all read paths that assume normalized composition is the primary representation
- record current database shape before schema work, including counts for:
  - `MaterialPropertyValue` linked to zero, one, or multiple samples
  - samples that currently have persisted property values, raw component measurements, both, or neither
  - compositions that cannot be reconstructed from current raw measurements without loss
- add focused regression tests around:
  - sample detail rendering
  - serializers/API payloads
  - import paths
  - filter behavior
  - duplication behavior for samples and sample series
- produce a compatibility matrix for each major read/write surface, identifying whether it will remain persisted, become derived, or run in dual-path compatibility mode during transition
- document current data volumes and nullability assumptions before schema migrations

Why first:

- later phases will change ownership and read semantics
- the plan needs stable regression coverage before changing central models

### Phase 0 checkpoint and retrospective

- **Phase 0 delivered the minimum safety baseline for the ownership migration**
  - the main `Sample.properties` read and write paths were inventoried across models, views, filters, serializers, and tests
  - focused regression coverage was added or updated for duplication behavior, filter behavior, serializer payloads, and sample-property CRUD views
  - the migration sequence was designed additively first, then destructively, rather than removing the legacy link path up front

- **A real dev-database snapshot was recorded before the destructive step**
  - before `materials.0014_remove_sample_properties`, the dev database contained 100 samples, 160 `MaterialPropertyValue` rows, 155 rows already carrying `sample_id`, 5 rows still lacking `sample_id`, and 166 legacy join-table links in `materials_sample_properties`
  - the baseline also identified 6 extra legacy links that would require cloning rather than a simple one-row backfill

- **The destructive migration was verified against real legacy data**
  - after applying `materials.0014_remove_sample_properties` on dev, the legacy join table was gone, all 166 resulting `MaterialPropertyValue` rows had non-null `sample_id`, and all pre-existing sample-property links were preserved
  - the multi-link legacy cases were preserved by cloning value rows and copying their `sources` links where required

- **What Phase 0 taught us**
  - the main risk was not adding `MaterialPropertyValue.sample`; it was preserving ambiguous legacy ownership cases safely when removing `Sample.properties`
  - a production-safe plan for this slice needs both regression coverage and a data-preserving normalization migration, not just runtime refactors

## Phase 1 - Introduce recursive material structure

Goal: let materials be decomposed across multiple levels of detail.

Recommended model direction:

- add an explicit decomposition relation for `BaseMaterial`
- prefer a dedicated relation model over a single self-FK if the same child may reasonably appear in multiple parent contexts
- keep the first implementation slice source-facing on `BaseMaterial` rather than coupling hierarchy immediately to a future semantic-definition layer

Recommended additions:

- `MaterialRelation` or similarly named model
  - `parent_material`
  - `child_material`
  - optional relation metadata such as `order`, `note`, or relation type if needed

Implementation steps:

- add the new relation model and admin/form support
- expose hierarchy in detail views and serializers
- add query helpers for:
  - ancestors
  - descendants
  - leaf materials
- backfill nothing initially unless an existing dataset already implies hierarchy

Success criteria:

- a material can be decomposed recursively without changing imported names
- existing material CRUD remains stable

## Phase 2 - Conditional semantic definition and reference mapping

Goal: separate stored material entries from their semantic meaning when there is a concrete consumer that justifies the extra abstraction.

Start this phase only when at least one concrete consumer is defined, such as:

- search/filter behavior that must align equivalent raw terms through shared definition nodes
- export or interoperability mappings to external reference systems
- curator workflows that need explicit canonical concepts beyond `comparable_component`
- cross-dataset analytics that cannot be expressed cleanly with the current comparable-field bridge

Recommended model direction:

- add a definition-layer model such as `MaterialDefinition`
- add a mapping model such as `MaterialDefinitionReference`
- link stored materials/components to definitions via an optional foreign key

Recommended additions:

- `MaterialDefinition`
  - canonical label
  - description
  - optional broader/narrower or parent relation if needed
- `MaterialDefinitionReference`
  - definition
  - external system name
  - external identifier / URI
  - optional relation type such as exact or close match
- optional `BaseMaterial.definition`

Bridge from current state:

- treat `comparable_component` as an interim alias mechanism
- migrate comparable chains gradually toward shared definition nodes
- keep `comparable_property` for property harmonization unless/until a separate property-definition strategy is needed

Implementation steps:

- define write ownership and governance for definition nodes and external mappings before introducing new models
- introduce the new models without deleting comparable fields
- create helpers to resolve the effective canonical definition for a material/component
- update search/filter logic to prefer the definition layer where available
- backfill existing comparable chains into definition nodes only after the model is stable

Success criteria:

- raw imported terms remain visible
- equivalent material terms can be aligned through a separate semantic layer
- external mappings can be stored without overloading the material table itself

## Phase 3 - Make measurement ownership and provenance explicit

Goal: ensure each measurement record belongs to a concrete sample.

Phase status: complete for the direct-ownership slice implemented on 2026-04-20.

Recommended schema change:

- add `sample = ForeignKey(Sample, related_name="property_values", ...)` to `MaterialPropertyValue`
- treat `Sample.properties` as transitional compatibility state

Why this matters:

- the report describes measurements as embedded in sampling context
- `ComponentMeasurement` already follows that rule
- a direct `sample` foreign key makes measurement ownership explicit and queryable

Implementation steps:

- add nullable `sample` foreign key to `MaterialPropertyValue`
- backfill it from existing `Sample.properties` links
- add validation to prevent one property value from being attached to multiple samples during transition
- update forms, serializers, views, duplication logic, and imports to use `sample.property_values`
- update model helpers, serializers, views, URL resolution, duplication logic, imports, and any reverse-relation assumptions to use `sample.property_values`
- make `Sample.properties` read-only compatibility state as soon as practical
- update tests/factories to create sample-owned property values through the FK path rather than `Sample.properties.add(...)`
- once all call sites are migrated, remove or deprecate `Sample.properties`

Optional follow-up in the same phase:

- evaluate whether geospatial context needs a dedicated field beyond `Sample.location`
- only add GIS-specific structure if there is a real downstream consumer

Success criteria:

- every `MaterialPropertyValue` belongs to exactly one sample
- new writes use direct reverse relations instead of many-to-many indirection
- sample detail pages and APIs use direct reverse relations instead of many-to-many indirection
- provenance remains explicit at sample and measurement level

### Phase 3 implementation checkpoint and retrospective

- **Schema and migration outcome**
  - `materials.0013_materialpropertyvalue_sample` introduced `MaterialPropertyValue.sample`
  - `materials.0014_remove_sample_properties` normalized remaining legacy links, cloned ambiguous multi-link rows where needed, copied `sources` links for those clones, and then removed `Sample.properties`

- **Runtime outcome**
  - runtime code now treats `MaterialPropertyValue.sample` and `sample.property_values` as the authoritative ownership path
  - the temporary `m2m_changed` transition receivers are no longer needed and were removed
  - model helpers, view logic, filters, and duplication behavior were updated to stop relying on `Sample.properties` and `sample_set`

- **Verification outcome**
  - focused Dockerized Django tests passed for the materials slice after the refactor
  - the destructive migration was applied on the dev database and verified to preserve all sample-property ownership links, including the previously ambiguous multi-link legacy cases

- **Immediate consequence for the roadmap**
  - the measurement-ownership mismatch with the report is now closed
  - the next high-value work is no longer ownership design; it is completing the raw-first composition transition around remaining `WeightShare` write paths and compatibility APIs

## Phase 4 - Extract and adopt raw-first derived normalization

Goal: shift the primary truth from normalized `WeightShare` storage to raw component measurements.

Phase status: Phase 4a is complete enough for current read-side adoption. The shared helper exists in `materials.composition_normalization`, has focused regression tests, and is used by sample detail plus sample serializers. Phase 4b remains open because direct normalized-value writes and compatibility serializers still exist.

Recommended direction:

- `ComponentMeasurement` becomes the canonical persisted representation for component-level observations
- normalized compositions become a derived read model
- keep `Composition` only as settings/compatibility infrastructure unless a later replacement is introduced
- treat `WeightShare` as compatibility storage for persisted normalized values, not the preferred target for new component observations

Implementation steps:

- Phase 4a - extract a shared normalization service/helper layer that can:
  - collect raw component measurements for a sample and group
  - normalize them to fractions or percentages on demand
  - expose warnings when normalization is partial or assumptions are required
- Phase 4a - define one canonical read contract for mixed-state samples during transition:
  - resolve each composition group independently rather than switching the entire sample to either persisted-only or derived-only mode
  - if raw `ComponentMeasurement` data exists for a group, the derived normalized output for that group is authoritative
  - if a group has no raw measurements yet, fall back to persisted `WeightShare` compatibility data for that group
  - preserve ordering and `fractions_of` from `Composition` settings where available
  - if raw-derived output and persisted normalized values disagree for the same group, expose the raw-derived output as canonical and surface an explicit warning for validation/cleanup
- Phase 4a - expose one shared serializer/helper output shape for both raw-derived groups and persisted-fallback groups so UI/API consumers do not need separate code paths; if consumers need origin visibility, add explicit metadata fields instead of divergent schemas
- add dedicated tests for the shared normalization rules so view behavior and API behavior cannot drift
- Phase 4b - inventory remaining direct consumers of `Composition` and `WeightShare`, separating:
  - persisted settings use
  - persisted normalized-value read use
  - persisted normalized-value write use
  - compatibility API use
- Phase 4b - migrate remaining primary read surfaces to `get_sample_normalized_compositions()` where feasible
- Phase 4b - define the write contract for component-level observations:
  - new observation writes should target `ComponentMeasurement`
  - `WeightShare` writes should be limited to explicit compatibility/edit-legacy workflows
  - forms that still mutate `WeightShare` should label that behavior as normalized-composition compatibility
- Phase 4b - add a mismatch report or management command that compares raw-derived output with persisted fallback rows before destructive cleanup is planned
- once the new path is stable, stop treating `WeightShare` as the authoritative storage model

Data strategy:

- do not delete legacy composition rows in the first migration wave
- keep them available for comparison and rollback during transition
- keep `Composition` rows available as ordering and `fractions_of` settings while derived reads still use them
- only plan retirement after all primary reads and writes have been migrated

Success criteria:

- incomplete raw data can be stored without forcing a 100% composition
- normalized compositions are still available for analysis/export
- normalized output is derived rather than manually curated as the primary truth
- primary component-measurement creation/edit flows write `ComponentMeasurement`
- remaining `WeightShare` usage is explicitly compatibility-only

## Phase 5 - Compatibility cleanup

Goal: remove superseded structures once new paths are stable.

Candidate cleanup items:

- verify that no deferred compatibility assumptions outside the migrated materials slice still reference the retired `Sample.properties` path
- reduce direct UI/API dependence on `Composition` and `WeightShare`
- move `WeightShare` to compatibility-only status and decide later whether it can be retired fully
- decide whether `Composition` remains as a lightweight settings model for group ordering and `fractions_of` or can also be retired
- review whether `MaterialProperty.unit` should remain only as a compatibility label while `allowed_units` and value-level `unit` stay authoritative

Only do this phase when:

- migrated read/write paths are fully covered by tests
- import/export paths use the new canonical model
- existing datasets have been backfilled and spot-checked

## 8. Suggested Delivery Order

| Order | Phase | Reason |
|---|---|---|
| 1 | Phase 0 - baseline and safety | protects all later schema work |
| 2 | Phase 3 - measurement ownership | highest semantic mismatch with the report and relatively self-contained |
| 3 | Phase 4a - shared normalization service extraction | completed enough for current read-side adoption |
| 4 | Phase 4b - migrate remaining consumers and constrain writes | moves the app toward raw-first behavior without removing compatibility too early |
| 5 | Phase 1 - recursive hierarchy | important, but can be introduced additively once the measurement path is safer |
| 6 | Phase 2 - conditional semantic definition layer | should wait until a concrete consumer justifies the added abstraction and governance overhead |
| 7 | Phase 5 - cleanup | only after new paths are proven |

Notes on ordering:

- Phase 1 and Phase 2 can be swapped if a concrete dataset urgently needs semantic mapping before hierarchical decomposition.
- Phase 3 has now been completed and should be treated as a prerequisite already satisfied for later materials work.
- Phase 4a is complete enough for Phase 4b to proceed.
- Phase 4b should start with a usage inventory because direct `Composition` and `WeightShare` references still include legitimate settings behavior, legacy normalized-value behavior, and compatibility API behavior.

## 9. Non-Goals

This plan should explicitly avoid the following mistakes.

- **Do not rewrite imported source labels into canonical terms**
  - keep source-faithful labels and map semantics separately
- **Do not force a single universal property/value table**
  - materials-specific semantics should remain explicit
- **Do not require every dataset to provide a full normalized composition**
  - incomplete raw measurements must remain storable
- **Do not remove legacy composition models before derived normalization is production-ready**
  - compatibility comes after stable read migration, not before
- **Do not treat every remaining `Composition` reference as a bug**
  - some uses may remain valid as group settings until a clearer settings model exists
- **Do not introduce GIS complexity without a concrete consumer**
  - `Sample.location` may remain sufficient until a real geospatial requirement appears

## 10. Definition of Done for the Target State

The materials module can be considered aligned with the report once all of the following are true.

- materials can be represented hierarchically at multiple levels of detail
- stored material records can point to separate semantic definition nodes and external references
- each material property measurement belongs directly to one sample
- raw component measurements are the canonical stored representation for new component observation data
- normalized compositions are derived on demand instead of being the primary truth, with any temporary persisted fallback clearly bounded as compatibility-only
- current UI/API/import workflows use the new canonical paths, with any remaining compatibility surfaces clearly bounded
- if `Composition` remains, it is clearly bounded as a settings/helper model rather than the primary store of normalized truth
- if `WeightShare` remains, it is clearly bounded as legacy normalized-value compatibility storage
- any remaining legacy structures are clearly marked as compatibility-only or retired

## 11. Immediate Next Step

If work should continue now, the best next implementation slice is:

1. Phase 4b inventory of remaining `Composition` and `WeightShare` consumers, classified by settings, read, write, import/export, and compatibility API behavior
2. migrate the next primary read surfaces to `get_sample_normalized_compositions()` where they still use direct persisted normalized values
3. define and enforce the write-side boundary so new component observations use `ComponentMeasurement` while `WeightShare` writes are limited to explicit legacy compatibility workflows
4. add a raw-derived versus persisted-normalized mismatch report before planning destructive cleanup

That slice is now the smallest high-value step because the measurement-ownership path is explicit and production-safe, and the shared normalization helper already exists. The largest remaining architectural mismatch with the report is the write-side and compatibility-surface dependence on persisted normalized `WeightShare` rows.
