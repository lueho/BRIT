# Materials Database Target-State Plan

- **Status**: Proposed
- **Date**: 2026-04-14
- **Source**: `Target report 1.2_R1_Database structure_TUHH.docx`
- **Scope**: `materials` app database structure and its immediate cross-app dependencies

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
- `Sample` and `SampleSeries` already carry much of the sampling context
- `BaseMaterial` supports comparable aliases for components, but not a real recursive hierarchy
- there is no separate semantic definition layer for materials/components yet
- legacy normalized composition storage (`Composition` + `WeightShare`) is still an active first-class structure
- `MaterialPropertyValue` is still attached to `Sample` through `Sample.properties` as a many-to-many relation instead of belonging directly to one sample

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
  - `MaterialProperty` already exists as the concrete materials property table
- **Value-level measurement metadata**
  - `MaterialPropertyValue` already includes `unit`, `basis_component`, `analytical_method`, and `sources`
- **Raw measurement storage**
  - `ComponentMeasurement` already stores raw per-sample component measurements with unit, basis, method, and sources
- **Sampling context**
  - `SampleSeries` and `Sample` already capture material, timesteps, dates, location text, laboratory context, and sources
- **Term harmonization bridge**
  - `comparable_component` and `comparable_property` already support canonical alias mapping for equivalent raw terms

### 3.2 Not yet aligned with the report

- **No recursive material hierarchy**
  - `BaseMaterial` has no parent/child decomposition relation
- **No separate semantic definition layer**
  - there is no dedicated model for semantic definitions or external reference mappings
- **Property values do not directly belong to one sample**
  - `MaterialPropertyValue` is linked through `Sample.properties` many-to-many instead of a direct foreign key
- **Legacy normalized composition storage is still primary in many code paths**
  - `Composition` and `WeightShare` remain central to views, serializers, and APIs
- **No on-the-fly normalization service is the canonical read path yet**
  - derived normalized views are not yet the main abstraction

## 4. Gap Summary

| Report goal | Current BRIT state | Gap to close |
|---|---|---|
| Recursive material decomposition | No explicit material hierarchy | Add recursive decomposition model and update queries/UI |
| Stored material separate from semantic definition | Alias-only canonical mapping on material/property terms | Add dedicated semantic definition and reference-mapping models |
| Measurement belongs to sample with provenance | `ComponentMeasurement` does; `MaterialPropertyValue` does not | Move `MaterialPropertyValue` to direct sample ownership |
| Property definition separated from value | Largely present already | Harden unit/basis authority and reduce legacy fallback behavior over time |
| Raw-first storage, normalized on demand | Raw component measurement exists, but legacy normalized storage is still active | Make raw measurement canonical and shift normalized compositions to derived/compatibility status |

## 5. Recommended BRIT Implementation Strategy

### 5.1 Preserve the current BRIT architecture direction

The plan should stay consistent with the existing BRIT property architecture.

Keep:

- `utils.properties` as the shared behavior layer
- `MaterialProperty` as the materials-owned concrete property table
- materials-specific fields such as `basis_component` and `analytical_method`

Do not attempt:

- a universal concrete property table for all domains
- a generic cross-domain measurement table that hides materials-specific semantics

### 5.2 Prefer additive migrations before destructive cleanup

The safest route is:

- introduce new models and read paths first
- backfill data
- switch forms/views/importers/serializers to the new path
- only then retire superseded schema pieces

### 5.3 Keep raw source labels intact

The report explicitly values storing data as found. That means:

- raw imported material/component/property names should remain unchanged
- semantic harmonization should happen through separate links, not by overwriting imported labels

### 5.4 Treat legacy normalized composition as compatibility, not truth

`Composition` and `WeightShare` can remain temporarily, but the long-term direction should be:

- write raw measurements first
- derive normalized compositions when needed for analysis or export
- progressively reduce direct write dependencies on normalized-only models

## 6. Phased Delivery Plan

## Phase 0 - Baseline and migration safety

Goal: make later schema changes low-risk and observable.

Deliverables:

- inventory all write paths that touch:
  - `Sample.properties`
  - `Composition`
  - `WeightShare`
  - `ComponentMeasurement`
  - `MaterialPropertyValue`
- inventory all read paths that assume normalized composition is the primary representation
- add focused regression tests around:
  - sample detail rendering
  - serializers/API payloads
  - import paths
  - filter behavior
  - duplication behavior for samples and sample series
- document current data volumes and nullability assumptions before schema migrations

Why first:

- later phases will change ownership and read semantics
- the plan needs stable regression coverage before changing central models

## Phase 1 - Introduce recursive material structure

Goal: let materials be decomposed across multiple levels of detail.

Recommended model direction:

- add an explicit decomposition relation for `BaseMaterial`
- prefer a dedicated relation model over a single self-FK if the same child may reasonably appear in multiple parent contexts

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

