---
name: testing-waste-atlas
description: Test Waste Atlas map selector flows and regional map pages end-to-end in the local BRIT worktree.
---

Use this skill when validating Waste Atlas UI changes, especially new regional map sets or selector/theme routing.

## Devin Secrets Needed

- None for local browser testing after the BRIT cloud snapshot is built.
- The repo blueprint uses `BRIT_OPS_REPO_URL` to set up BRIT-ops before sessions; this should already be configured in Devin secrets.

## Local setup

1. Start services through the isolated BRIT-ops wrapper:

```bash
/home/ubuntu/BRIT-ops/scripts/brit-worktree-compose /home/ubuntu/repos/BRIT up -d db redis web celery
```

2. If the browser needs an authenticated Waste Atlas user, create a local-only test account in the running app database:

```bash
/home/ubuntu/BRIT-ops/scripts/brit-worktree-compose /home/ubuntu/repos/BRIT exec -T web python manage.py shell -c "from django.contrib.auth.models import Group, User; group, _ = Group.objects.get_or_create(name='waste_atlas'); user, _ = User.objects.get_or_create(username='devin_atlas_tester', defaults={'email': 'devin-atlas@example.test'}); user.set_password('devin-atlas-password'); user.is_staff = True; user.is_superuser = True; user.save(); user.groups.add(group); print('local_waste_atlas_user_ready')"
```

This password is local development-only and is not a real secret.

3. Log in at `http://localhost:8000/users/login/` with `devin_atlas_tester` / `devin-atlas-password`.

## Useful URLs

- Overview: `http://localhost:8000/waste_collection/api/waste-atlas/map/`
- Map route pattern: `/waste_collection/api/waste-atlas/map/<region>/<theme>/?year=<year>`
- Change map overview: `/waste_collection/api/waste-atlas/map/changes/`

## Selector-flow testing pattern

1. Open the Waste Atlas overview.
2. Use the visible selectors rather than direct URLs:
   - Region
   - Waste category
   - Theme
   - Year
3. Click `Go` and verify:
   - The URL matches the selected route plus `?year=<year>`.
   - The page heading matches the selected map title.
   - The selectors remain on the requested Region/Waste category/Theme/Year.
   - The hidden `atlas-config` JSON has the expected `country`, `nutsPrefix`, and `nutsLevel` for locked regional maps.

## Caveats

- Local snapshot data may render selector state, config, legend, and export controls but no catchment geometry. If SVG geometry is empty, record that limitation explicitly instead of claiming full choropleth rendering was verified.
- Do not run Django app commands with host Python. Use the BRIT-ops Compose wrapper.
