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
   - The URL matches the selected route plus `?year=<year>` (regional maps also append `country=` / `nuts_level=`).
   - The page heading matches the selected map title.
   - The selectors remain on the requested Region/Waste category/Theme/Year.
   - The hidden `atlas-config` JSON has the expected `country`, `nutsPrefix`, and `nutsLevel` for locked regional maps.

## Clean unified layout checks (post-overhaul)

The overview is intentionally a calm, unified layout: NO colored topic pills/badges, NO
topic-color legend row, plain typographic map links (`.atlas-map-link` inside
`.atlas-map-list`), and quiet underline region tabs (`data-bs-toggle="tab"`). Map-page
"Related maps" use the same plain-link treatment (`.atlas-map-list--inline`).

Verify quickly in the browser console on the overview page (expected: the "noise" counts
are all 0, link counts are large):

```js
JSON.stringify({
  topicChips: document.querySelectorAll('[class*="atlas-topic-"]').length,   // expect 0
  outlineBtns: document.querySelectorAll('.btn-outline-primary').length,      // expect 0
  legend: document.querySelectorAll('.atlas-topic-legend').length,            // expect 0
  badges: document.querySelectorAll('.badge').length,                         // expect 0
  mapLinks: document.querySelectorAll('.atlas-map-link').length,              // expect many (>100)
  tabsToggle: document.querySelector('#atlas-region-tabs .nav-link')?.getAttribute('data-bs-toggle') // expect "tab"
})
```

To prove tabs switch one pane at a time, click a tab (e.g. "Other countries") then check
exactly one pane is visible:

```js
JSON.stringify({
  visiblePanes: [...document.querySelectorAll('.tab-pane')].filter(p=>p.classList.contains('show')&&p.classList.contains('active')).map(p=>p.id), // expect length 1
  totalPanes: document.querySelectorAll('.tab-pane').length
})
```

On a map page, related maps should be plain links, not chips:

```js
JSON.stringify({
  relatedChips: document.querySelectorAll('.atlas-related-maps .btn, .atlas-related-maps [class*="atlas-topic-"]').length, // expect 0
  relatedPlainLinks: document.querySelectorAll('.atlas-related-maps .atlas-map-link').length // expect many
})
```

## API-level testing (viewset / query changes)

For changes to `waste_atlas/viewsets.py` (e.g. query scoping, filtering, new endpoints), test via shell commands — no browser recording needed.

### Creating test data via Django shell

Use the BRIT-ops Compose wrapper to run Django shell commands:

```bash
/home/ubuntu/BRIT-ops/scripts/brit-worktree-compose /home/ubuntu/repos/BRIT exec -T web python manage.py shell -c "<python code>"
```

Key models and relationships for test data:
- `Region` needs `country='XX'` set for country-based filtering to work
- `CollectionCatchment` needs `region=<region>` to link catchments to a country
- `Collection` needs `catchment`, `waste_category`, `valid_from`, and `publication_status`
- `WasteCategory` name must match endpoint filters (e.g. `"Biowaste"` or `"Food waste"` for collection-system endpoint — see `_select_primary_collections()` calls in viewsets.py)
- For GeoJSON endpoints, the Region needs a `GeoPolygon` with actual geometry (`borders=<geopolygon>`)
- Use a fake country code like `'ZZ'` to avoid colliding with real data

### Hitting API endpoints

Waste atlas API endpoints are public (no auth required):

```bash
curl -s http://localhost:8000/waste_collection/api/waste-atlas/<endpoint>/?country=ZZ&year=2025 | python3 -m json.tool
```

Key endpoints:
- `collection-system/` — filters by `["Biowaste", "Food waste"]` waste categories
- `catchment/geojson/` — returns GeoJSON FeatureCollection with catchment geometry
- `collector-orga-level/` — collector organization level
- `collection-orga-level/` — collection organization level
- `connection-type/` — connection type per catchment
- `collection-conflicts/` — conflicting collection systems

### Adversarial pattern for scoping changes

When testing publication scoping or similar filtering:
1. Create objects with multiple filter states (e.g. published, private, review)
2. Hit the API and verify the response count matches only the included state
3. The adversarial check: without the fix, N items would appear; with the fix, only 1

## Caveats

- Local snapshot data may render selector state, config, legend, and export controls but no catchment geometry. The map page commonly shows a red `500 Error loading map data` banner — this is a local data limitation, NOT a UI defect. Record it explicitly instead of claiming full choropleth rendering was verified.
- CI `lint` and `test` are frequently red for reasons unrelated to UI changes: the whole `test` job can error with `TypeError: AbstractConnection.__init__() got an unexpected keyword argument 'ssl_cert_reqs'` (a redis-py incompatibility affecting ~1800+ tests). Confirm such failures are preexisting (also on `main`) before attributing them to a PR; `verify-assets` and `migrations` should pass. Prefer running focused tests locally via the worktree test script over trusting CI for the atlas suite.
- After editing `waste_atlas.css`, rebuild assets with `make assets` so `waste_atlas.min.css` (which the templates link) is regenerated; the `verify-assets` CI check fails otherwise.
- Do not run Django app commands with host Python. Use the BRIT-ops Compose wrapper.
