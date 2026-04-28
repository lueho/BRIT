# Dataset Registry and Federated Geodata Target-State Plan

- **Status**: Active roadmap; Phase 0 complete, Phase 1 Tasks 1.1-1.3 complete enough for the current compatibility-backed route path, Task 1.4 local-relation table/detail/map API slice in progress
- **Date**: 2026-04-16
- **Scope**: `maps` dataset onboarding, standalone exploration, long-term federation of external geospatial data sources, and domain-level harmonized integration across incompatible datasets

## Documentation Boundary

- **This document is the single authoritative roadmap for BRIT's generic dataset onboarding and federation direction**
It owns the target state, sequencing, gap analysis, evaluation criteria, delivery phases, and implementation-progress tracking for making new geodata explorable with little or no code.

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
- `maps/README.md` now documents the current as-is `GeoDataset` workflow and points future registry work back to this roadmap
- the `maps` list/gallery UX already treats `GeoDataset` as a primary user-facing object
- Phase 1 has introduced normalized runtime metadata via `GeoDatasetRuntimeConfiguration` and `GeoDatasetColumnPolicy`
- dataset-scoped detail, map, table, and feature-detail routes now exist, including `/maps/geodatasets/<pk>/map/` and `/maps/geodatasets/<pk>/table/`
- the implementation still partly depends on `model_name`, compatibility runtime-model mappings, and hardcoded feature API basenames
- the table/view-backed adapter path is not yet the authoritative runtime path for ordinary new datasets
- the current generic dataset path is therefore an active migration path rather than a completed architecture

There is an even higher-level product goal above dataset registration and harmonization: the resulting data should ultimately become jointly usable in the inventory app. That is the point where the overall workflow is completed.

So this roadmap is not only about making datasets visible in `maps`. It is also about making them dependable downstream building blocks for cross-domain inventory evaluation.

This document turns that direction into a concrete target-state roadmap.

## Critical Review Refinements

This roadmap is directionally sound, but the target state needs several guardrails so implementation does not turn into an over-broad geospatial platform.

- **Do not conflate the registry with ingestion**
  - The registry should expose, govern, and describe datasets.
  - Importers, source connectors, and harmonization pipelines may create or refresh backing relations, but they should converge on the registry contract rather than becoming part of the baseline map/table runtime.

- **Separate dataset identity, runtime binding, and version binding**
  - `GeoDataset` should remain the stable user-facing identity.
  - Runtime binding should describe where the current rows come from and how to query them.
  - Version binding should describe whether the current runtime points at a moving relation or an immutable snapshot.
  - The current one-to-one `GeoDatasetRuntimeConfiguration` is a valid Phase 1 stepping stone, but it should not become the final versioning model if BRIT needs multiple snapshots or runtime modes for the same logical dataset.

- **Treat arbitrary SQL access as a privileged backend concern, not a UI feature**
  - Generic exploration should never mean users can provide arbitrary SQL, join arbitrary tables, or request arbitrary derived expressions.
  - The registry may point to approved tables, views, materialized views, or foreign tables, but those relations must be prepared and reviewed by trusted operators before publication.

- **Keep the first production pilot intentionally boring**
  - The first proof should be one local PostGIS table or view with a geometry column, scalar display fields, a primary key, and a small allowlisted filter set.
  - Federation, refresh orchestration, harmonization, and inventory pinning should remain follow-up capabilities until this baseline is stable.

- **Make deprecation measurable**
  - `model_name` and hardcoded map routes should not merely be described as compatibility-only.
  - Each compatibility path should eventually have an owner, a replacement path, a test proving the replacement, and a removal condition.

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
- the core registry remains open to multiple source-access patterns, for example:
  - PostgreSQL-native federation
  - authenticated WFS or similar feature-service access
  - authenticated file download workflows
  - managed imports from file URLs such as CSV, GeoJSON, or Excel
- regardless of source type, the user-facing dataset should still expose the same baseline metadata, provenance, refresh, and exploration contract wherever technically possible

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

### 2.9 Inventory-ready downstream evaluation

The long-term workflow is only complete when registered and harmonized datasets can be evaluated together in the inventory app.

Target outcome:

- inventories can reference datasets and harmonized domain views through stable dataset contracts
- inventories can deliberately choose current datasets or pinned dataset versions depending on reproducibility needs
- cross-domain evaluation can combine multiple harmonized inputs without depending on hardcoded model names or one-off import logic
- inventory users can still inspect provenance, freshness, coverage, and integration status of the inputs they are evaluating

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

### 3.5 Stable dataset identity, explicit dataset versions

BRIT should distinguish clearly between:

- the logical dataset identity
- the currently exposed dataset state
- immutable historical versions or snapshots of that dataset

This is especially important for imported external datasets that are refreshed over time.

Recommended rule:

- a provider dataset such as `Roadside trees - County X` should usually have one stable `GeoDataset` identity
- each import or upstream release can create a new dataset version or snapshot when reproducibility matters
- the normal user-facing dataset page should point to the current approved version by default
- downstream analytical consumers must be able to choose whether they bind to the moving current dataset or to a fixed version

The long-term plan should therefore avoid two extremes:

- **not only in-place overwrite with no version record**
  - this loses auditability and makes historical analysis unreproducible
- **not one unrelated top-level dataset per refresh cycle**
  - this clutters the registry and makes users treat time iterations as entirely different datasets when they are really versions of one source

### 3.6 Import strategy by upstream change pattern

Different external sources need different physical handling, but under one consistent contract.

#### Periodic full releases

Examples:

- annual roadside-tree export from a county
- yearly published inventory table from a ministry

Recommended handling:

- ingest each release as an immutable version or snapshot
- expose one stable dataset identity that points to the latest approved version for normal browsing
- keep older versions available for reproducible analysis, QA, and rollback

This usually fits better than appending into one ever-changing table because each release is effectively a new authoritative state of the same dataset.

#### Continuous upstream updates

Examples:

- a provider updates records daily or weekly in place
- BRIT pulls from an operational system with no formal annual release boundary

Recommended handling:

- maintain a stable current representation for normal exploration
- also record refresh runs and, where analytically important, periodic snapshots or changelog-style version points
- use a materialized current table/view or equivalent registry-backed surface for performance and predictable querying

This usually fits better than creating a brand-new top-level table for every refresh event.

#### Append-only event streams or naturally temporal data

If the upstream dataset is genuinely cumulative and the row model itself is temporal, appending may be correct. Even then, BRIT should still expose version metadata for import runs so that users know what upstream state they are seeing.

### 3.7 Stable core capabilities, flexible source connectors

BRIT should keep the basic dataset experience stable while staying flexible about how data enters or is accessed.

The stable core should define at least:

- dataset identity
- provenance and source metadata
- exposure policy and allowlists
- schema summary
- refresh and version status
- map/table/detail exploration surfaces where applicable
- domain-harmonization hooks for downstream source apps

