# Sources Plugin Decoupling Roadmap

**Status:** Proposed
**Date:** 2026-04-09
**Related:** `2026-02-10_sources_consolidation_plan.md`

## Context

The large consolidation into `sources.*` is complete enough that `sources` now owns the canonical runtime surface for the built-in source domains.
The latest completed slice made the core registry discovery-driven and moved file-export registration behind the shared plugin contract instead of hard-coded imports.

That means the codebase has moved from **"apps live under `sources`"** to the next stage: **"the core `sources` app acts as a dynamic hub for pluggable source-domain apps"**.

This roadmap covers the remaining work needed to finish that decoupling in small, safe slices.

## Goals

- Remove remaining hard-coded knowledge of built-in source-domain apps from `sources` core code.
- Keep the `sources` app responsible for hub behavior, not domain-specific implementation details.
- Make plugin contributions explicit, discoverable, and testable.
- Preserve compatibility during the transition with minimal blast radius.
- Enable future third-party or optional source-domain apps to participate without editing core registry code.

## Non-goals

- Rewriting domain apps into a generic abstraction layer.
- Renaming public URL names unless there is a strong compatibility reason.
- Deleting compatibility surfaces before their replacements are proven by tests and documentation.

## Current State

Completed already:

- Canonical source-domain ownership now lives under `sources.greenhouses`, `sources.roadside_trees`, `sources.waste_collection`, and `sources.urban_green_spaces`.
- `sources.registry` discovers plugins from installed apps via `<app>.plugin`.
- `utils.file_export.registry_init` discovers optional plugin-side `EXPORTS` metadata.
- The `sources` README now documents the plugin contract and discovery model.

Still coupled or partially coupled:

- Some hub features still assume specific plugin capabilities indirectly instead of through explicit metadata.
- URL ownership is only partially centralized behind the `/sources/` hub.
- Built-in plugins still rely on conventions that are not fully validated by shared tooling.
- Compatibility surfaces and documentation still reflect a hybrid transitional architecture.

## Guiding Principles

- Prefer small compatibility-preserving slices.
- Move responsibility to plugin-owned modules before deleting legacy paths.
- Add contract tests before widening the plugin surface.
- Keep `sources` core focused on orchestration, discovery, and shared UX.
- Do not introduce a plugin capability until at least one real consumer exists.

## Phase 1: Harden the plugin contract

**Objective:** Make the current plugin system safer and more explicit before more features depend on it.

### Deliverables

- Define which `SourceDomainPlugin` fields are required, optional, and capability-gated.
- Add shared validation helpers for duplicate slugs, invalid mount paths, and inconsistent capability declarations.
- Decide whether plugin discovery should stay import-time cached or move to lazy evaluation with explicit caching.
- Add tests for malformed plugins and partial plugin modules.

### Recommended slices

1. Add registry validation for duplicate `slug` values and invalid `mount_path` combinations.
2. Add capability-specific validation, for example:
   - `mount_in_hub=True` requires `mount_path`
   - explorer participation requires both `explorer_context_var` and `published_count_getter`
3. Add a documented rule for optional modules such as `exports.py`.
4. Add a single smoke test that loads all installed source plugins and validates the full contract.

### Exit criteria

- Core discovery fails fast with clear errors for malformed plugins.
- Plugin contract expectations are documented and enforced by tests.

## Phase 2: Move remaining core integrations behind plugin metadata

**Objective:** Replace remaining built-in assumptions in shared code with plugin-owned declarations.

### Likely integration points

- Sources explorer cards and counters
- Hub navigation and labels
- Optional API/router contributions
- Optional admin registrations or review integrations
- Optional management-command discovery hooks
- Optional map or inventory integration points

### Deliverables

- Inventory all remaining `sources` and shared-code imports that directly reference built-in source domains.
- For each remaining integration, choose one of:
  - plugin metadata field
  - plugin-owned optional module
  - keep as intentionally non-pluggable core behavior
- Remove hard-coded lists once an equivalent plugin-driven path exists.

### Recommended slices

1. Add a discovery inventory doc or checklist of remaining direct imports.
2. Convert one integration at a time, starting with read-only/UI-facing behavior.
3. Keep each new plugin contribution surface narrow and real-world-driven.
4. Delete superseded hard-coded registration code in the same change.

### Exit criteria

- No core `sources` module needs to import a built-in domain app directly for shared orchestration concerns.
- The remaining direct imports are intentional and documented.

