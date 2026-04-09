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

## Execution tracking

The remaining post-cutover cleanup is tracked in GitHub issue #87.
This file remains a completed rollout record rather than a live follow-up checklist.

## Usage note

Do not treat this file as a live deploy checklist.
If a future schema-removal rollout needs an operational checklist, create a new document specific to that change rather than reusing this completed record.