The flexible edge should allow multiple connector or ingestion modes, for example:

- direct database relation registration
- PostgreSQL foreign tables
- authenticated WFS or other feature-service connectors
- authenticated HTTP download of files
- managed imports from remote Excel, CSV, GeoJSON, or similar files

The architectural rule should be:

- vary the source connector as needed
- keep the user-facing dataset contract and downstream integration contract as stable as possible

### 3.8 Prefer PostgreSQL-native backends first

BRIT should solve the common case first:

- local PostGIS tables/views/materialized views
- PostgreSQL foreign tables and related DB-native mechanisms

### 3.9 UX consistency with existing module direction

This roadmap should follow the existing UX guidance that the primary module entry is the main list of `GeoDataset` records, with explorer/list/detail/map patterns remaining consistent with other BRIT modules.

### 3.10 Source-domain ownership of harmonization

The generic registry layer should not try to understand the semantics of every domain.

- `maps` owns dataset registration and generic exploration
- source-domain apps own canonical domain schemas, semantic mappings, unit normalization rules, and integration logic for incompatible same-domain datasets
- cross-provider harmonization belongs to the domain app because only the domain app can define what counts as equivalence, acceptable downgrade, or required analytical minimum

### 3.11 Integration must preserve partial truth

Harmonization should not require every dataset to be equally rich.

- if one roadside-tree dataset provides species and another only genus, both can still contribute to the integrated roadside-tree view
- if one dataset provides crown diameter in centimeters and another in meters, both can still contribute after explicit normalization
- if a field is absent in a source dataset, the integrated record should carry `null` or lower-detail information rather than forcing invented values

### 3.12 Inventory app is the main downstream completion point

The architecture should treat the inventory app as the main downstream integration target for this work.

- dataset registration is not an end in itself
- harmonized domain views are not an end in themselves
- both should converge on stable, inspectable, version-aware inputs that inventories can evaluate together
- if a design choice improves map visibility but makes inventory consumption brittle, the roadmap should prefer the more inventory-stable option

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
- run inventory evaluations that consume multiple registered or harmonized datasets together through stable references

### 4.3 What the system knows

For each dataset BRIT knows at least:

- registry metadata
- stable dataset identity
- current exposed version
- physical backend type
- schema and geometry metadata
- provenance and bibliography references
- permissions and exposure policy
- whether the data is live, cached, or immutable
- whether the dataset is generic-only or has additional domain semantics
- whether the dataset participates in a harmonized domain integration pipeline
- what coverage status it contributes to for its declared region or regions

For imported datasets BRIT should also know at least:

- import mode, for example full replacement, incremental append, or federated-live
- refresh cadence, for example annual, monthly, on demand, or continuous
- upstream release identifier or upstream last-modified marker where available
- whether the current surface is reproducible or only the latest moving state

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
- each county dataset can expose both its current version and older imported releases where policy allows
- the `sources.roadside_trees` domain app defines the canonical integrated roadside-tree representation
- harmonized records from all integrated county datasets become queryable together through one integrated roadside-tree surface
- a Germany-wide map can display all integrated roadside-tree objects together
- the same map can shade counties by coverage status, for example:
  - integrated
  - source dataset available but not yet integrated
  - no known dataset available

The same pattern should apply to other domains where cross-provider integration is meaningful.

### 4.7 What completion of the end-to-end workflow looks like

The full workflow should ultimately look like this:

- external or local datasets are registered in BRIT through the generic registry contract
- recurring imports and live/federated sources are versioned and tracked explicitly
- source-domain apps harmonize incompatible same-domain datasets where cross-provider analysis is needed
- integrated domain views and coverage summaries become available for exploration and QA
- the inventory app can then evaluate multiple registered and harmonized datasets together as stable, inspectable inputs

At that point, `maps` is no longer only a viewing surface. It becomes the governed data-entry layer for downstream inventory evaluation.

## 5. Current State in BRIT

### 5.1 Already aligned with the direction

- **User-facing dataset object exists**
  - `maps.GeoDataset` already exists and is treated as a first-class object in list/gallery views
- **Runtime metadata is now normalized in the model layer**
  - `GeoDatasetRuntimeConfiguration` stores backend/relation metadata for the current Phase 1 runtime path
  - `GeoDatasetColumnPolicy` stores per-column exposure flags instead of relying only on parallel text allowlists
- **Dataset-scoped navigation has started**
  - dataset detail and map routes now resolve by dataset identity, including `geodataset-detail` and `geodataset-map`
- **Maps UX already exposes datasets as a primary concept**
  - `maps_list`, `geodataset-gallery`, and owned list/gallery routes already exist
- **Admin registration exists in early form**
  - `GeoDataset` is manageable in admin
- **The codebase documents the current boundary honestly**
  - `maps/README.md` now describes current as-is behavior and points future registry work back to this roadmap
- **Plugin-aware route composition exists elsewhere in the repo**
  - the `sources.registry` pattern shows BRIT can already move toward metadata/plugin contracts instead of hardcoded monolith coupling

### 5.2 Not yet aligned with the direction

- **Compatibility model lookup still participates in runtime behavior**
  - `GeoDataset.model_name`, runtime-model compatibility mappings, and hardcoded feature API basenames still support existing map behavior
- **The table/view-backed adapter path is not yet authoritative**
  - runtime metadata exists, but ordinary local PostGIS tables or views are not yet fully introspected, queried, filtered, and serialized through one generic adapter
- **The generic route family is incomplete**
  - dataset-scoped detail and map routes exist, but the table/detail/feature drill-down path and map feature API still need to become fully dataset-backed
- **The backend abstraction is not yet implemented as a reusable adapter layer**
  - local Django models, raw tables, views, materialized views, and foreign tables are not yet represented through one unified runtime contract
- **No federated-source governance layer exists yet**
  - there is not yet a first-class model for external connections, foreign servers, refresh policy, or query safety
- **Versioning/freshness semantics are not yet standardized across generic datasets**
  - datasets do not yet uniformly express snapshot/live/cached behavior
- **No first-class contract yet exists for domain-integrated views and coverage maps**
  - this roadmap now defines the target boundary, but there is not yet an implemented model/API contract for source-domain apps to publish integrated coverage status through the registry

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
| Inventory-ready downstream evaluation | Inventories are mentioned, but not yet framed as the architectural completion point | Make inventory consumption an explicit design driver for dataset identity, versioning, and harmonization contracts |

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

The Phase 1 implementation has already started this split with `GeoDatasetRuntimeConfiguration` and `GeoDatasetColumnPolicy`. Treat those models as the current stepping stone, not as a frozen final schema:

- `GeoDatasetRuntimeConfiguration` is acceptable while one dataset has one active runtime binding
- `GeoDatasetColumnPolicy` is the right direction for exposure policy, but it should grow from introspection snapshots and explicit review rather than from free-form field lists alone
- later versioning work should not overload the runtime configuration model with import-run or snapshot history
- if a logical dataset eventually needs multiple runtime bindings, for example current live, cached materialized, and archived snapshot, introduce a version/runtime-binding layer rather than duplicating top-level `GeoDataset` identities

