# Waste Atlas selector plan

## Objective

Improve Waste Atlas map selection with a unified selector for:

- **Region**: the map set/geographic scope, such as Germany, Catalonia, Italy, South Tyrol, or other country-specific entries.
- **Theme**: the mapped information shown on the map, such as collection systems, schedules, fees, amounts, or bin sizes.
- **Year**: the data year passed to the selected map route.

The selector should reuse existing route-backed map pages and preserve region-specific behavior such as fixed NUTS scopes for South Tyrol, Baden-Württemberg/Rheinland-Pfalz, Catalonia, and Flanders/Brussels.

## Scope

- Use a central registry for available region/theme route combinations.
- Show the selector on the Waste Atlas overview page.
- Show the same selector on individual map pages.
- Navigate to the existing map route for the selected region and theme, preserving the selected year as a query parameter.
- Keep existing direct map links on the overview page.
- Do not implement municipality-level selector behavior in this phase.
- Do not replace existing API endpoints or map rendering templates.

## Checklist

- [x] Create a central Waste Atlas map selection registry.
- [x] Expose selector context in the overview and map views.
- [x] Add the selector to the overview page.
- [x] Add the selector to individual map pages.
- [x] Update JavaScript navigation for region/theme/year selections.
- [x] Rename user-facing and internal selector terminology from mapped aspect to theme.
- [x] Add focused regression coverage for the selector context and rendering.
- [x] Regenerate tracked minified JavaScript when the source changes.
- [x] Validate with focused Waste Atlas view tests.
- [ ] Manually test selector behavior in the browser for representative regions and themes.
- [ ] Decide whether Europe-level overview maps should be included in the selector registry.
- [ ] Decide whether generic country query-parameter maps should remain discoverable only through direct links or become explicit registry entries.
- [ ] Improve theme grouping or ordering if the flat theme list becomes hard to scan.
- [ ] Consider adding a small help text explaining that Region currently means map set/geographic scope, not municipality.
- [ ] Consider extracting shared selector markup into an include if more templates need it.

## Validation commands

Use Dockerized Django test runs.

```bash
docker compose exec web python manage.py test sources.waste_collection.tests.test_views.WasteAtlasMapViewsTestCase --keepdb --noinput --settings=brit.settings.testrunner --parallel 4
```

Check JavaScript syntax after changing the selector script.

```bash
node --check sources/waste_collection/waste_atlas/static/js/waste_atlas_choropleth.js
node --check sources/waste_collection/waste_atlas/static/js/waste_atlas_choropleth.min.js
```

Check whitespace before committing.

```bash
git diff --check
```

## Current implementation notes

- Registry file: `sources/waste_collection/waste_atlas/map_selection.py`
- Shared map-page template: `sources/waste_collection/waste_atlas/templates/waste_atlas/choropleth_map.html`
- Overview template: `sources/waste_collection/waste_atlas/templates/waste_atlas/overview.html`
- Selector JavaScript: `sources/waste_collection/waste_atlas/static/js/waste_atlas_choropleth.js`
- Focused test class: `sources.waste_collection.tests.test_views.WasteAtlasMapViewsTestCase`

## Commit history

- `c98d6edb feat: add waste atlas map selector`
- `d5b500b4 fix: rename waste atlas selector theme label`
- `56eaec01 refactor: use theme naming for atlas selector`
