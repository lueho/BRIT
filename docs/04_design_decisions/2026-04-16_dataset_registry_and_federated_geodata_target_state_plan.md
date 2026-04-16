# Dataset Registry and Federated Geodata Target-State Plan

- **Status**: Proposed
- **Date**: 2026-04-16
- **Scope**: `maps` dataset onboarding, standalone exploration, long-term federation of external geospatial data sources, and domain-level harmonized integration across incompatible datasets

## Documentation Boundary

- **This document is the single authoritative roadmap for BRIT's generic dataset onboarding and federation direction**
  It owns the target state, sequencing, gap analysis, evaluation criteria, and delivery phases for making new geodata explorable with little or no code.

- **Related records remain supporting documents, not parallel roadmaps**
  Use [Geodataset Harmonization Pipeline](2026-02-10_geodataset_harmonization_pipeline.md) for the source-type-specific harmonized ingestion architecture and [Module UX Harmonization Guideline](2026-02-09_module_ux_harmonization_guideline.md) for the broader explorer/list/detail UX constraints this roadmap should follow.

## 1. Context

A long-term BRIT goal is that a developer or administrator can make a new geospatial dataset explorable without writing new Django models, new views, new serializers, or new templates for each dataset.

The intended workflow is progressively:

- a table already exists in a database
- an admin registers it in BRIT as a `GeoDataset`
- BRIT introspects its schema and geometry metadata
- BRIT automatically provides map, table, filtering, detail, provenance, and export surfaces
- downstream modules can reference the dataset by a stable dataset identity rather than by hardcoded Python model names

The final step beyond local onboarding is federation:

- BRIT should be able to expose selected third-party datasets without physically copying them into the BRIT database first
- those datasets should still appear as normal `GeoDataset` entries in the UI
- BRIT should preserve provenance, access control, and reproducibility boundaries even when the physical data lives elsewhere

There is a second requirement beyond standalone dataset visibility: datasets of the same domain should be harmonized so they can be analyzed together.

Examples:

- German counties may each publish their own roadside-tree datasets
- all of those datasets represent the same domain, but differ in schema, semantics, units, completeness, and level of detail
- each source dataset should remain explorable on its own terms
- the responsible source-domain app should also be able to integrate them into one canonical cross-provider view for analysis and mapping

This means the target architecture needs two layers that coexist:

- a **generic dataset registry layer** for standalone registration and exploration of any one dataset
- a **domain harmonization layer** owned by the relevant source-domain app for integrating incompatible datasets of the same domain into a common analytical view

This direction is already visible in the codebase, but only partially:

- `maps.GeoDataset` already exists as user-managed metadata
- `maps/README.md` already documents a no-code generic dataset workflow
- the `maps` list/gallery UX already treats `GeoDataset` as a primary user-facing object
- the implementation still centers on `model_name` and hardcoded `GIS_SOURCE_MODELS`
- the documented metadata fields for table/geometry/display/filter configuration are not yet reflected as the authoritative runtime path in the current `GeoDataset` model
- the current generic dataset path is therefore more a design direction than a completed architecture

This document turns that direction into a concrete target-state roadmap.

## 2. Target State to Reach

The desired end state is not just “dynamic map views.” It is a general BRIT dataset registry with safe, metadata-driven exploration, optional federation, and domain-owned harmonized integrated views.

### 2.1 Dataset-first architecture

BRIT should treat datasets as first-class registered assets, independent of whether their rows come from:

- a native BRIT Django model
- a manually added PostGIS table
- a database view
- a materialized view
- a PostgreSQL foreign table
- a remote read-only database connection exposed through a controlled adapter

Target outcome:

- `GeoDataset` becomes the stable user-facing entry point
- physical storage details are implementation details behind a dataset adapter layer
- most new datasets become onboarding/configuration work, not application-code work

### 2.2 Safe schema introspection

BRIT should be able to inspect a registered dataset and derive enough metadata to render safe generic exploration surfaces.

Target outcome:

- discover geometry columns, primary keys, scalar columns, nullability, and basic types
- identify candidate display columns and filterable columns
- record SRID, geometry type, row count, and spatial extent where available
- validate that only explicitly allowed columns are exposed in the UI/API

### 2.3 One generic exploration surface

Every registered dataset should get the same baseline capabilities unless explicitly disabled.

Target outcome:

- gallery/list entry in the Maps module
- filtered table view
- filtered map view
- feature detail modal/page
- provenance/source display
- dataset metadata page with schema summary and refresh status
- export surface where policy allows it

### 2.4 Explicit provenance and reproducibility

A dataset must remain interpretable and auditable even when dynamically registered.

Target outcome:

- every `GeoDataset` records where data comes from
- BRIT distinguishes dataset identity from dataset version
- managed imports, materialized snapshots, and federated live datasets expose their freshness and reproducibility characteristics explicitly
- inventories or analyses can bind to either a stable moving dataset or a fixed snapshot, depending on the use case

### 2.5 Federation without hidden trust

External data access should be possible, but never as an opaque shortcut.

Target outcome:

- third-party datasets can be exposed through read-only federation
- the query path is bounded, audited, and metadata-driven
- BRIT knows whether a dataset is local, federated-live, or federated-cached
- admins can decide when live access is acceptable and when local snapshotting is required instead

### 2.6 Domain integration without per-dataset code

Generic exploration should be the baseline. Domain-specific logic should become optional composition on top.

Target outcome:

- source-domain apps can consume `GeoDataset` records through stable contracts
- dataset-specific plugins remain possible for advanced harmonization or domain semantics
- simple onboarding never requires a bespoke plugin
- plugins become the exception for domain intelligence, not the default for visibility

### 2.7 Domain-level harmonized integration

Datasets in the same domain should be integrable even when their raw structures differ.

Target outcome:

- each source-domain app defines the canonical analytical shape for its own domain
- provider-specific source datasets are mapped into that canonical shape through domain-owned configuration and transformation logic
- semantic differences such as column names, coded categories, or taxonomic granularity are normalized in the domain layer rather than in the generic registry core
- unit mismatches are normalized explicitly
- missing or lower-detail source data remains usable through `null` values, canonical fallback fields, or clearly documented downgraded resolution rather than being excluded entirely

### 2.8 Integrated coverage-aware domain views

For each domain, BRIT should be able to expose one integrated view that sits alongside the standalone source datasets.

Target outcome:

- users can open an integrated domain map such as “Roadside trees in Germany”
- the integrated view shows harmonized objects from all successfully integrated datasets in that domain
- regions with integrated coverage are highlighted
- regions where source datasets exist but are not yet integrated can be shown as not yet integrated
- regions with no available dataset can be shown separately from integration gaps where useful
- uncovered or not-yet-integrated regions can be grayed so users can immediately see the current analytical footprint

## 3. Principles and Constraints

### 3.1 Configuration over code

The normal path for adding a dataset should be:

- prepare or connect the data source
- register dataset metadata
- review inferred schema
- publish

Not:

- add model
- add serializer
- add filter class
- add URL route
- add template

### 3.2 Read-only by default

For physically external datasets and manually added tables, BRIT should assume read-only access unless a stronger managed-ingestion workflow exists.

### 3.3 Explicit allowlists, never open-ended introspection

Introspection should power defaults, but exposure must remain controlled.

- only approved columns become visible/filterable/exportable
- only approved geometry field is used
- only approved joins or derived expressions are queryable

### 3.4 Stable dataset identity, mutable storage backend

The user-facing identity of a dataset should survive storage refactors.

- moving from local table to materialized view should not require URL redesign
- moving from federated-live to snapshot should not break downstream references

### 3.5 Progressive enhancement

The first generic dataset experience only needs to be correct, safe, and useful.

- advanced analytics
- semantic mapping
- scheduled drift detection
- cross-dataset joins

should come after the baseline registry works reliably.

### 3.6 UX consistency with existing module direction

This roadmap should follow the existing UX guidance that the primary module entry is the main list of `GeoDataset` records, with explorer/list/detail/map patterns remaining consistent with other BRIT modules.

