# Phyllis Import Quality Plan

**Last audit:** 2026-08-27  
**Overall owner:** to be assigned

## Purpose

This document tracks the work required to turn the current Phyllis import from a
private, provenance-preserving staging dataset into a semantically reliable BRIT
dataset that may eventually be submitted for review and publication.

The work is intentionally divided into separate sessions and pull requests. Do
not attempt to solve all workstreams in one change.

## Current status

**Overall status:** imported privately; suitable for raw-data review; not ready
for publication or normalized composition use.

| Concern | Current value |
|---|---:|
| Phyllis records | 3,288 |
| Materials | 1,494 |
| Component measurements | 47,955 |
| Property measurements | 6,948 |
| Raw source rows retained in payload | 56,610 |
| Unresolved source rows retained only in payload | 1,707 |
| Literature entries | 3,322 |
| Genuine sample dates mapped | 293 |
| Active analytical methods | 103 |
| Valid analytical-method assignments | 5,999 |
| Exact duplicate measurement rows | 3 |
| Samples with no measurements | 1 (`Phyllis #3511`) |

All imported reviewable objects are private and owned by `devin` in the isolated
local database. Production has not been modified.

## Decisions already made

The following decisions should be treated as the current baseline unless a later
review explicitly changes them.

- Each Phyllis record maps to one standalone BRIT `Sample`.
- Sample names use the normalized material name. When several source records
  share a material, a source-agnostic disambiguation suffix is derived from
  sample metadata (sample date, production date, country, sample location,
  producer, alternative name, literature, and description). A local disambiguator
  (`part <n>`) is used only when the available metadata is not sufficient. The
  Phyllis source ID lives only in `SampleExternalRecord`.
- The Phyllis permalink and raw metadata live in `SampleExternalRecord`; the
  import does not create one bibliography `Source` per sample.
- One shared `Source` represents the Phyllis2 database.
- Original observations are imported; calculated ar/daf display variants are
  retained in the raw payload rather than imported as duplicate measurements.
- Genuine `Sample date` values map to `Sample.datetime`; BRIT import timestamps
  are not shown as scientific dates.
- Original literature remains in the payload. Resolved DOI titles are displayed
  before supporting author/year/journal lines.
- `Measured`, `Calculated`, `Unknown`, `Average`, `method added`, and
  `as received (ar)` are not analytical methods.
- Clear method spelling variants are canonicalized conservatively; standard
  editions and national adoptions remain distinct.
- Superseded imported objects are archived rather than deleted.
- Raw source values are never silently corrected.

## Verified strengths

- The raw payload preserves metadata and all ar/dry/daf source columns, so the
  import can be reprocessed without scraping again.
- The selected dry observation is consistent with Phyllis documentation for all
  19,766 rows containing both dry and calculated daf values.
- All normalizable source units are explicitly recognized by the importer.
- Physical-property rows do not contain competing non-formula values in multiple
  basis columns.
- Active analytical methods have no duplicate names, status-label assignments,
  blank descriptions, or generic import descriptions.
- Import SQL is transactional, defaults to rollback, and is idempotent for new
  external record IDs.
- The current import remains private, which prevents known semantic issues from
  affecting public users.

## Publication blockers

The following issues block publication. They are ordered by priority rather than
implementation difficulty.

| ID | Priority | Workstream | Repository | Status | Blocks publication |
|---|---|---|---|---|---|
| PH-00 | P0 | Persist and package the current implementation | BRIT + BRIT-data | In progress | Yes |
| PH-01 | P0 | Stop unsafe automatic composition normalization | BRIT | Not started | Yes |
| PH-02 | P0 | Display and handle censored values correctly | BRIT | Not started | Yes |
| PH-03 | P0 | Add importer validation and quarantine reports | BRIT-data | Not started | Yes |
| PH-04 | P1 | Redesign component groups, bases, and aggregates | BRIT + BRIT-data | Not started | Yes |
| PH-05 | P1 | Make measurement re-imports update-safe | BRIT-data, possibly BRIT | Not started | Yes |
| PH-06 | P1 | Curate canonical components, properties, groups, and units | BRIT-data | Not started | Yes |
| PH-07 | P2 | Map useful sample metadata and material categories | BRIT + BRIT-data | Not started | Yes |
| PH-08 | P2 | Harden review and publication workflow | BRIT | Not started | Yes |
| PH-09 | P2 | Refresh source snapshot and confirm reuse rights | Operations/data governance | Not started | Yes |
| PH-10 | P3 | Refine names, descriptions, literature, and methods | BRIT-data | Partially complete | No |

## PH-00 — Persist and package the current implementation

**Goal:** ensure the importer, schema, and review UI survive worktree cleanup and
can be reproduced from Git.

