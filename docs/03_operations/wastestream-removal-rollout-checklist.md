# Collection Waste Semantics Simplification Rollout Record

**Scope:** Issue #80 hardening for epic #71 (removal of `WasteStream` and direct `Collection` waste semantics in waste collection)  
**Date:** 2026-02-28  
**Status:** Completed 2026-04-09

## Outcome

The rollout to direct `Collection` waste semantics is complete.

- `Collection` now carries the relevant waste fields directly
- the legacy `WasteStream` runtime path has been removed from the active implementation
- production cutover and smoke checks completed successfully on 2026-04-09

This file is retained as a short operations record rather than an active rollout checklist.

## Completed verification themes

The completed rollout covered the following checks:

- test coverage for the waste-collection runtime after the semantics simplification
- migration and deployment verification
- collection create/update/copy/versioning smoke checks
- review/detail/API behavior checks
- waste-atlas behavior checks
- importer behavior checks without legacy `WasteStream` logic

## Remaining follow-up

The remaining work is post-cutover cleanup, not rollout execution:

1. Remove obsolete legacy `soilcom` content types and dependent permissions for retired waste-stream-related models in a dedicated follow-up.
2. Remove any remaining documentation/examples that still describe `WasteStream` as an active runtime concept.
3. Keep database cleanup separate from the completed rollout so recovery scope stays small and auditable.

## Usage note

Do not treat this file as a live deploy checklist.
If a future schema-removal rollout needs an operational checklist, create a new document specific to that change rather than reusing this completed record.
