# Sources Plugin Decoupling Roadmap

**Status:** Proposed
**Date:** 2026-04-09
**Related:** `2026-02-10_sources_consolidation_decision_record.md`

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

## Execution tracking

Active implementation follow-up for this roadmap is now tracked in GitHub issue #86.
This document remains the architectural roadmap and target-state reference rather than a live execution checklist.

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