**Why first:** the original app worktree was pruned before its uncommitted changes
were preserved. The database volume survived, but the model and migration files
did not.

**Scope**

- Separate the public BRIT schema/UI changes from private BRIT-data importer
  changes.
- Commit focused branches in both repositories.
- Add exact setup and verification commands to the eventual PR descriptions.
- Confirm generated agent bootstrap files are not included in either commit.
- Confirm the import can be recreated in a fresh worktree and empty database.

**Acceptance criteria**

- A fresh BRIT checkout contains migrations 0021/0022 and passes migration checks.
- A fresh BRIT-data checkout can generate the staging bundle from ignored raw
  input.
- A fresh isolated database imports 3,288 records with the expected measurement
  counts.
- A second import creates no duplicate records.

## PH-01 — Stop unsafe automatic composition normalization

**Goal:** prevent mathematically invalid normalized charts while retaining raw
measurements.

**Evidence**

| Group | Sample groups | Groups over 100% | Maximum calculated total |
|---|---:|---:|---:|
| Chemical Elements | 2,855 | 1,899 | 121,129% |
| Biochemical Composition | 829 | 593 | 451% |
| Proximate Analysis | 2,555 | 996 | 196% |
| Ash Composition | 549 | 53 | 132% |
| Particle Size Distribution | 24 | 3 | 291% |
| Special Components | 49 | 1 | 859% |

BRIT currently sums every positive component, chooses the most common basis when
bases differ, and fills totals below 100% with `Other`. It does not reject totals
above 100% or exclude aggregate components.

**Recommended first session**

- Add an explicit group-level normalization policy, for example
  `normalization_kind = disabled | closed_composition`.
- Mark all imported Phyllis groups `disabled` initially.
- Continue showing raw measurement tables.
- When normalization is disabled, show a neutral explanation instead of a chart.

**Acceptance criteria**

- No Phyllis sample displays a normalized composition by default.
- Raw data remains visible and exportable.
- Existing non-Phyllis normalization behavior remains unchanged.
- Focused tests cover disabled groups and legacy enabled groups.

## PH-02 — Display and handle censored values correctly

**Goal:** stop presenting thresholds and detection limits as exact observations.

**Evidence**

- 881 component measurements are `less_than`.
- 15 component measurements are `below_detection_limit`.
- 3 property measurements are `less_than`.
- 45 ash-temperature properties are `greater_than`.
- Current templates, serializers, exports, and normalization use `average`
  without applying `value_qualifier`.

**Scope**

- Add a shared display value that prefers `raw_value` for non-exact records.
- Show `<`, `>`, and detection-limit semantics in classic and v2 detail views.
- Include qualifier, raw value, and detection limit in read serializers and Excel
  exports.
- Exclude non-exact values from composition normalization by default.
- Decide separately how censored values participate in statistical aggregates.

**Open decision**

Choose and document one statistical policy for aggregate calculations:

- omit censored observations;
- use the limit as a conservative bound;
- use a substituted fraction of the limit; or
- calculate interval/bound results.

No policy should be applied silently.

**Acceptance criteria**

- `<0.1 mg/kg` is never displayed as exact `0.1 mg/kg`.
- `>1450 °C` retains its greater-than qualifier.
- Detection limits appear in UI/API/export.
- Normalization emits an explicit warning or excludes qualified values.

## PH-03 — Import validation and quarantine

**Goal:** distinguish preserved source anomalies from values safe for BRIT
calculations.

**Observed anomalies**

- 72 negative component values.
- 22 negative standard deviations.
- 3 negative detection limits.
- 567 `Total (with halides)` values above 100%.
- 62 `Total ash + biochemical` values above 100%.
- Particle-size bins above 200%.
- Elemental concentrations above 1,000,000 mg/kg.
- `Phyllis #3636` contains `Total (with halides) = 60,577.75%` and
  `Chlorine = 602,740,000 mg/kg`.

**Scope**

- Generate a machine-readable validation report before SQL generation.
- Classify findings as blocking errors, review warnings, or informational notes.
- Preserve rejected rows in `SampleExternalRecord.payload`.
- Do not create normalized measurement rows for blocking anomalies.
- Include source ID, term, raw value, basis, unit, and rule ID in every finding.

**Initial rules to evaluate**

- Component percentage outside 0–100.
- Negative concentration, standard deviation, or detection limit.
- Concentration above physical mass-equivalence limits.
- Closed composition total outside an agreed tolerance.
- Aggregate total inconsistent with its constituents.
- Unknown unit, section, basis, or measurement route.

**Acceptance criteria**

- Full-import validation is deterministic and tested.
- Blocking anomalies are counted and listed before any database transaction.
- Operators must explicitly acknowledge or resolve blocking findings.
- No source value is silently changed.