### 7.2 Introduce a small dataset adapter contract

The generic UI/query layer should not care whether a dataset comes from a Django model, a foreign table, an authenticated WFS workflow, or a managed Excel import.

Recommended adapter responsibilities:

- introspect schema
- provide base queryset or SQL relation handle
- expose geometry column and primary key
- build safe filtered queries from allowlisted metadata
- fetch a single feature by identity
- provide count/extent summaries where possible

In practice this implies two separable concerns:

- a **source connector or ingestion adapter** that knows how to authenticate, fetch, refresh, and validate an upstream source
- a **dataset runtime adapter** that exposes the resulting dataset to BRIT's generic map/table/detail/query surfaces

BRIT should standardize the second layer more strictly than the first.

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

Connector/ingestion modes that the architecture should remain open to include:

- PostgreSQL-native federation
- authenticated feature-service fetches such as WFS
- authenticated file downloads
- scheduled imports from Excel, CSV, GeoJSON, or similar source files

Not every connector needs the same implementation style. Some may materialize into local tables, while others may remain live or semi-live. What matters is that they converge on the same registry contract once inside BRIT.

The first runtime adapter should deliberately support fewer capabilities than the final contract:

- local PostgreSQL relation or view only
- one geometry column
- one stable primary-key column
- scalar fields only for table/detail display
- simple allowlisted filters only
- no arbitrary joins
- no user-provided SQL
- no computed expressions except those already materialized in a trusted view

This narrower adapter is enough to prove the registry architecture while preserving a safe path to later federation.

### 7.3 Add an import-run and dataset-version contract

Imported external datasets need first-class lifecycle objects, not only backend connection metadata.

Recommended conceptual objects:

- `GeoDataset`
  - stable logical dataset identity shown to users
- `GeoDatasetVersion`
  - immutable version or snapshot of one dataset, with upstream release metadata, imported-at timestamp, schema signature, and reproducibility status
- `GeoDatasetImportRun`
  - operational record of one attempted refresh, including source location, started/finished timestamps, status, row counts, and validation results
- current-version binding
  - marks which version is the current exposed one for normal browsing and for domain harmonization defaults

This lets BRIT support all of the following without changing the user-facing dataset identity:

- annual full replacements
- rolling current datasets
- rollback to a previous import
- domain harmonization pinned either to latest approved data or to a specific reproducible release set

### 7.4 Keep federation inside the database boundary first

The simplest credible path to federation is not direct arbitrary remote querying from Django.

Prefer this order:

- PostgreSQL local tables/views
- PostgreSQL materialized views
- PostgreSQL foreign tables via approved FDW workflow
- only later consider non-SQL remote adapters

This ordering is a delivery preference, not a permanent architectural exclusion. The long-term design should remain open to non-database connectors when they are operationally justified.

This keeps:

- one query engine
- one permission boundary
- one geometry capability layer
- one optimization strategy

### 7.5 Separate introspection from exposure policy

Discovered columns are not automatically public columns.

The registry should store, per dataset:

- discovered columns
- visible columns
- filterable columns
- searchable columns
- exportable columns
- redacted/internal columns

This keeps introspection safe and reviewable.

The operational workflow should be:

- introspection discovers available columns and stores a snapshot
- all discovered columns default to non-visible and non-exportable unless a trusted migration or admin action explicitly marks them otherwise
- staff review promotes selected columns into `GeoDatasetColumnPolicy`
- publication should fail or warn if the approved column policy references columns that no longer exist
- drift detection should be able to compare the current relation against the last reviewed schema snapshot

This avoids treating introspection as publication.

### 7.6 Treat live federation and immutable snapshots as different products

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

This distinction should be visible in both UI and machine-readable metadata. A dataset used for inventory evaluation should never silently switch from immutable snapshot semantics to live federation semantics simply because the backing relation changed.

### 7.7 Preserve domain-specific harmonization as an overlay

The geodataset harmonization pipeline remains valuable, but should sit on top of the registry, not beside it.

That means:

- canonical source-type target models still make sense where BRIT needs semantic harmonization
- generic registry support should also allow simple passthrough datasets that are only explorable, not harmonized
- harmonized datasets and passthrough datasets should share the same registry and exploration surface

### 7.8 Let source-domain apps own canonical integration contracts

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

### 7.9 Add first-class integrated domain surfaces

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

Phase status: complete; the audit and architecture-boundary decisions for Tasks 0.1 through 0.6 are now recorded, and Phase 1 can proceed against this baseline.

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

### Phase 0 implementation tasks

- **Task 0.1 - Lock the post-refactor meaning of `GeoDataset`**
  - Decide explicitly that `GeoDataset` is the stable logical dataset identity shown to users, not merely a thin wrapper around one hardcoded model route and not one unrelated top-level object per refresh cycle.
  - This decision must be recorded clearly enough that later work on versions, imports, and inventories can build on it without redefining the dataset concept.
  - Primary file targets:
    - `docs/04_design_decisions/2026-04-16_dataset_registry_and_federated_geodata_target_state_plan.md`
    - `maps/models.py`
    - `inventories/models.py`

- **Task 0.2 - Audit all runtime coupling to `model_name`**
  - Enumerate every place where dataset identity currently depends on `GeoDataset.model_name`, `GIS_SOURCE_MODELS`, CamelCase route names, or hardcoded model assumptions.
  - The audit should cover model fields, URL resolution, view lookup, tests, and user-facing navigation so that Phase 1 can remove coupling systematically rather than leaving hidden dependencies behind.
  - Primary file targets:
    - `maps/models.py`
    - `maps/views.py`
    - `maps/urls.py`
    - `maps/forms.py`
    - `maps/tests/test_views.py`
    - `maps/tests/test_filters.py`

- **Task 0.3 - Reconcile documented promises with implemented behavior**
  - Review the no-code onboarding story documented in `maps/README.md` against the actual runtime path and make every mismatch explicit.
  - In particular, settle whether the documented generic dataset fields, routes, and rollout assumptions already exist, are partially implemented, or still need to be created in Phase 1.
  - Primary file targets:
    - `maps/README.md`
    - `docs/04_design_decisions/2026-02-09_module_ux_harmonization_guideline.md`
    - `maps/models.py`
    - `maps/urls.py`

- **Task 0.4 - Define the minimum Phase 1 metadata contract**
  - Agree on the smallest metadata set that makes a local table/view-backed dataset genuinely explorable through registry metadata rather than bespoke code.
  - At minimum this contract should decide how BRIT stores backend type, physical relation identity, geometry column, primary key column, label/display configuration, and visible/filterable/searchable/exportable field allowlists.
  - Primary file targets:
    - `maps/models.py`
    - `maps/forms.py`
    - `maps/admin.py`