### 3.7 Source-domain ownership of harmonization

The generic registry layer should not try to understand the semantics of every domain.

- `maps` owns dataset registration and generic exploration
- source-domain apps own canonical domain schemas, semantic mappings, unit normalization rules, and integration logic for incompatible same-domain datasets
- cross-provider harmonization belongs to the domain app because only the domain app can define what counts as equivalence, acceptable downgrade, or required analytical minimum

### 3.8 Integration must preserve partial truth

Harmonization should not require every dataset to be equally rich.

- if one roadside-tree dataset provides species and another only genus, both can still contribute to the integrated roadside-tree view
- if one dataset provides crown diameter in centimeters and another in meters, both can still contribute after explicit normalization
- if a field is absent in a source dataset, the integrated record should carry `null` or lower-detail information rather than forcing invented values

## 4. Final-State Vision

In the final state, BRIT behaves as a geodata workbench rather than a set of hardcoded map pages.

### 4.1 What an administrator can do

An administrator can:

- register a new local PostGIS table or view as a dataset
- connect a read-only foreign table or approved remote source and register it as a dataset
- inspect inferred schema metadata in admin before publication
- choose visible columns, filterable columns, default labels, default sorting, and map styling
- attach bibliography sources, licence, provider, update cadence, and descriptive notes
- mark the dataset as:
  - local managed
  - local unmanaged
  - federated live
  - federated cached
  - snapshot/versioned

### 4.2 What a user can do

A user can:

- browse datasets in a unified list/gallery
- understand where a dataset comes from and how fresh it is
- open a map or table without knowing the underlying table name
- filter and inspect features using safe generic UI controls
- compare snapshots or versions when the dataset supports versioning
- reuse datasets in inventories or analyses through stable dataset references
- switch between individual raw/provider datasets and integrated domain views
- open a domain-wide integrated map and immediately see which regions are already analytically covered and which are not yet integrated

### 4.3 What the system knows

For each dataset BRIT knows at least:

- registry metadata
- physical backend type
- schema and geometry metadata
- provenance and bibliography references
- permissions and exposure policy
- whether the data is live, cached, or immutable
- whether the dataset is generic-only or has additional domain semantics
- whether the dataset participates in a harmonized domain integration pipeline
- what coverage status it contributes to for its declared region or regions

### 4.4 What no longer needs code changes

In the intended steady state, the following should no longer require source changes for ordinary cases:

- adding a new local table-backed map dataset
- exposing a new local view or materialized view
- changing popup/display columns
- changing filterable columns
- changing the default geometry field or label field
- attaching a new dataset to an existing region and source set

### 4.5 What still may require code changes

The roadmap should not promise magic where custom logic is genuinely needed.

Code may still be justified for:

- domain-specific harmonization pipelines
- custom write-back/editing workflows
- non-tabular remote protocols that need new connector implementations
- advanced semantic or analytical adapters
- non-generic visualizations beyond the baseline map/table/detail surfaces

### 4.6 What an integrated domain experience looks like

For a domain such as roadside trees, the final user experience should look like this:

- each county dataset remains available as its own `GeoDataset` with its own provenance and raw feature set
- the `sources.roadside_trees` domain app defines the canonical integrated roadside-tree representation
- harmonized records from all integrated county datasets become queryable together through one integrated roadside-tree surface
- a Germany-wide map can display all integrated roadside-tree objects together
- the same map can shade counties by coverage status, for example:
  - integrated
  - source dataset available but not yet integrated
  - no known dataset available

The same pattern should apply to other domains where cross-provider integration is meaningful.

## 5. Current State in BRIT

### 5.1 Already aligned with the direction

- **User-facing dataset object exists**
  - `maps.GeoDataset` already exists and is treated as a first-class object in list/gallery views
- **Maps UX already exposes datasets as a primary concept**
  - `maps_list`, `geodataset-gallery`, and owned list/gallery routes already exist
- **Admin registration exists in early form**
  - `GeoDataset` is manageable in admin
- **The codebase already documents a generic goal**
  - `maps/README.md` describes a no-code onboarding workflow via `GeoDataset`
