# Sources Module Consolidation Decision Record

**Date:** 2026-02-10
**Status:** Completed 2026-04-09 (historical decision record; follow-up cleanup may still continue)
**Decision:** Option A — consolidate all source-type apps into `sources/`
**Context:** Sources domain ontology (Section 9 of UX Harmonization Guideline),
Geodataset Harmonization Pipeline proposal

---

## 1. Decision

Consolidate the three case-study apps (`case_studies.soilcom`,
`case_studies.flexibi_nantes`, `case_studies.flexibi_hamburg`) into the `sources/`
app. The `sources/` app becomes the single home for all source-type models,
views, URLs, and the future ingestion pipeline.

**Rationale:** These apps are currently organized by project origin (SOILCOM,
FLEXIBI Nantes, FLEXIBI Hamburg) rather than by domain concept (sources of
bioresources). As the platform evolves, the project origin becomes less relevant
and the domain concept becomes the primary organizing principle.

## 2. Current State at Decision Time

```
sources/                             # Shell: TemplateView explorer only
case_studies/
├── soilcom/                         # Waste collection (5,800 LOC + 8,300 test LOC)
├── flexibi_nantes/                  # Greenhouses     (1,400 LOC +   185 test LOC)
└── flexibi_hamburg/                 # Roadside trees   (  580 LOC +   320 test LOC)
```

Total: ~7,800 lines source + ~8,800 lines tests = ~16,600 lines to move.

Database tables: `soilcom_*`, `flexibi_nantes_*`, `flexibi_hamburg_*`.

## 2a. Current Runtime Architecture (2026-04-09)

The consolidation is now complete at the runtime level.

- `sources.waste_collection`, `sources.greenhouses`, `sources.roadside_trees`, and `sources.urban_green_spaces` own the canonical source-domain runtime surface
- the `soilcom`, `flexibi_nantes`, and `flexibi_hamburg` migration-history transitions are complete
- `waste_collection`, `greenhouses`, `roadside_trees`, and `urban_green_spaces` use clean baselines aligned to their current schema ownership
- temporary migration shims used during the transition have been retired from active settings/runtime

The `sources` hub itself is now discovery-driven rather than hard-coding built-in domain apps:

- installed source-domain apps publish a `SourceDomainPlugin` in `<app>.plugin`
- the hub discovers plugins from installed apps at runtime
- optional export adapters are discovered through `<app>.exports` when a plugin declares the `exports` capability

This plugin/discovery model is now the authoritative architecture for the `sources` package.

## 2b. Current URL and Ownership Notes

The canonical implementation lives under `sources.*`, but some public compatibility entrypoints still remain:

- `/sources/` provides the hub-mounted source-domain surface
- `/waste_collection/` still points at `sources.waste_collection.urls`
- `/case_studies/nantes/` still points at `sources.greenhouses.urls`
- `/case_studies/hamburg/` still routes through `sources.roadside_trees.legacy_urls`

This means the consolidation is complete in terms of module ownership, while some legacy public prefixes remain intentionally for compatibility.

## 3. Remaining Follow-up Cleanup

The remaining work is cleanup, not architectural migration:

1. Convert remaining legacy public prefixes into pure redirects or retire them once it is safe to do so.
2. Remove remaining compatibility re-exports and legacy package seams after confirming fresh database setup and the relevant Dockerized test coverage stay green.
3. Remove leftover legacy `soilcom` database artifacts in a dedicated follow-up:
   - empty tables `soilcom_georeferencedcollector` and `soilcom_georeferencedwastecollection`
   - obsolete `soilcom` content types and dependent permissions for retired models
4. Continue trimming documentation and examples that still describe the transition-era architecture as if it were current.

## 4. Scope of This Record

This document is a completed decision record, not a step-by-step migration playbook.
Detailed bridge-phase execution notes, rollout checklists, and superseded target-state sketches have been removed so the file reflects the current architecture and the remaining cleanup only.