### Phase 0 decision for Task 0.4 - Minimum Phase 1 metadata contract

- **Keep `GeoDataset` as the stable dataset identity and layer runtime metadata onto it**
  - Phase 1 should extend `GeoDataset` rather than introduce a separate user-facing dataset identity model.
  - Existing descriptive fields such as `name`, `description`, `preview`, `region`, `sources`, and `map_configuration` remain part of the dataset contract.
  - Existing `model_name` should move to compatibility-only status once the new runtime metadata is available.

- **Use normalized subordinate models from the start rather than JSON-style field lists on `GeoDataset`**
  - The Phase 1 contract should be normalized at the database level from the beginning, even for the first local registry slice.
  - `GeoDataset` remains the stable dataset identity, but runtime configuration that has its own structure should live in subordinate `maps` models rather than in denormalized list fields.
  - In particular, per-column exposure policy should be represented as one row per dataset column, not as `JSONField` or array-based allowlists stored directly on `GeoDataset`.

- **Required runtime metadata for the first local registry slice**
  - dataset backend metadata
    - identifies how the dataset is resolved at runtime
    - Phase 1 should support at least local table and local view style backends, while leaving room for later materialized and federated backends
    - this metadata should live in a normalized subordinate model such as a dataset backend or relation binding record rather than being spread across loosely related scalar fields without structure
  - physical relation identity
    - BRIT should store a stable database relation reference rather than infer it from a Django model name
    - this should be represented as normalized runtime metadata such as `schema_name` plus `relation_name` on a backend/configuration model or an equivalent normalized relation identifier
  - geometry and identity metadata
    - the authoritative geometry field used for map rendering and spatial extent logic
    - the authoritative unique row identifier used for detail lookup, pagination stability, and feature URLs
    - the default human-readable label/display field used in generic list, popup, and detail navigation
    - these fields should be represented in the normalized runtime metadata layer, not as ad hoc conventions

- **Required presentation metadata for safe generic exploration**
  - one normalized dataset-column metadata row per exposed scalar column
    - stores the authoritative runtime column name and any derived display label
    - records whether the column is visible, filterable, searchable, orderable, and exportable
    - provides the place to add richer per-column metadata later without another schema reversal
  - one clear distinction between relation-level metadata and column-level metadata
    - relation-level concerns such as backend type, schema, relation name, geometry field, primary key, and default label belong together
    - column-level exposure policy belongs in a dedicated subordinate model rather than in multiple parallel allowlist fields

- **Fields that are explicitly not required for the minimum Phase 1 contract**
  - versioning and refresh metadata
    - those belong to later phases focused on reproducibility and imports
  - federated credential/configuration details
    - those belong to later backend-specific work and should not be mixed into the minimum local registry contract
  - semantic harmonization metadata
    - those belong to domain-level overlays rather than baseline dataset registration

- **Admin and form implications of the minimum contract**
  - Phase 1 admin/editor surfaces should expose the runtime metadata above as explicit dataset configuration, rather than hiding them behind code or documentation.
  - The editing workflow should support both relation-level metadata and normalized per-column policy records.
  - The first pass does not need a polished end-user self-service workflow; it does need one authoritative editable metadata surface for staff or developers.
  - `model_name` may remain temporarily visible only where necessary for compatibility, but new generic dataset setup should rely on the new runtime metadata instead.

- **Task 0.5 - Define the dataset runtime adapter boundary**
  - Specify the minimal interface the generic map/table/detail surfaces need from any backend so that the UI layer does not care whether the data comes from a Django model, raw database relation, or later a federated source.
  - The contract should cover schema introspection, geometry resolution, primary-key lookup, safe filtered querying, single-feature lookup, and count/extent summaries where supported.
  - Primary file targets:
    - `maps/views.py`
    - `maps/mixins.py`
    - `maps/viewsets.py`

### Phase 0 decision for Task 0.5 - Dataset runtime adapter boundary

- **Introduce one dataset runtime adapter contract behind the generic views**
  - Phase 1 should resolve a registered `GeoDataset` into one runtime adapter instance that hides whether the backing data comes from a Django model, a local relation, or a later federated backend.
  - Generic map, table, detail, and export surfaces should depend on this adapter contract rather than on `model_name`, `ModelMapConfiguration`, or hardcoded view subclasses.

- **The adapter owns data resolution, not user-facing routing**
  - Generic dataset routes, permissions, templates, and response shapes should remain in the `maps` view and viewset layer.
  - The adapter should provide data access and schema behavior; it should not generate canonical BRIT URLs.
  - This keeps routing, moderation, and UX policy centralized while still allowing multiple backend implementations.

- **Minimum adapter responsibilities for the first local registry slice**
  - dataset identity binding
    - resolve from one `GeoDataset` instance and validate that the configured backend metadata is sufficient to run
  - schema introspection
    - return the authoritative primary key field, geometry field, label field, scalar column metadata, and the configured visible, filterable, searchable, and exportable allowlists
  - filtered collection query
    - build a safe allowlisted query path for generic table and map browsing
    - support filtering, search, ordering, pagination, and optional bounding-box restriction where the backend can do so
  - single-feature lookup
    - return one feature or row by configured primary key for detail views and feature drill-down
  - feature serialization inputs
    - expose enough structured row and field information for generic serializers to build table rows, map features, labels, and detail payloads without backend-specific template logic
  - aggregate helpers
    - provide count and extent summaries where supported so the generic UI can support totals, viewport logic, and lightweight summary endpoints
  - cache/version inputs
    - expose a stable dataset-version signal or the raw ingredients needed by the generic caching layer to compute one

- **Responsibilities that should stay outside the adapter**
  - map configuration serialization and layer URL assembly
    - these should stay in the generic `maps` view and serializer layer, even if they become dataset-scoped rather than model-scoped
  - permission enforcement and publication-state policy
    - these should remain governed by the existing object-management and view permission patterns
  - domain-specific semantic overlays
    - those belong to later source-domain composition, not to the baseline runtime adapter

- **Direct implications for the current runtime**
  - The future adapter contract should replace the current `FilteredMapMixin.get_dataset()` and `GeoDataset.objects.get(model_name=...)` pattern with dataset-identity-based resolution.
  - It should also replace the current reliance on model-name-derived `api_basename` discovery in `MapMixin` with explicit dataset-backed runtime configuration.
  - `CachedGeoJSONMixin` and the generic viewset layer should become reusable consumers of adapter-backed query and version behavior rather than requiring one bespoke model viewset per dataset.

- **Task 0.6 - Settle model placement and compatibility policy**
  - Decide whether new backend/configuration models remain in `maps` or move into a more cross-cutting layer, and document the rationale so Phase 1 is not blocked by structural churn.
  - Decide which existing routes and fields remain temporarily as compatibility paths during migration, and which ones are expected to become compatibility-only immediately.
  - Primary file targets:
    - `maps/models.py`
    - `maps/urls.py`
    - `maps/views.py`
    - `docs/04_design_decisions/2026-04-16_dataset_registry_and_federated_geodata_target_state_plan.md`