## Phase 3: Finish hub ownership of routes and entrypoints

**Objective:** Make `/sources/` the canonical source-domain hub while preserving compatibility.

### Deliverables

- Decide which built-in source apps should mount in the hub now versus later.
- Move remaining canonical public entrypoints under `/sources/` where appropriate.
- Keep old prefixes as redirects during the compatibility window.
- Document which URL names remain stable and which paths are canonical.

### Recommended slices

1. Evaluate each built-in plugin for `mount_in_hub` readiness.
2. Add or refine redirect coverage for legacy prefixes.
3. Ensure templates and docs link to canonical `/sources/` entrypoints.
4. Add routing tests that assert both canonical paths and compatibility redirects.

### Exit criteria

- Canonical user-facing source entrypoints are discoverable from the hub.
- Legacy prefixes are compatibility layers, not competing primary surfaces.

## Phase 4: Shrink the core app to hub responsibilities only

**Objective:** Keep domain-specific behavior inside plugins and shared behavior inside the hub.

### Deliverables

- Clarify what belongs in `sources` core:
  - plugin discovery
  - hub URLs
  - explorer composition
  - shared contracts
  - shared integration helpers
- Clarify what belongs in plugin apps:
  - domain URLs/views/templates/static
  - exports
  - domain-specific selectors/helpers
  - optional integration modules
- Move any remaining domain-specific logic out of `sources` core modules.

### Recommended slices

1. Audit `sources/views`, `sources/urls`, `sources/tests`, and shared adapters for domain leakage.
2. Move leaked behavior into plugin-owned modules.
3. Keep only generic composition logic in the hub.
4. Update README examples to reflect the boundary.

### Exit criteria

- `sources` core reads like a hub/orchestration package, not a domain implementation package.
- Each built-in source domain can explain its integration through its own `plugin.py` and optional companion modules.

## Phase 5: Remove transitional compatibility layers

**Objective:** Retire temporary shims once the plugin-driven architecture is stable.

### Deliverables

- Delete obsolete compatibility re-exports and dead adapter modules.
- Remove stale references to transitional architecture from docs.
- Simplify tests that only exist to protect already-retired compatibility layers.

### Recommended slices

1. Remove one compatibility layer at a time.
2. Run focused domain tests plus the full Docker `web` suite after each removal batch.
3. Update documentation and migration notes in the same PR.

### Exit criteria

- Transitional shims no longer shape runtime architecture.
- The plugin-driven path is the only supported implementation path.

## Phase 6: Operational hardening

**Objective:** Make the plugin architecture safe to evolve.

### Deliverables

- Add regression tests for discovery order, contract validation, and optional-module loading.
- Add developer guidance for creating a new source-domain plugin.
- Add release-check guidance for plugin-related changes.

### Suggested verification checklist

- `manage.py test sources.tests utils.file_export.tests --settings=brit.settings.testrunner`
- targeted domain tests for any plugin touched
- full Docker `web` suite before major contract changes
- `makemigrations --check --dry-run`

### Exit criteria

- Adding a new plugin or modifying a capability has a documented and tested workflow.

## Recommended Order of Work

1. Harden the plugin contract.
2. Inventory and convert remaining hard-coded integrations.
3. Centralize canonical hub entrypoints and redirects.
4. Remove domain leakage from `sources` core.
5. Delete transitional compatibility layers.
6. Finish operational documentation and regression coverage.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Plugin contract grows too quickly | Over-abstraction and fragile APIs | Add new fields only for proven integration needs |
| Discovery errors appear only at runtime | Broken pages or startup failures | Add fail-fast validation and smoke tests |
| Canonical URLs drift from legacy routes | Broken links and confusion | Keep redirect tests and document canonical paths |
| Optional modules become implicit magic | Hard-to-debug integration behavior | Document naming conventions and validate capability/module alignment |
| Cleanup stalls after partial success | Long-term maintenance burden | Remove superseded code in the same PR whenever a replacement is complete |

## Definition of Done

This roadmap is complete when:

- `sources` core contains no unnecessary built-in domain imports.
- Built-in source domains participate through the same plugin contract expected of future plugins.
- Canonical hub routing and explorer composition are plugin-driven.
- Transitional re-exports and obsolete shims are removed.
- Developer documentation explains how to add or modify a source-domain plugin without editing core registries.