- **Plugin-aware route composition exists elsewhere in the repo**
  - the `sources.registry` pattern shows BRIT can already move toward metadata/plugin contracts instead of hardcoded monolith coupling

### 5.2 Not yet aligned with the direction

- **Hardcoded dataset identity still dominates runtime behavior**
  - `GeoDataset.model_name` and `GIS_SOURCE_MODELS` still act as the main dataset selector
- **The documented table-introspection metadata is not yet the authoritative implementation path**
  - README describes table name / geometry field / display fields / filter fields, but the current model excerpt does not yet expose that as the completed runtime contract
- **Generic filtered map routing is incomplete**
  - generic filtered map classes exist, but the active flow still points heavily at model-bound behavior
- **No clear backend abstraction exists yet**
  - local Django models, raw tables, views, and foreign tables are not represented through one unified adapter contract
- **No federated-source governance layer exists yet**
  - there is not yet a first-class model for external connections, foreign servers, refresh policy, or query safety
- **Versioning/freshness semantics are not yet standardized across generic datasets**
  - datasets do not yet uniformly express snapshot/live/cached behavior
- **No first-class contract yet exists for domain-integrated views and coverage maps**
  - the current direction documents harmonization ideas, but the registry roadmap did not yet explicitly define how source-domain apps own same-domain integration or how integrated coverage should be surfaced to users

## 6. Gap Summary

| Goal | Current BRIT state | Gap to close |
|---|---|---|
| Dataset-first registry | `GeoDataset` exists, but still coupled to `model_name` | Make `GeoDataset` the stable registry object independent of hardcoded source-model names |
| Metadata-driven local table onboarding | Documented in README, only partially reflected in implementation | Add authoritative schema/backend metadata and dynamic query path |
| Unified exploration surfaces | List/gallery exists; generic exploration is incomplete | Deliver table/map/detail surfaces fully from dataset metadata |
| Storage-agnostic backend handling | Mostly model-centric | Add adapter layer for Django model, table, view, materialized view, foreign table |
| External federation | Not first-class | Add safe read-only federation model and operations workflow |
| Provenance and freshness semantics | Partial via existing sources and owner/publication concepts | Standardize provider, licence, update mode, snapshot/live semantics |
| Downstream stable references | Current coupling often assumes model-specific endpoints | Let consumers bind to dataset IDs/contracts rather than Python model names |
| Same-domain harmonization | Described in a separate proposal, but not clearly positioned in the registry target state | Define the boundary where source-domain apps own canonical schemas, mappings, and integrated analytical views |
| Integrated coverage-aware domain maps | No explicit cross-domain contract for coverage status | Add integrated domain surfaces that show harmonized objects together and distinguish integrated from not-yet-integrated regions |

## 7. Recommended BRIT Architecture

### 7.1 Split registry metadata from backend access

`GeoDataset` should become the user-facing registry record, while physical access details move behind an explicit backend model or adapter configuration.

Recommended conceptual split:

- `GeoDataset`
  - user-facing identity, publication, region, sources, description, preview, map config
- `DatasetBackend` or equivalent backend configuration
  - backend type
  - connection or server reference
  - schema name / table name / view name / foreign table name
  - geometry column
  - primary key column
  - optional label/title expression
  - refresh mode
- `DatasetSchemaSnapshot` or equivalent cached introspection record
  - discovered columns and types
  - allowed visible/filterable/exportable columns
  - inferred statistics
  - last introspected timestamp

The exact model names can change, but the separation of concerns should remain.

### 7.2 Introduce a small dataset adapter contract

The generic UI/query layer should not care whether a dataset comes from a Django model or a foreign table.

Recommended adapter responsibilities:

- introspect schema
- provide base queryset or SQL relation handle
- expose geometry column and primary key
- build safe filtered queries from allowlisted metadata
- fetch a single feature by identity
- provide count/extent summaries where possible

Initial backend types to support:

- `django_model`
- `db_table`
- `db_view`
- `materialized_view`
- `foreign_table`

Later, if justified:

- remote SQL proxy adapter
- file-backed virtual adapter
- HTTP feature service adapter

### 7.3 Keep federation inside the database boundary first

The simplest credible path to federation is not direct arbitrary remote querying from Django.

Prefer this order:

- PostgreSQL local tables/views
- PostgreSQL materialized views
- PostgreSQL foreign tables via approved FDW workflow
- only later consider non-SQL remote adapters

This keeps:

- one query engine
- one permission boundary
- one geometry capability layer
- one optimization strategy

### 7.4 Separate introspection from exposure policy

Discovered columns are not automatically public columns.

The registry should store, per dataset:

- discovered columns
- visible columns
- filterable columns
- searchable columns
- exportable columns
- redacted/internal columns

This keeps introspection safe and reviewable.

### 7.5 Treat live federation and immutable snapshots as different products

BRIT should explicitly distinguish:

- **Live federated datasets**
  - current data from a read-only foreign source
  - freshness favored over reproducibility
- **Cached federated datasets**
  - periodically refreshed local materialization
  - balanced performance and stability
- **Immutable snapshots**
  - frozen version for inventory reproducibility and publication

The same logical dataset may expose more than one operational mode over time.

### 7.6 Preserve domain-specific harmonization as an overlay

The geodataset harmonization pipeline remains valuable, but should sit on top of the registry, not beside it.

That means:

- canonical source-type target models still make sense where BRIT needs semantic harmonization
- generic registry support should also allow simple passthrough datasets that are only explorable, not harmonized
- harmonized datasets and passthrough datasets should share the same registry and exploration surface

### 7.7 Let source-domain apps own canonical integration contracts

The registry should not own the canonical schema of roadside trees, greenhouses, waste-collection assets, or future domains.

Recommended boundary:

- the registry layer owns dataset discovery, exposure, backend access, and generic exploration
- each source-domain app owns:
  - canonical analytical fields for its domain
  - source-to-canonical field mappings
  - code/value harmonization
  - unit normalization
  - level-of-detail reconciliation rules
  - domain-specific quality thresholds for calling a region integrated

This keeps the generic registry simple while allowing domain-specific intelligence where it belongs.

### 7.8 Add first-class integrated domain surfaces

In addition to raw/provider datasets, BRIT should support logical integrated domain surfaces.

Recommended conceptual objects:

- **raw dataset entries**
  - one `GeoDataset` per provider-specific dataset or snapshot
- **harmonized domain records**
  - canonical per-feature records produced by the source-domain app
- **integrated domain views**
  - queryable surfaces built from all harmonized records of a domain
- **coverage summaries**
  - region-level status records indicating whether a region is integrated, partially integrated, raw-only, or uncovered

These may be implemented as tables, views, materialized views, or equivalent registry-backed surfaces depending on performance and reproducibility needs.

## 8. Phased Delivery Plan

## Phase 0 - Baseline audit and architecture boundary

Goal: document reality and stop the roadmap from drifting away from the code.

Deliverables:

- inventory all current `GeoDataset` read/write paths
- inventory all current dependencies on `model_name` and `GIS_SOURCE_MODELS`
- inventory what `maps/README.md` promises that the code does not yet implement
- identify all current map routes that still assume a concrete Django model name
- define the canonical boundary between:
  - dataset registry metadata
  - backend access configuration
  - dynamic exploration UI
  - optional domain-specific semantic overlays
- record concrete examples of datasets BRIT should support in the future:
  - local unmanaged PostGIS table
  - local view
  - materialized snapshot
  - PostgreSQL foreign table

Success criteria:

- there is one agreed-on starting-point document or issue summary
- the current gap between README promise and implementation is explicit
- the target architecture vocabulary is stable enough for incremental work

## Phase 1 - Finish the local metadata-driven dataset registry

Goal: make ordinary local tables/views explorable without code changes.

Deliverables:

- extend the dataset metadata model so the table/view-backed path is real, not only documented
- support authoritative storage of:
  - backend type
  - schema/table identifier
  - geometry column
  - primary key column
  - visible/filterable columns
  - label/display configuration