### Phase 0 decision for Task 0.6 - Model placement and compatibility policy

- **Keep the first registry implementation in `maps`**
  - Phase 1 should keep new registry metadata, adapter resolution, and generic dataset runtime work inside `maps` rather than creating a new cross-cutting app immediately.
  - This is the lowest-risk path because `GeoDataset`, `MapConfiguration`, current list and gallery UX, and the relevant map/runtime views already live there.
  - `inventories` and other downstream consumers already depend on `maps.GeoDataset`, so moving the core identity concept during Phase 1 would add churn without solving the main blocker.

- **Use `GeoDataset` as the continuity anchor during migration**
  - Existing `GeoDataset` primary keys and downstream foreign keys remain authoritative.
  - New runtime metadata should attach to `GeoDataset` through `maps`-local helper models that are clearly subordinate to it wherever that metadata has its own structure or lifecycle.
  - Do not introduce a second competing user-facing dataset identity in Phase 1.

- **Define the canonical path versus compatibility-only paths**
  - Canonical for new work
    - dataset-scoped generic routes resolved by stable dataset identity
    - runtime behavior driven by explicit dataset metadata and the adapter contract
  - Compatibility-only during migration
    - `GeoDataset.model_name`
    - `GIS_SOURCE_MODELS`
    - hardcoded named routes such as `NutsRegion`
    - model-name-derived `ModelMapConfiguration` lookup and `api_basename` inference
    - source-domain map mounts used as the primary way to open registry-backed datasets

- **Compatibility expectations for Phase 1**
  - Existing list, gallery, CRUD, autocomplete, and downstream `GeoDataset` selection workflows should continue to work while the canonical runtime path changes underneath them.
  - `GeoDataset.get_absolute_url()` should move toward the dataset-scoped canonical route when the new runtime metadata is present, while retaining a controlled fallback for legacy rows that still rely on `model_name`.
  - New generic datasets introduced in Phase 1 should not require `model_name` to function.
  - Existing hardcoded or plugin-provided routes may continue to exist for bespoke domain behavior, but they should no longer define the baseline registry path.

- **Admin and form policy during migration**
  - The authoritative configuration surface for new registry-backed datasets should live in `maps` admin and form tooling.
  - Legacy fields may remain visible where needed for existing rows, but they should be treated as migration-era compatibility inputs rather than the preferred setup path.
  - Phase 1 should favor explicit staff-editable metadata over hidden conventions or route-name inference.

### Phase 0 baseline audit snapshot at phase start

This snapshot records the code state that motivated the roadmap. Some entries have already moved forward during Phase 1; keep the snapshot as historical baseline evidence, and use the Phase 1 status checkpoint for current progress.

- **Initial `GeoDataset` model contract was still model-bound**
  - `maps/models.py` defined `GeoDataset` with `preview`, `publish`, `region`, `model_name`, `sources`, `data_content_type`, `data_object_id`, and `map_configuration`.
  - `GeoDataset.get_absolute_url()` resolved via `model_name`, so dataset navigation was coupled directly to stored route/model identifiers rather than dataset identity.
  - `GIS_SOURCE_MODELS` was a hardcoded tuple containing values such as `HamburgRoadsideTrees`, `NantesGreenhouses`, `NutsRegion`, and `WasteCollection`.

- **Initial create, filter, and admin surfaces still exposed `model_name` as a first-class choice**
  - `maps/forms.py` exposed `model_name` in `GeoDataSetModelForm`.
  - `maps/filters.py` exposed `model_name = ChoiceFilter(choices=GIS_SOURCE_MODELS, label="Dataset type")` in `GeoDataSetFilterSet`.
  - `maps/admin.py` registered `GeoDataset` with only minimal admin customization, which was far below the metadata review surface described by the target architecture.

- **Initial runtime map lookup was not dataset-scoped yet**
  - `maps/views.py` implemented `FilteredMapMixin.get_dataset()` as `GeoDataset.objects.get(model_name=self.model_name)` and contained an explicit TODO indicating that lookup should move to `pk`.
  - The generic-looking `GeoDataSetPublishedFilteredMapView`, `GeoDataSetReviewFilteredMapView`, and `GeoDataSetPrivateFilteredMapView` therefore depended on a model-bound selector rather than a dataset-bound runtime contract.
  - `maps/urls.py` provided list, gallery, create, update, delete, and autocomplete routes for `GeoDataset`, but did not yet provide the dataset-scoped generic runtime route promised by the then-current README.

- **Hardcoded compatibility map routes are still part of the active public surface**
  - `maps/urls.py` still defines `path("nutsregions/map/", NutsRegionPublishedMapView.as_view(), name="NutsRegion")`.
  - The same URL file also mounts additional source-domain map URLs through `sources.registry`, which means the compatibility surface is a combination of core hardcoded routes and plugin-provided routes rather than one registry-driven dataset routing scheme.
  - Existing tests still validate this model-bound behavior, for example `maps/tests/test_views.py` asserts `reverse("NutsRegion")` and constructs test datasets with `model_name="NutsRegion"`.

- **The README initially over-promised relative to production code**
  - Earlier README text stated that a user could register a dataset using fields such as table name, geometry field, display fields, and filter fields before that path was authoritative.
  - The README has since been narrowed to document current implemented behavior only, while this roadmap remains the future-state source.

- **Downstream inventory code already depends on `GeoDataset` as a stable selection object**
  - `inventories/models.py` uses `GeoDataset` foreign keys in both `InventoryAlgorithm` and `ScenarioInventoryConfiguration`.
  - `Scenario.available_geodatasets()`, `Scenario.evaluated_geodatasets()`, and `Scenario.available_inventory_algorithms()` all query through `GeoDataset` identity and region, which is compatible with the target direction.
  - `inventories/forms.py` and `inventories/views.py` build autocomplete and configuration flows directly on `GeoDataset` IDs, so Phase 1 should preserve `GeoDataset` as the downstream-facing identity even while removing route/model-name coupling.

### Phase 0 dependency matrix

