# Waste Atlas selector plan

## Objective

Improve Waste Atlas map selection with a unified selector for:

- **Region**: the map set/geographic scope, such as Germany, Baden-Württemberg/Rheinland-Pfalz, Catalonia, Italy, South Tyrol, Sweden, Denmark, Netherlands, Belgium, and optionally Europe.
- **Theme**: the mapped information shown on the map, such as administrative level, collection systems, schedules, collection counts, fee systems, collection amounts, bin sizes, or collection points.
- **Year**: the data year passed to the selected map route.

The selector should reuse existing route-backed map pages and preserve region-specific behavior such as fixed NUTS scopes for South Tyrol, Baden-Württemberg/Rheinland-Pfalz, Catalonia, and Flanders/Brussels.

## Product decision: Region, not municipality catchment

The first selector field intentionally means atlas map set / geographic scope, not an individual BRIT catchment.

This keeps the current feature small/medium in complexity because the existing Waste Atlas pages are scope-level choropleths. Individual catchment selection would be a separate larger feature requiring autocomplete/search, selected-catchment highlight or zoom behavior, possible data filtering, and potentially API/frontend rendering changes.

## Scope

- Use a central registry for available region/theme route combinations.
- Include route availability in the registry because not every theme exists for every region.
- Show the selector on the Waste Atlas overview page.
- Show the same selector on individual map pages.
- Filter theme options by selected region.
- Navigate to the existing map route for the selected region and theme, preserving the selected year as a query parameter.
- Keep existing direct map links on the overview page during rollout.
- Preserve special route behavior by navigating to existing routes instead of forcing all selections through one generic endpoint.
- Do not implement municipality-level selector behavior in this phase.
- Do not replace existing API endpoints or map rendering templates.

## Registry target shape

The registry should remain the single authoritative place for selector availability, labels, and route names.

```python
WASTE_ATLAS_MAP_SELECTIONS = {
    "DE": {
        "label": "Germany",
        "themes": {
            "collection_system": {
                "label": "Biowaste collection systems",
                "route_name": "waste-atlas-germany-collection-system-map",
            },
        },
    },
}
```

The implemented registry currently uses separate label and route-name constants in `sources/waste_collection/waste_atlas/map_selection.py`. A later cleanup can consolidate that into the nested target shape if it improves maintainability.

## Existing duplicated knowledge to reduce

The selector registry is intended to reduce duplicated map-selection knowledge currently spread across:

- `overview.html` direct links
- `urls.py` route names
- `views.py` subclasses
- older Italy/South Tyrol-specific route metadata

## Special route behavior to preserve

- **Italy / South Tyrol**: separate routes, fixed regional scope for South Tyrol.
- **Baden-Württemberg & Rheinland-Pfalz**: fixed `nuts_prefix=DE1,DEB`, `nuts_level=1`.
- **Germany**: fixed Bundesland/NUTS-1 border behavior.
- **Catalonia**: fixed Catalonia scope.
- **Flanders + Brussels**: fixed Belgium sub-scope.

## Phases

### Phase 1: Metadata registry

Create a central registry for available regions, themes, labels, route names, and availability.

Status: **done**.

### Phase 2: Form on overview page

Add a prominent “Find map” form at the top of `overview.html` with:

- Region
- Theme, filtered by selected region
- Year
- Submit button navigating to the selected route with `?year=YYYY`

Keep the existing map directory below it during rollout.

Status: **done**.

### Phase 3: Shared selector on map pages

Replace the previous country/map-set + year controls in `choropleth_map.html` with:

- Region
- Theme
- Year

Preselect the current page’s region and theme from view context.

Status: **done**.

### Phase 4: JavaScript navigation update

Update `waste_atlas_choropleth.js` so the load/submit action:

- reads selected region
- reads selected theme
- reads selected year
- finds the selected registry route URL from option metadata
- navigates to the selected route with `?year=...` when the route changes
- reloads the current map data for year-only changes on the same route

Include tracked minified JavaScript output when the source changes.

Status: **done**.

### Phase 5: Tests

Add or update tests for:

- overview context and rendering includes selector options
- shared map template renders selector options
- selected current route/theme/region are preselected
- Germany, BW/RP, Italy, South Tyrol and other route-specific pages still expose correct fixed scope metadata
- year query behavior remains available through route navigation

Status: **partially done**. Focused view/template regression coverage exists. Browser-level navigation behavior and selected-year URL behavior still need manual or JavaScript-focused validation.

## Checklist

- [x] Create a central Waste Atlas map selection registry.
- [x] Expose selector context in the overview and map views.
- [x] Add the selector to the overview page.
- [x] Add the selector to individual map pages.
- [x] Update JavaScript navigation for region/theme/year selections.
- [x] Rename user-facing and internal selector terminology from mapped aspect to theme.
- [x] Filter unavailable theme combinations by selected region.
- [x] Add focused regression coverage for selector context and rendering.
- [x] Regenerate tracked minified JavaScript when the source changes.
- [x] Validate with focused Waste Atlas view tests.
- [ ] Manually test selector behavior in the browser for representative regions and themes.
- [ ] Manually verify year-only reload on the same route.
- [ ] Manually verify route changes preserve `?year=YYYY`.
- [ ] Decide whether Europe-level overview maps should be included in the selector registry.
- [ ] Decide whether generic country query-parameter maps should remain discoverable only through direct links or become explicit registry entries.
- [ ] Consider consolidating the registry into the nested `WASTE_ATLAS_MAP_SELECTIONS` target shape.
- [ ] Improve theme grouping or ordering if the flat theme list becomes hard to scan.
- [ ] Consider adding help text explaining that Region means map set/geographic scope, not municipality.
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
- `ce72136d docs: track waste atlas selector plan`