- implement safe schema introspection for local PostGIS relations
- implement generic table/detail/map querying from registry metadata
- make `GeoDataset.get_absolute_url()` independent from `model_name`
- reduce `GIS_SOURCE_MODELS` to compatibility-only status or remove it where safe

Success criteria:

- a new local PostGIS table can be registered and explored end-to-end with no code changes
- the README workflow becomes true in production code, not only aspirational
- at least one existing hardcoded map dataset can be re-expressed through the generic registry path

## Phase 2 - Harden safety, permissions, and observability

Goal: make dynamic exploration safe enough for broad internal use.

Deliverables:

- column allowlist and geometry allowlist enforcement
- dataset-level health check in admin
- clear validation errors for missing relation, missing geometry field, invalid PK, unsupported types
- audit-friendly metadata showing who changed exposure settings and when
- performance safeguards:
  - max page size
  - bounded filter operators
  - optional extent/count caching
- clear public/private/review behavior aligned with existing `UserCreatedObject` policy patterns where applicable

Success criteria:

- dynamic datasets fail safely and explain why
- sensitive/internal columns cannot leak through introspection alone
- large datasets remain usable without accidental full-table scans in common views

## Phase 3 - Introduce federated database backends

Goal: allow selected external datasets to appear in BRIT without physical copy-first ingestion.

Deliverables:

- define operational support for read-only federation through PostgreSQL-native mechanisms first
- add backend metadata for foreign server / remote schema / foreign table identity where needed
- add admin guidance and validation for federated dataset registration
- distinguish live federated vs cached federated datasets in metadata and UI
- document operational requirements for DBAs/admins, including read-only credentials and ownership boundaries

Success criteria:

- a read-only external PostGIS dataset exposed through approved database federation can be registered as a `GeoDataset`
- users can browse and filter it through the same baseline UI as local datasets
- the UI clearly indicates that the dataset is federated and whether results are live or cached

## Phase 4 - Versioning, refresh, and reproducibility

Goal: support both live browsing and reproducible analytical use.

Deliverables:

- dataset version/snapshot model or equivalent version contract
- refresh metadata:
  - last refreshed
  - upstream last seen
  - refresh status
  - refresh mode
- optional materialization flow for turning federated-live data into reproducible snapshots
- ability for downstream consumers to select either current dataset or fixed snapshot

Success criteria:

- BRIT can support both exploratory live maps and reproducible inventory inputs without conflating the two
- dataset freshness and immutability are visible and machine-readable

## Phase 5 - Semantic overlays and downstream integration contracts

Goal: let source-domain apps harmonize incompatible same-domain datasets into integrated analytical views without reintroducing per-dataset hardcoding.

Deliverables:

- add optional semantic mapping layer for datasets that correspond to domain concepts
- define per-domain canonical analytical contracts in the relevant source-domain apps
- support field aliasing, coded-value normalization, unit normalization, and level-of-detail reconciliation without rewriting source provenance away
- let inventories and source-domain tools reference datasets through stable dataset contracts
- align with the existing harmonization-pipeline work where canonical target models are needed
- add at least one integrated domain surface that combines harmonized records across provider datasets
- add region-level coverage status for integrated domain surfaces so maps can distinguish:
  - integrated coverage
  - source data exists but is not yet integrated
  - no known source data available

Success criteria:

- generic registry datasets and harmonized canonical datasets can coexist under one consistent dataset contract
- downstream modules no longer depend on Python model names for basic dataset selection
- at least one pilot domain such as roadside trees can be explored both as individual provider datasets and as one integrated cross-provider map
- the integrated map clearly distinguishes covered from not-yet-integrated regions

## Phase 6 - Operational polish and deprecation cleanup

Goal: remove the transitional architecture once the registry is trusted.

Deliverables:

- remove or isolate remaining `model_name`-driven compatibility paths
- retire hardcoded dataset-specific map routing where generic routing is sufficient
- align URLs, explorer naming, and detail/map navigation with the broader UX harmonization direction
- consolidate documentation so the active onboarding workflow lives in one place and matches the code