| Current coupling point | Replacement target | Compatibility strategy | Phase 1 owner/file targets |
|---|---|---|---|
| `GeoDataset.model_name` and `GIS_SOURCE_MODELS` in `maps/models.py` | Registry metadata that describes backend type and dataset identity independently of Python model names | Keep `model_name` only as a temporary compatibility field while new metadata-backed routes come online | `maps/models.py`, `maps/migrations/`, `maps/forms.py` |
| `GeoDataset.get_absolute_url()` resolves via `reverse(self.model_name)` | Dataset-scoped route resolved by dataset identity such as `pk` or slug | Preserve legacy named map routes as compatibility aliases or redirects until templates and links move over | `maps/models.py`, `maps/urls.py`, `maps/views.py` |
| `FilteredMapMixin.get_dataset()` uses `GeoDataset.objects.get(model_name=self.model_name)` | Generic runtime lookup by dataset identity with backend adapter resolution | Keep model-bound map subclasses only as temporary wrappers around the new dataset runtime path | `maps/views.py`, `maps/mixins.py` |
| `GeoDataSetModelForm` and `GeoDataSetFilterSet` expose `model_name` as a first-class user choice | Backend metadata, dataset category, or adapter-backed dataset type fields that reflect the registry contract | Continue accepting `model_name` in old forms/filters only until equivalent metadata fields exist and list filtering is migrated | `maps/forms.py`, `maps/filters.py`, `maps/models.py` |
| `maps/templates/maps/geodataset_list.html` displays `object.model_name` as dataset type | Dataset type or backend summary derived from registry metadata | Render both values temporarily if needed while existing rows are backfilled | `maps/templates/maps/geodataset_list.html`, `maps/models.py` |
| Hardcoded route names such as `name="NutsRegion"` in `maps/urls.py` plus plugin-mounted source map routes | One generic dataset route family for list/detail/table/map, with optional source-domain overlays on top | Treat existing hardcoded and plugin routes as compatibility surface until dataset-scoped navigation is stable | `maps/urls.py`, `maps/views.py`, `sources/registry.py` |
| `MapMixin.get_map_configuration()` derives `model_name` from `self.model.__name__` and resolves `ModelMapConfiguration` plus `api_basename` assumptions | Map configuration resolution keyed by dataset registry identity or explicit dataset backend metadata rather than Django model class name | Keep existing model-based map configuration lookup as a fallback during migration | `maps/views.py`, `maps/models.py`, `maps/serializers.py` |
| Tests in `maps/tests/test_views.py` and `maps/tests/test_filters.py` create datasets with `model_name` and assert routes like `reverse("NutsRegion")` | Tests centered on dataset-scoped routes, adapter-backed lookup, and metadata-driven filtering | Retain a small compatibility test slice while the new registry path is introduced | `maps/tests/test_views.py`, `maps/tests/test_filters.py` |
| `inventories` selects datasets by `GeoDataset` FK and ID-driven autocomplete/configuration flows | Keep `GeoDataset` as the stable downstream-facing selection object, then add version/current-selection semantics later | Do not break `GeoDataset` foreign key usage in Phase 1; layer version-aware selection on top in a later phase | `inventories/models.py`, `inventories/forms.py`, `inventories/views.py` |

### Phase 0 immediate conclusions from the audit

- **`GeoDataset` should remain the stable downstream-facing dataset object**
  - Inventory integration already points in that direction, so the refactor should decouple routing/runtime access from `model_name` without replacing `GeoDataset` as the main selection object.

- **The first implementation boundary is route/runtime decoupling, not federation**
  - The most immediate architectural mismatch is that dataset navigation, map lookup, filters, and tests are still keyed by `model_name` and hardcoded route names.

- **The first concrete documentation debt is the README mismatch**
  - Phase 1 should either make the documented metadata-driven path true or narrow the README until the implementation catches up.

### Phase 0 status checkpoint and retrospective

- **Phase 0 is now complete**
  - The discovery and audit portion is complete.
  - The remaining architecture-boundary decisions for Tasks 0.4, 0.5, and 0.6 have now been recorded in this document.

- **Completed in Phase 0 so far**
  - `GeoDataset` has been confirmed as the stable downstream-facing dataset object rather than a throwaway wrapper around hardcoded model routes.
  - Runtime coupling to `model_name`, `GIS_SOURCE_MODELS`, CamelCase route names, and model-based map configuration has been audited and captured in one place.
  - The mismatch between the current `maps/README.md` onboarding story and the implemented runtime path is now explicit.
  - A dependency matrix now identifies the main replacement targets and compatibility surfaces for Phase 1.
  - The minimum Phase 1 metadata contract has now been defined for the first local registry slice.
  - The dataset runtime adapter boundary is now defined for the generic map, table, and detail surfaces.
  - Model placement and compatibility policy are now settled well enough to start Phase 1 without structural ambiguity.

- **What Phase 0 taught us**
  - The biggest blocker is not federated storage itself; it is the fact that dataset identity, routing, and view lookup are still entangled with Django model names.
  - `GeoDataset` already behaves like the correct downstream selection object in `inventories`, which means the safest migration path is to preserve that identity while replacing the runtime plumbing behind it.
  - The current compatibility surface is broader than one field or one route: it spans forms, filters, templates, tests, map configuration lookup, and plugin-mounted map URLs.
  - Documentation drift is a first-class planning signal here: the README already describes a target architecture that the runtime has not fully implemented, so Phase 1 must either fulfill or narrow that promise quickly.

- **Immediate consequence for the next phase**
  - Phase 1 can now focus on implementation rather than further Phase 0 clarification work.
  - The next step is to build the first local registry-backed runtime slice against the contract and compatibility policy defined here.

- **Exit recommendation**
  - Treat Phase 0 as complete and use this document as the entry baseline for Phase 1 execution.
  - Reopen Phase 0 only if implementation uncovers a missing architectural decision rather than a normal Phase 1 design refinement.

Success criteria:

- there is one agreed-on starting-point document or issue summary
- the current gap between README promise and implementation is explicit
- the target architecture vocabulary is stable enough for incremental work

## Phase 1 - Finish the local metadata-driven dataset registry

Goal: make ordinary local tables/views explorable without code changes.

Deliverables:

- extend the dataset metadata model so the table/view-backed path is real, not only documented
- support authoritative normalized storage of:
  - backend/runtime relation metadata
  - schema/table identifier
  - geometry column
  - primary key column
  - label/display configuration
  - one row per exposed dataset column with explicit visibility and query/export policy
- implement safe schema introspection for local PostGIS relations
- implement generic table/detail/map querying from registry metadata
- make `GeoDataset.get_absolute_url()` independent from `model_name`
- reduce `GIS_SOURCE_MODELS` to compatibility-only status or remove it where safe

### Phase 1 implementation tasks

- **Task 1.1 - Refactor `GeoDataset` into a real registry contract**
  - Update the model layer so the local table/view-backed path is represented by authoritative runtime metadata instead of being described only in documentation.
  - Preserve a minimal compatibility story where needed, but stop treating `model_name` as the primary runtime identity for new generic exploration.
  - Use normalized subordinate models from the beginning for backend/relation metadata and per-column exposure policy instead of `JSONField` or parallel allowlist arrays on `GeoDataset`.
  - Primary file targets:
    - `maps/models.py`
    - `maps/migrations/`
    - `maps/forms.py`
    - `maps/admin.py`