## PH-04 — Component groups, bases, and aggregates

**Goal:** represent analytical domains without double counting or mixing
incompatible bases.

**Required design work**

- Treat `Availability` as non-compositional concentration data.
- Treat `Special Components` as raw/non-compositional unless a closed definition
  exists.
- Decide whether proximate analysis is raw property data or a composition derived
  through explicit dry↔fresh conversion.
- Retain original biochemical subsections rather than collapsing amino acids,
  fatty acids, carbohydrates, lignin, C5/C6 totals, and other analyses into one
  group.
- Mark `Total...` and `Sum...` terms as aggregate components and exclude them from
  sums of their constituents.
- Normalize only measurements sharing one compatible basis.

**Current basis issue**

`Proximate Analysis` contains 5,059 dry-matter and 1,489 fresh-matter
measurements. Of 2,555 sample/group combinations, 1,438 contain multiple bases.
The current majority-basis heuristic does not perform a conversion.

**Candidate safe groups**

`Ash Composition` and `Particle Size Distribution` may become closed
compositions after aggregate exclusion and total validation. They should remain
disabled until tests establish their invariants.

**Acceptance criteria**

- Every enabled group has a documented closure rule and basis.
- Mixed-basis groups never normalize without an explicit conversion.
- Aggregate and single components are distinguishable.
- Totals over 100% produce no chart and a clear validation result.

## PH-05 — Update-safe re-imports

**Goal:** ensure corrected source workbooks update normalized database rows.

**Current problem**

Existing external records receive updated payloads, names, descriptions, and
method metadata, but measurement inserts are restricted to new external IDs. A
corrected Phyllis value therefore leaves stale component/property rows in BRIT.

**Design options**

1. Add an external measurement record keyed by source record and source row.
2. For importer-owned samples, transactionally replace all normalized
   measurements when the source workbook hash changes.
3. Implement a full field-level upsert using a stable source row key.

Option 2 is simplest if imported measurements cannot be manually edited. Option
1 is safer if curation edits must survive source refreshes.

**Acceptance criteria**

- A test changes one source value and reruns the importer.
- The database measurement and payload both reflect the change.
- Removed source rows no longer remain as active measurements.
- Unchanged workbooks produce no writes.
- Manually curated data has an explicit preservation policy.

## PH-06 — Canonical term curation

**Goal:** integrate imported definitions into BRIT semantics rather than retaining
source labels only.

**Current state**

- 173 used components have generic descriptions.
- No used component has `comparable_component` configured.
- 25 used properties have generic descriptions.
- No used property has `comparable_property` configured.
- Seven component groups and four property groups have generic descriptions.
- Ten imported units have generic descriptions.
- No imported component is marked `aggregate`, despite total/sum terms.

**Scope**

- Build a reviewed mapping table in BRIT-data.
- Reuse exact canonical BRIT definitions where appropriate.
- Create source-term aliases linked through comparable fields where names differ.
- Keep chemically distinct entities separate, for example elemental chlorine,
  chloride, and chlorine-bearing compounds.
- Add concise source-neutral descriptions.
- Mark aggregate components explicitly.

**Acceptance criteria**

- Every imported term is classified as canonical, alias, aggregate, or
  intentionally source-specific.
- Mapping changes are reviewable as data, not hidden in procedural code.
- No ambiguous mapping is applied automatically.

## PH-07 — Sample metadata and material categories

**Goal:** make imported records discoverable and scientifically contextualized.

**Unmapped metadata currently retained only in payload**

| Metadata | Records containing it |
|---|---:|
| Sample location | 270 |
| Country | 451 |
| Source description | 669 |
| Remarks | 1,528 |
| Production date | 427 |
| Ash type | 706 |
| Sample lot size | 116 |
| Producer | 103 |
| Combustion temperature | 112 |

All 3,288 BRIT sample descriptions currently contain only a generic import
sentence. All 1,494 imported materials have no BRIT category.

**Scope**

- Map sample location and country without conflating them.
- Replace generic sample descriptions with concise source descriptions and
  relevant remarks.
- Display production date, ash type, producer, and sample method as structured
  external metadata where no BRIT field exists.
- Design a Phyllis classification-to-BRIT category mapping.
- Do not classify every record as `Bioresource`; the dataset includes plastics,
  recovered fuels, and other non-biogenic materials.
- Decide whether the metadata-only `Phyllis #3511` sample belongs in analytical
  lists.

**Acceptance criteria**

- Available location/date/description metadata is visible and searchable.
- Material category filters include imported records appropriately.
- Classification mappings retain their source scheme.
- Metadata-only records are explicitly labeled or excluded from analytical lists.

## PH-08 — Review and publication workflow

**Goal:** prevent incomplete dependency graphs or invalid derived data from being
published.