Success criteria:

- adding a standard dataset is primarily an admin/data task
- hardcoded dataset wiring exists only where BRIT genuinely needs custom logic
- documentation and runtime behavior match

## 9. Progress Scorecard

Use this section to evaluate whether the roadmap is actually moving forward.

### 9.1 Capability checklist

| Capability | Not started | Partial | Done |
|---|---|---|---|
| Local table-backed dataset registration with no code changes |  |  |  |
| Local view-backed dataset registration with no code changes |  |  |  |
| Generic map/table/detail surfaces fully driven by metadata |  |  |  |
| `GeoDataset` independent from hardcoded `model_name` routing |  |  |  |
| Column exposure allowlists enforced |  |  |  |
| Federated read-only foreign table support |  |  |  |
| Dataset freshness/version semantics visible in UI |  |  |  |
| Downstream consumers select datasets by stable dataset identity |  |  |  |
| Source-domain apps define canonical harmonization contracts for same-domain datasets |  |  |  |
| At least one integrated domain map combines harmonized records across providers |  |  |  |
| Coverage maps distinguish integrated from not-yet-integrated regions |  |  |  |

### 9.2 Definition of “the vision is materially real”

The roadmap should be considered substantively achieved when all of the following are true:

- a new local PostGIS relation can be exposed through BRIT with admin-only configuration
- at least one federated external dataset can be exposed read-only through the same mechanism
- users cannot tell from the baseline UI whether a dataset is backed by a local table or foreign table except where provenance/freshness labels intentionally disclose it
- no new URL/view/filter/template code is required for ordinary dataset onboarding
- domain-specific code is only needed for semantic enrichment or non-generic workflows
- at least one domain has a real integrated cross-provider analytical surface
- that integrated surface includes a map that shows integrated regions and grays not-yet-integrated ones

### 9.3 Anti-goals that indicate failure

The effort is drifting off course if:

- each new dataset still needs a new Django model or view class
- federation exists only as undocumented DBA magic outside the BRIT registry
- introspection exposes arbitrary columns by default
- live federated data and frozen snapshots are not distinguishable
- the README continues to promise behavior that the codebase does not actually implement
- same-domain datasets remain explorable only in isolation with no path to an integrated analytical view
- the generic registry starts absorbing domain semantics that should instead live in the responsible source-domain app

## 10. Risks and Open Questions

### 10.1 Security and data-governance risk

Dynamic exploration can accidentally expose fields that were safe in the database but not intended for UI users.

Mitigation direction:

- allowlists
- read-only backends
- explicit publication workflow
- per-dataset exposure review

### 10.2 Performance risk

Generic querying against large external relations can degrade quickly.

Mitigation direction:

- bounded filters
- count/extent caching
- materialized cache option
- operational guidance for indexes and view design

### 10.3 Schema drift risk for federated data

External providers can change schema without warning.

Mitigation direction:

- introspection snapshots
- drift detection in health checks
- clear degraded status in admin/UI
- snapshotting for critical downstream use

### 10.4 Scope creep risk

It is easy to overreach from “generic exploration” into “full universal geospatial ETL platform.”

Mitigation direction:

- deliver local table-backed registry first
- add FDW-based federation before non-SQL connectors
- keep advanced harmonization as a later overlay, not a prerequisite

### 10.5 Open design question: model placement

The current name `GeoDataset` is probably still appropriate for the user-facing registry object, but the backend/configuration models may need to live either in `maps` or in a more cross-cutting data-access module. The roadmap does not require that answer immediately, but Phase 0 should settle the boundary.

## 11. Recommended Next Slice

The next practical implementation slice should be narrow and reality-based:

- make the current `GeoDataset` contract honest
- choose the authoritative metadata fields for local table-backed datasets
- decouple URL/view lookup from `model_name`
- deliver one real end-to-end example where a manually created PostGIS table is registered and explored without code changes
- define the pilot domain contract for a first harmonized integrated view, with `roadside_trees` as the most natural candidate

That slice is small enough to validate the architecture and large enough to prove the core promise.