- **Task 1.2 - Introduce true dataset-scoped generic routes**
  - Add the generic dataset detail, table, and map route shape needed by the registry so users can open a dataset by stable dataset identity rather than by a hardcoded model-specific map name.
  - Existing CRUD/list/gallery routes for `GeoDataset` should remain aligned with this new runtime surface rather than pointing users back into model-bound paths.
  - Primary file targets:
    - `maps/urls.py`
    - `maps/views.py`

- **Task 1.3 - Replace `model_name`-based dataset resolution in map views**
  - Rework the current `FilteredMapMixin` pattern so the generic map surface resolves datasets by dataset identity instead of `GeoDataset.objects.get(model_name=...)`.
  - The Phase 1 implementation should prove that at least one real dataset can be rendered without introducing a bespoke view subclass for that dataset.
  - Primary file targets:
    - `maps/views.py`
    - `maps/mixins.py`

- **Task 1.4 - Implement the first generic local backend/query path**
  - Deliver one backend path for local PostGIS tables or views that supports schema introspection, safe filtering derived from normalized dataset-column policy, geometry access, pagination, and single-feature lookup.
  - This first slice should validate the registry runtime without yet taking on federation, advanced import orchestration, or harmonization logic.
  - The pilot should use a deliberately simple relation or view with one geometry column, one primary key, scalar visible fields, and a small allowlisted filter set.
  - Any richer provider data should be prepared into a trusted view before registration rather than making the generic runtime support joins or user-defined expressions.
  - Primary file targets:
    - `maps/views.py`
    - `maps/viewsets.py`
    - `maps/filters.py`
    - `maps/mixins.py`

- **Task 1.5 - Make map configuration compatible with runtime datasets**
  - Update map-configuration resolution so a dataset registered at runtime can still participate in the normal map rendering flow without depending on a fixed model-name-driven API basename.
  - This is the point where generic routing and generic map configuration must meet cleanly.
  - Primary file targets:
    - `maps/models.py`
    - `maps/views.py`
    - `maps/viewsets.py`

- **Task 1.6 - Repoint user-facing dataset navigation to the generic runtime surface**
  - Update list/gallery/detail navigation so user-facing dataset cards lead to the dataset-driven table/map/detail flow, not to legacy `model_name`-backed URLs.
  - This keeps the Maps UX aligned with the registry architecture rather than hiding legacy coupling behind the main user entry points.
  - Primary file targets:
    - `maps/templates/maps/geodataset_list.html`
    - `maps/templates/maps/geodataset_gallery.html`
    - any new or updated dataset runtime templates in `maps/templates/maps/`

- **Task 1.7 - Keep inventory coupling stable for now, but document the next boundary**
  - Continue letting inventories reference `GeoDataset` during the first local-registry slice, but document clearly that version-pinning and current-version selection are later-phase concerns.
  - The Phase 1 goal is to avoid breaking downstream dataset references while still moving the registry toward stable dataset identity.
  - Do not make inventories depend on `GeoDatasetRuntimeConfiguration` directly; inventories should keep selecting the logical dataset until the version/current binding contract is introduced.
  - Primary file targets:
    - `inventories/models.py`
    - `inventories/views.py`
    - `inventories/forms.py`
    - this roadmap document

- **Task 1.8 - Add regression tests and one real pilot dataset demonstration**
  - Add tests that prove the new dataset path works end-to-end for a local PostGIS relation without relying on `model_name` lookup, and that field exposure obeys normalized per-column policy records.
  - The phase should end with one real pilot example that demonstrates the architecture rather than only a model refactor.
  - Include negative tests for unexposed columns, missing runtime metadata, missing geometry column, and invalid primary-key configuration so the first adapter fails safely.
  - Primary file targets:
    - `maps/tests/test_views.py`
    - `maps/tests/test_filters.py`
    - additional `maps/tests/` modules if needed

### Phase 1 status checkpoint

- **Task 1.1 is complete**
  - `GeoDataset` now stores runtime metadata through normalized subordinate models rather than flat runtime fields or JSON-style allowlists.
  - `GeoDatasetRuntimeConfiguration` now holds backend and relation metadata, while `GeoDatasetColumnPolicy` stores one row per exposed dataset column.
  - `maps/forms.py`, `maps/admin.py`, `maps/views.py`, and the runtime-metadata migration have been updated to use that normalized contract.
  - Focused Dockerized validation passed for `maps.tests.test_models`, `maps.tests.test_views`, `maps.tests.test_forms`, and `maps.tests.test_filters` using `brit.settings.testrunner`.

- **Task 1.2 route family is complete on the current compatibility-backed runtime path**
  - Dataset-scoped detail, map, table, and feature-detail routes now exist, including `geodataset-detail`, `geodataset-map`, `geodataset-table`, and `geodataset-feature-detail`.
  - `GeoDataset.get_absolute_url()` and `GeoDataset.get_map_url()` now prefer dataset identity where the route is available.
  - The current map/table/detail route family still resolves through compatibility runtime-model mappings and feature API basenames, so this is not yet the final generic table/view-backed runtime path.
  - The first table/detail slice uses `GeoDatasetColumnPolicy` visibility records for displayed fields and keeps feature navigation scoped by stable dataset identity.

- **Task 1.3 has started with an adapter boundary**
  - Dataset-scoped runtime views now resolve through a `maps.runtime_adapters.DatasetRuntimeAdapter` boundary instead of owning compatibility mapping logic directly in `maps.views`.
  - Compatibility-backed Django model datasets still use the existing model/filterset route behavior behind that boundary.

- **Task 1.4 has started with a local relation table/detail/map API query path**
  - `maps.runtime_adapters.LocalRelationDatasetRuntimeAdapter` can now read a configured local PostGIS relation/table through validated runtime metadata.
  - The first slice supports quoted schema/table/column identifiers, required metadata validation, selected visible columns, exact-match filters for explicitly filterable columns, bounded table reads, single-feature lookup, and dataset-scoped GeoJSON output from the configured geometry column.
  - Dataset-scoped table, feature-detail, map, and `geodataset-features-geojson` routes can render records from this adapter without a bespoke Django model or `model_name` lookup.
  - This is still a deliberately small local-relation slice; richer schema introspection, summaries, exports, and production pilot hardening remain follow-up work.

- **Current next step**
  - Continue Task 1.4 and Task 1.5 by hardening local-relation map configuration and proving the path with a boring pilot dataset.
  - Avoid expanding to federation, versioning, or domain harmonization until the local pilot is validated.

Success criteria:

- a new local PostGIS table can be registered and explored end-to-end with no code changes
- the README workflow becomes true in production code, not only aspirational
- at least one existing hardcoded map dataset can be re-expressed through the generic registry path

## Phase 2 - Harden safety, permissions, and observability

Goal: make dynamic exploration safe enough for broad internal use.

Deliverables:

- column allowlist and geometry allowlist enforcement
- safe publication checks that prevent exposing a dataset whose approved policy references missing or changed columns
- dataset-level health check in admin
- clear validation errors for missing relation, missing geometry field, invalid PK, unsupported types
- audit-friendly metadata showing who changed exposure settings and when
- schema drift status comparing the current relation to the last reviewed introspection snapshot
- performance safeguards:
  - max page size
  - bounded filter operators
  - bounded ordering and search fields
  - optional extent/count caching
- database operational safeguards:
  - expected indexes documented for primary key, geometry, and common filters
  - query timeouts or defensive limits for dynamic endpoints
- clear public/private/review behavior aligned with existing `UserCreatedObject` policy patterns where applicable

Success criteria:

- dynamic datasets fail safely and explain why
- sensitive/internal columns cannot leak through introspection alone
- publication cannot silently expose columns that were only discovered but never reviewed
- large datasets remain usable without accidental full-table scans in common views

## Phase 3 - Introduce federated database backends

Goal: allow selected external datasets to appear in BRIT without physical copy-first ingestion.

Deliverables:

- define operational support for read-only federation through PostgreSQL-native mechanisms first
- add backend metadata for foreign server / remote schema / foreign table identity where needed
- add admin guidance and validation for federated dataset registration
- distinguish live federated vs cached federated datasets in metadata and UI
- document operational requirements for DBAs/admins, including read-only credentials and ownership boundaries
- document the generalized source-connector contract so later authenticated WFS or file-download connectors can plug into the same registry without redesigning the user-facing dataset model

Success criteria:

- a read-only external PostGIS dataset exposed through approved database federation can be registered as a `GeoDataset`
- users can browse and filter it through the same baseline UI as local datasets
- the UI clearly indicates that the dataset is federated and whether results are live or cached
- the architecture is still ready for later non-database connectors without introducing a second competing dataset concept

## Phase 4 - Versioning, refresh, and reproducibility

Goal: support both live browsing and reproducible analytical use.

Deliverables:

- dataset version/snapshot model or equivalent version contract
- import-run model or equivalent refresh audit contract
- refresh metadata:
  - last refreshed
  - upstream last seen
  - refresh status
  - refresh mode
- import/update strategy classification per dataset, for example:
  - full replacement with immutable snapshots
  - moving current dataset plus periodic snapshots
  - incremental append with temporal semantics
- optional materialization flow for turning federated-live data into reproducible snapshots
- current-version binding so one stable dataset identity can resolve to the latest approved version without changing URLs
- ability for downstream consumers to select either current dataset or fixed snapshot

Success criteria:

- BRIT can support both exploratory live maps and reproducible inventory inputs without conflating the two
- dataset freshness and immutability are visible and machine-readable
- annual imported datasets do not need a brand-new top-level registry identity for each refresh
- historical imported releases can still be inspected or pinned when required

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
- demonstrate that at least one inventory-facing workflow can consume the resulting dataset contracts without bespoke model-name wiring

Success criteria:

- generic registry datasets and harmonized canonical datasets can coexist under one consistent dataset contract
- downstream modules no longer depend on Python model names for basic dataset selection
- at least one pilot domain such as roadside trees can be explored both as individual provider datasets and as one integrated cross-provider map
- the integrated map clearly distinguishes covered from not-yet-integrated regions
- the inventory app has a credible path to consume the same stable dataset and version contracts used by `maps`

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
| Stable registry contract supports multiple connector and ingestion modes |  |  |  |
| Dataset freshness/version semantics visible in UI |  |  |  |
| Imported datasets have explicit import-run and current-version contracts |  |  |  |
| Downstream consumers select datasets by stable dataset identity |  |  |  |
| Inventory app can evaluate registered and harmonized datasets through stable contracts |  |  |  |
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
- imported datasets can be refreshed without collapsing dataset identity and version into one concept
- the inventory app can consume the same registered datasets and harmonized views through stable contracts rather than bespoke source-specific glue
- at least one domain has a real integrated cross-provider analytical surface
- that integrated surface includes a map that shows integrated regions and grays not-yet-integrated ones

### 9.3 Anti-goals that indicate failure

The effort is drifting off course if:

- each new dataset still needs a new Django model or view class
- federation exists only as undocumented DBA magic outside the BRIT registry
- introspection exposes arbitrary columns by default
- live federated data and frozen snapshots are not distinguishable
- the README continues to promise behavior that the codebase does not actually implement
- each new source type requires inventing a separate user-facing dataset concept instead of plugging into the same core registry contract
- every annual import becomes a completely separate top-level dataset with no stable identity linking them
- refreshes overwrite imported data in place with no recoverable version boundary where reproducibility matters
- same-domain datasets remain explorable only in isolation with no path to an integrated analytical view
- the inventory app still needs source-specific one-off glue for ordinary dataset consumption because the registry contract is not actually stable enough
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

### 10.5 Connector proliferation risk

Supporting many upstream access patterns can devolve into a hard-to-maintain plugin zoo if BRIT does not define a strong common contract.

Mitigation direction:

- keep the core dataset registry and runtime adapter contract small and strict
- allow connector diversity mainly at the fetch/auth/refresh edge
- prefer materializing unusual sources into a standard internal representation when live querying would complicate the generic surfaces too much
- require every connector to expose the same provenance, refresh, and failure metadata to the registry

### 10.6 Reproducibility versus storage-cost trade-off

Keeping every imported release as an immutable snapshot improves auditability, rollback, and analytical reproducibility, but increases storage and operational complexity.

Mitigation direction:

- make snapshot retention policy explicit per dataset class
- default annual or formally released datasets toward immutable snapshots
- allow continuously refreshed operational datasets to keep only selected snapshots where full retention is not justified
- let high-value downstream workflows pin required versions before retention cleanup

### 10.7 Future extraction question: cross-cutting data-access layer

Phase 0 settled that the first registry implementation should stay in `maps` because `GeoDataset`, map configuration, and the current UX already live there.

The remaining question is whether a later phase should extract backend/runtime adapter infrastructure into a more cross-cutting data-access layer after the local registry path is proven.

Mitigation direction:

- keep `GeoDataset` as the stable user-facing object during Phase 1
- avoid leaking `maps` implementation details into inventories or source-domain apps
- revisit extraction only after there is at least one production-quality generic local backend and one clear non-maps consumer pressure

## 11. Recommended Next Slice

The next practical implementation slice should be narrow and reality-based:

- finish the dataset-scoped route family for the first production slice, especially table and feature-detail surfaces if they remain in Phase 1 scope
- implement one local relation/view-backed runtime adapter that does not depend on `model_name` compatibility mappings
- add safe introspection with non-exposed defaults and explicit `GeoDatasetColumnPolicy` promotion
- deliver one real end-to-end pilot where a deliberately simple PostGIS table or trusted view is registered and explored without code changes
- add negative tests for missing runtime metadata, invalid geometry/primary-key configuration, and unexposed-column access
- defer versioning, federation, and harmonized `roadside_trees` integration until the local adapter path is proven

That slice is small enough to validate the architecture and large enough to prove the core promise.