**Risks**

- Imported samples have no explicit `Composition` rows; charts are inferred from
  raw measurements.
- Current sample approval checks do not validate inferred totals, mixed bases, or
  censored values.
- Samples may link to private components, properties, groups, units, methods, or
  sources that public users cannot open.
- Analytical method review actions cascade to linked sources.

**Scope**

- Add a pre-publication validation report for samples and dependencies.
- Define review order for source, units, groups, terms, methods, materials, then
  samples.
- Prevent sample approval when required linked definitions are not published.
- Prevent approval when enabled normalized groups fail invariants.
- Confirm `SampleExternalRecord` intentionally inherits visibility from its
  parent sample rather than having a separate review lifecycle.

**Acceptance criteria**

- A published sample has no inaccessible linked definitions.
- Publication cannot bypass normalization and qualifier validation.
- Bulk review actions are auditable and use the four-eyes workflow.

## PH-09 — Source refresh and data governance

**Goal:** establish whether the dataset may be redistributed and which snapshot is
being published.

**Current discrepancy**

- Imported snapshot: 3,288 records.
- Phyllis colophon on 2026-08-26: 3,289 biomasses, 49,024 values.
- The site reports that the database was modified on 2026-08-26.
- The colophon asserts TNO copyright but does not state an explicit redistribution
  licence.

**Scope**

- Confirm reuse and redistribution rights with TNO or authoritative licence text.
- Refresh the scrape after permission and compare IDs/hashes with the current
  snapshot.
- Record acquisition date, source version, tool version, and hashes in the
  manifest.
- Decide whether withdrawn or corrected Phyllis records must be archived in BRIT.

**Acceptance criteria**

- Written licence/reuse basis is recorded.
- The imported snapshot matches the intended source release.
- Refresh and deletion/correction policies are documented and tested.

## PH-10 — Lower-priority refinements

Completed or partially completed:

- Material-first sample names without the Phyllis source ID; disambiguation uses
  source-agnostic sample metadata and falls back to a local index only when
  necessary.
- Genuine sample dates in lists.
- Source-neutral material descriptions.
- Phyllis permalinks through external records.
- Literature title resolution for known DOIs and legacy database URLs.
- Removal of method-status labels.
- Conservative analytical-method spelling normalization.
- Short analytical-method descriptions.

Remaining refinements:

- Review capitalization of proper nouns and scientific names after automated
  sentence-case normalization.
- Consolidate author/year/journal lines into structured citations.
- Replace generic method descriptions for vague labels such as `16 EPA` and
  `Sugar Analysis` with expert-reviewed definitions.
- Validate new DOI titles during future source refreshes.

## Sequencing

### Phase A — Preserve and stop misleading output

1. PH-00: persist current implementation.
2. PH-01: disable unsafe normalization.
3. PH-02: display qualifiers correctly.
4. PH-03: add deterministic quarantine reporting.

### Phase B — Correct import semantics

5. PH-04: redesign groups, bases, and aggregates.
6. PH-05: make re-imports update-safe.
7. PH-06: curate canonical terms.

### Phase C — Prepare for review and publication

8. PH-07: map metadata and categories.
9. PH-08: harden publication workflow.
10. PH-09: refresh source and resolve licensing.
11. PH-10: finish presentation refinements.

No workstream in Phase C should begin publication while any P0 or P1 blocker is
open.

## Session template

Use this checklist when starting a workstream in a new session.

```text
Workstream: PH-XX — <title>
Repository: BRIT | BRIT-data | both

Scope:
- <one narrowly defined behavior>

Out of scope:
- <related topics intentionally deferred>

TDD plan:
1. Add the smallest failing test.
2. Run the focused target.
3. Implement the minimal change.
4. Run nearby tests and repository checks.

Data validation:
- Expected rows before:
- Expected rows after:
- Rollback rehearsal:
- Idempotency check:

Acceptance criteria:
- [ ] ...

Planning update:
- Mark PH-XX status and record PR/issue references in this document.
```

## Status vocabulary

Use only these status values in the tracking table:

- `Not started`
- `Discussion`
- `Ready`
- `In progress`
- `Blocked`
- `In review`
- `Completed`
- `Deferred`

## Definition of ready for publication

The Phyllis dataset is ready to enter bulk review only when all of the following
are true:

- All P0 and P1 workstreams are completed.
- No unsafe normalized composition is displayed.
- Censored values are visibly and computationally distinguished from exact
  observations.
- Import validation has no unacknowledged blocking findings.
- Re-import tests prove source corrections update database measurements.
- Canonical term and category mappings have been reviewed.
- Public samples cannot reference inaccessible private dependencies.
- The current source snapshot and redistribution rights are documented.
- A fresh-database import and second-run idempotency rehearsal both pass.
