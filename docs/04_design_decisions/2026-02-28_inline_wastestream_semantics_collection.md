# Inline WasteStream Semantics into Collection

**Status:** Accepted
**Date:** 2026-02-28
**Related issues:** #71 (epic), #72 (ADR), #73/#74/#75/#76/#77/#78/#79/#80

## Context

Historically, `case_studies.soilcom.Collection` referenced an intermediate `WasteStream` model for:
- waste category
- allowed materials
- forbidden materials

This indirection increased complexity across forms, views, filters, serializers, importer logic, query paths, tests, admin wiring, and migration handling.

At current usage, the intermediate model did not provide sufficient domain value to justify this complexity.

## Decision

Store waste semantics directly on `Collection` and remove runtime dependency on `WasteStream`.

`Collection` is the canonical source of truth for:
- `waste_category`
- `allowed_materials`
- `forbidden_materials`

Implementation is phased:
1. Add inline fields and backfill from legacy `waste_stream`.
2. Migrate read/write paths to direct fields.
3. Remove `Collection.waste_stream` and delete `WasteStream` model.
4. Harden with regression tests and rollout checklist.

## Alternatives considered

1. Keep `WasteStream` unchanged
   - Pros: no migration effort.
   - Cons: preserves broad code complexity and ongoing maintenance cost.

2. Keep `WasteStream` but hide behind helper APIs
   - Pros: less invasive than schema change.
   - Cons: retains relational indirection and migration burden; does not simplify data model.

3. Denormalize only for reads (materialized projection)
   - Pros: faster reads in some endpoints.
   - Cons: dual-source drift risk, write complexity, and higher operational burden.

## Consequences and trade-offs

### Positive
- Simpler domain model for collections.
- Cleaner query paths for filters, atlas endpoints, and serializers.
- Fewer moving parts in importer and form save flows.
- Lower long-term maintenance and onboarding cost.

### Negative / Risks
- Data migration correctness is critical.
- Temporary transition complexity in compatibility phase.
- Potential subtle behavior regressions in exports and API payloads.

Mitigation:
- Backfill migration before deletion migration.
- Regression tests across forms/views/filters/serializers/importer/atlas.
- Full-suite validation in Docker test environment.

## Rollout phases

1. **Schema phase**
   - Add direct fields to `Collection`.
   - Backfill from legacy relations.

2. **Compatibility/migration phase**
   - Migrate runtime read/write paths to direct fields.
   - Verify parity via focused tests.

3. **Cleanup phase**
   - Remove `Collection.waste_stream` field.
   - Delete `WasteStream` model.
   - Remove obsolete test/admin/signal/task references.

4. **Hardening phase**
   - Resolve regressions.
   - Run full test suite.
   - Update docs and operations checklist.

## Rollback strategy

If severe regression is detected after deployment:

1. Stop rollout and prevent further writes.
2. Revert application code to pre-removal revision.
3. If schema rollback is required, restore from verified pre-deploy DB backup/snapshot.
4. Re-run smoke and regression checks.
5. Resume rollout only after root-cause fix is validated.

Notes:
- Roll-forward is preferred when feasible.
- Because model deletion is destructive at schema level, tested backup/restore is mandatory.

## Validation

Expected quality gate for this decision:

```bash
docker compose exec web python manage.py test --keepdb --noinput --settings=brit.settings.testrunner --parallel 4
```

## Follow-up

- Keep this ADR as canonical architectural rationale for #71 child issue work.
- Record team sign-off and any exceptions in issue comments (GitHub #72 / #71).
