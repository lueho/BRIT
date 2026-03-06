# WasteStream Removal Rollout & Rollback Checklist

**Scope:** Issue #80 hardening for epic #71 (`WasteStream` removal in soilcom)
**Date:** 2026-02-28
**Owners:** Maintainer + reviewer on duty

## 1) Pre-rollout checks

- [ ] Confirm code includes direct `Collection` waste fields (`waste_category`, `allowed_materials`, `forbidden_materials`).
- [ ] Confirm cleanup migration exists and is reviewed (`0012_remove_wastestream_model`).
- [ ] Confirm stale runtime imports/references to `WasteStream` are removed.
- [ ] Confirm backups/snapshots are available for target database.
- [ ] Confirm deployment window and rollback owner are assigned.

## 2) Validation before deploy

Run in Docker:

```bash
docker compose exec web python manage.py test --keepdb --noinput --settings=brit.settings.testrunner --parallel 4
```

- [ ] Full suite is green.
- [ ] Focused soilcom suites pass (forms/views/filters/serializers/viewsets/importers).
- [ ] No migration conflicts in target branch.

## 3) Deploy steps

- [ ] Deploy application image/revision.
- [ ] Run DB migrations:

```bash
docker compose exec web python manage.py migrate
```

- [ ] Verify app startup and worker startup.
- [ ] Verify no migration/runtime errors in logs.

## 4) Post-deploy smoke tests

- [ ] Collection create/update/copy/versioning works.
- [ ] Collection detail/review pages render with inline material data.
- [ ] API payloads include expected waste fields.
- [ ] Waste-atlas endpoints return expected classification semantics.
- [ ] Import workflow succeeds without `WasteStream` creation logic.

## 5) Monitoring window (first 24h)

- [ ] Monitor web logs for template/query errors.
- [ ] Monitor Celery logs for importer/cache tasks.
- [ ] Watch for elevated error rate or slow queries in atlas/filter endpoints.

## 6) Rollback plan

Use rollback only for severe production regressions that cannot be patched quickly.

### A. Preferred: roll forward with hotfix

- [ ] Triage regression and patch quickly.
- [ ] Re-run focused tests.
- [ ] Deploy hotfix.

### B. Full rollback path

- [ ] Put app into maintenance mode (or halt writes).
- [ ] Redeploy previous known-good application revision.
- [ ] Restore database from pre-rollout backup/snapshot if schema/data requires reversal.
- [ ] Run smoke tests for core user paths.
- [ ] Communicate incident + recovery status.

## 7) Closeout

- [ ] Add deployment notes to issue #80.
- [ ] Record final sign-off in issue #71 child issues.
- [ ] Archive this checklist reference in operations notes for future major schema removals.