## Phase 2 - Add semantic definition and reference mapping

Goal: separate stored material entries from their semantic meaning.

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
- once all call sites are migrated, remove or deprecate `Sample.properties`

Optional follow-up in the same phase:

- evaluate whether geospatial context needs a dedicated field beyond `Sample.location`
- only add GIS-specific structure if there is a real downstream consumer

Success criteria:

- every `MaterialPropertyValue` belongs to exactly one sample
- sample detail pages and APIs use direct reverse relations instead of many-to-many indirection
- provenance remains explicit at sample and measurement level

## Phase 4 - Make raw measurements the canonical composition source

Goal: shift the primary truth from normalized `WeightShare` storage to raw component measurements.

Recommended direction:

- `ComponentMeasurement` becomes the canonical persisted representation for component-level observations
- normalized compositions become a derived read model

Implementation steps:

- introduce a normalization service/helper layer that can:
  - collect raw component measurements for a sample and group
  - normalize them to fractions or percentages on demand
  - expose warnings when normalization is partial or assumptions are required
- add read-side helpers/serializers for normalized composition output without requiring `WeightShare` writes
- migrate views currently reading `Composition`/`WeightShare` to use the derived normalization path where feasible
- restrict creation of new `WeightShare` data to compatibility workflows only
- once the new path is stable, stop treating `WeightShare` as the authoritative storage model

Data strategy:

- do not delete legacy composition rows in the first migration wave
- keep them available for comparison and rollback during transition
- only plan retirement after all primary reads and writes have been migrated

Success criteria:

- incomplete raw data can be stored without forcing a 100% composition
- normalized compositions are still available for analysis/export
- normalized output is derived rather than manually curated as the primary truth

## Phase 5 - Compatibility cleanup

Goal: remove superseded structures once new paths are stable.

Candidate cleanup items:

- deprecate and then remove `Sample.properties`
- reduce direct UI/API dependence on `Composition` and `WeightShare`
- decide whether `Composition`/`WeightShare` remain as a legacy compatibility layer or can be retired fully
- review whether `MaterialProperty.unit` should remain only as a compatibility label while `allowed_units` and value-level `unit` stay authoritative

Only do this phase when:

- migrated read/write paths are fully covered by tests
- import/export paths use the new canonical model
- existing datasets have been backfilled and spot-checked

## 7. Suggested Delivery Order

| Order | Phase | Reason |
|---|---|---|
| 1 | Phase 0 - baseline and safety | protects all later schema work |
| 2 | Phase 3 - measurement ownership | highest semantic mismatch with the report and relatively self-contained |
| 3 | Phase 4 - raw-first normalization | central report requirement and closely related to Phase 3 |
| 4 | Phase 1 - recursive hierarchy | important, but can be introduced additively once the measurement path is safer |
| 5 | Phase 2 - semantic definition layer | valuable but can build on the already improved structural base |
| 6 | Phase 5 - cleanup | only after new paths are proven |

Notes on ordering:

- Phase 1 and Phase 2 can be swapped if a concrete dataset urgently needs semantic mapping before hierarchical decomposition.
- Phase 3 should happen before major API or import work that expands property-value usage further.
- Phase 4 should not start until Phase 0 has identified all normalized-composition dependencies.

## 8. Non-Goals

This plan should explicitly avoid the following mistakes.

- **Do not rewrite imported source labels into canonical terms**
  - keep source-faithful labels and map semantics separately
- **Do not force a single universal property/value table**
  - materials-specific semantics should remain explicit
- **Do not require every dataset to provide a full normalized composition**
  - incomplete raw measurements must remain storable
- **Do not remove legacy composition models before derived normalization is production-ready**
  - compatibility comes after stable read migration, not before
- **Do not introduce GIS complexity without a concrete consumer**
  - `Sample.location` may remain sufficient until a real geospatial requirement appears

## 9. Definition of Done for the Target State

The materials module can be considered aligned with the report once all of the following are true.

- materials can be represented hierarchically at multiple levels of detail
- stored material records can point to separate semantic definition nodes and external references
- each material property measurement belongs directly to one sample
- raw component measurements are the canonical stored representation for component composition data
- normalized compositions are derived on demand instead of being the primary truth
- current UI/API/import workflows use the new canonical paths
- any remaining legacy structures are clearly marked as compatibility-only or retired

## 10. Immediate Next Step

If work should start now, the best first implementation slice is:

1. Phase 0 inventory of all `Sample.properties`, `Composition`, and `WeightShare` reads/writes
2. Phase 3 design and migration of `MaterialPropertyValue.sample`
3. regression tests for sample detail, duplication, serializers, and imports

That slice is the smallest high-value step because it improves semantic correctness immediately and reduces later migration complexity for the raw-first measurement architecture.
