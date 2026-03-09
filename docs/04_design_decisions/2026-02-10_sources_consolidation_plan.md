# Sources Module Consolidation Plan

**Date:** 2026-02-10
**Status:** In progress (adapter-first transition underway)
**Decision:** Option A — consolidate all source-type apps into `sources/`
**Context:** Sources domain ontology (Section 9 of UX Harmonization Guideline),
Geodataset Harmonization Pipeline proposal

---

## 1. Decision

Consolidate the three case-study apps (`case_studies.soilcom`,
`case_studies.flexibi_nantes`, `case_studies.flexibi_hamburg`) into the `sources/`
app. The `sources/` app becomes the single home for all source-type models,
views, URLs, and the future ingestion pipeline.

**Rationale:** These apps are currently organized by project origin (SOILCOM,
FLEXIBI Nantes, FLEXIBI Hamburg) rather than by domain concept (sources of
bioresources). As the platform evolves, the project origin becomes less relevant
and the domain concept becomes the primary organizing principle.

## 2. Current State

```
sources/                             # Shell: TemplateView explorer only
case_studies/
├── soilcom/                         # Waste collection (5,800 LOC + 8,300 test LOC)
├── flexibi_nantes/                  # Greenhouses     (1,400 LOC +   185 test LOC)
└── flexibi_hamburg/                 # Roadside trees   (  580 LOC +   320 test LOC)
```

Total: ~7,800 lines source + ~8,800 lines tests = ~16,600 lines to move.

Database tables: `soilcom_*`, `flexibi_nantes_*`, `flexibi_hamburg_*`.

## 2a. Current Execution Strategy

Rather than moving models, app labels, and URL ownership all at once, the
refactor is currently proceeding through small compatibility slices that:

- introduce thin `sources.*` adapter modules around existing
  `case_studies.*` implementations
- rewire shared entrypoints to import through `sources` first
- preserve legacy runtime compatibility where serialized paths or URL prefixes
  still exist
- validate each slice with focused Docker `web` tests and a full Docker `web`
  suite run before commit

This reduces blast radius and prepares the codebase for the later
`SeparateDatabaseAndState` migration phases without forcing model or app-label
moves prematurely.

## 2b. Progress Update (2026-03-08)

Validated and committed slices completed so far:

- scaffolded nested domain apps under `sources`
- routed Sources explorer counts through domain selectors
- discovered nested `sources.*.inventory.algorithms` modules during inventory
  discovery
- routed maps GeoJSON helpers through `sources` adapters
- routed the review dashboard fallback through `sources` selectors
- routed the export registry through `sources` export adapters
- routed case-study URLs through `sources` URL adapters
- delegated inventory entrypoints through `sources` inventory adapters while
  preserving legacy task-reference lookup compatibility
- routed Hamburg and Nantes domain-model access in shared code and tests
  through `sources` model adapters
- routed waste-collection domain-model access in shared code and tests through
  `sources` model adapters
- routed shared geojson and export serializer imports through `sources`
  serializer adapters
- routed shared export filter and renderer imports through `sources`
  filter/renderer adapters
- routed the remaining shared direct waste-collection view import through a
  `sources` view adapter, leaving only intentional thin adapters and adapter
  regression tests referencing `case_studies`
- made `sources.roadside_trees` the authoritative owner of the Hamburg
  URL/view/router surface while preserving legacy `case_studies.flexibi_hamburg`
  modules as compatibility re-exports
- made `sources.greenhouses` the authoritative owner of the Nantes
  URL/view/router surface while preserving legacy `case_studies.flexibi_nantes`
  modules as compatibility re-exports
- made `sources.waste_collection` the authoritative owner of the waste
  collection URL/view/router surface while preserving legacy
  `case_studies.soilcom` modules as compatibility re-exports
- added `forms` and waste-collection `tasks` adapters so the new
  `sources`-owned greenhouse and waste-collection views no longer import those
  seams directly from `case_studies.*`
- added domain `viewsets` adapters so `sources`-owned routers no longer import
  those seams directly from `case_studies.*`
- converted the top-level `sources.views` and `sources.models` shims into
  package-backed entrypoints to prepare for the later package-based app
  structure without changing runtime behavior
- added the remaining empty top-level `sources` package scaffolding
  (`forms`, `filters`, `serializers`, `viewsets`, and `renderers`) so the
  package layout now matches the planned bridge-phase target shape more closely
- moved the Hamburg model classes into `sources.roadside_trees.models` while
  preserving the existing `flexibi_hamburg_*` physical table and index names,
  converted `case_studies.flexibi_hamburg.models` into a compatibility
  re-export, and added paired state/content-type migrations for the new
  `roadside_trees` app label
- moved the remaining small Hamburg implementation modules (`filters`,
  `serializers`, `viewsets`, `renderers`, and inventory `algorithms`) into
  `sources.roadside_trees`, leaving the legacy `case_studies.flexibi_hamburg`
  modules as thin compatibility re-exports
- added source-owned copies of the Hamburg map templates under
  `sources.roadside_trees/templates/` so Django now resolves those templates
  from the `sources` app path first while preserving behavior
- added source-owned Hamburg filter/serializer/view test coverage under
  `sources/tests/` while keeping the legacy Hamburg tests in place for
  compatibility during the transition
- exposed the Hamburg roadside-tree URL surface through the top-level
  `sources/urls.py` so `/sources/roadside_trees/...` now works alongside the
  existing `/maps/hamburg/...` and legacy `/case_studies/hamburg/...` routes
- converted `/case_studies/hamburg/...` into a redirecting compatibility layer
  that now forwards the legacy Hamburg routes to the canonical `sources`
  entrypoints while preserving query strings
- added source-owned copies of the Hamburg roadside-tree JS assets under
  `sources.roadside_trees/static/js/` so Django now resolves those static files
  from the `sources` app path first as well
- moved the remaining greenhouse implementation modules (`forms`, `filters`,
  `serializers`, `viewsets`, `renderers`, and inventory `algorithms`) into
  `sources.greenhouses`, leaving the legacy `case_studies.flexibi_nantes`
  modules as thin compatibility re-exports
- moved the waste-collection `renderers`, Celery `tasks`, API `viewsets`, and
  `serializers` into `sources.waste_collection`, leaving the legacy
  `case_studies.soilcom` modules as thin compatibility re-exports while
  preserving the legacy task patch surface used by tests
- moved the waste-collection `filters` into `sources.waste_collection`,
  leaving the legacy `case_studies.soilcom.filters` module as a thin
  compatibility re-export while preserving the existing helper filter import
  surface used by tests and view patches
- moved the waste-collection `forms` into `sources.waste_collection`, leaving
  the legacy `case_studies.soilcom.forms` module as a thin compatibility
  re-export while preserving the existing choice-constant and Celery task patch
  surface used by tests
- removed `case_studies.flexibi_hamburg` from `INSTALLED_APPS` by introducing a
  `sources.legacy_flexibi_hamburg` migration shim that keeps the
  `flexibi_hamburg` migration label mapped to the legacy migration module while
  moving Hamburg admin registration into `sources.roadside_trees.admin`
- removed `case_studies.flexibi_nantes` and `case_studies.soilcom` from
  `INSTALLED_APPS` by introducing shim app configs under `sources` that keep
  their legacy app names, migrations, admin autodiscovery, and Soilcom signal
  registration active while decoupling settings registration from the
  `case_studies` package
- completed the Nantes and Soilcom model-ownership handoff into
  `sources.greenhouses` and `sources.waste_collection` while preserving the
  legacy `flexibi_nantes_*` and `soilcom_*` table names plus the legacy
  migration-module labels through `SeparateDatabaseAndState` handoff migrations
- copied the required Nantes and Soilcom template/static assets into `sources`,
  added source-side Soilcom management-command wrappers, and pinned the moved
  waste-collection views to their copied legacy template paths where Django
  could no longer infer them from the new app labels
- updated the review-context API enrichment checks so source-owned
  `waste_collection` review objects receive the same Collection flyer and
  CollectionPropertyValue parent/timeline context as the legacy Soilcom models
- validated the Nantes and Soilcom ownership-transfer slice with focused
  Nantes/Soilcom suites, the full Docker `web` suite, and
  `makemigrations --check --dry-run` for `greenhouses`, `waste_collection`,
  `flexibi_nantes`, and `soilcom`

## 3. Target State

```
sources/
├── apps.py                          # SourcesConfig
├── models/
│   ├── __init__.py                  # Re-exports all models
│   ├── waste_collection.py          # Collection, CollectionPropertyValue, Collector, ...
│   ├── greenhouses.py               # Greenhouse, Culture, GrowthCycle, ...
│   ├── roadside_trees.py            # HamburgRoadsideTrees, HamburgGreenAreas
│   └── pipeline.py                  # DataSourceConfig (future)
├── views/
│   ├── __init__.py
│   ├── explorer.py                  # SourcesExplorerView
│   ├── waste_collection.py          # Collection CRUD, explorer, list views
│   ├── greenhouses.py               # Greenhouse CRUD, list, map views
│   └── roadside_trees.py            # Map views
├── forms/
│   ├── __init__.py
│   ├── waste_collection.py
│   └── greenhouses.py
├── filters/
│   ├── __init__.py
│   ├── waste_collection.py
│   ├── greenhouses.py
│   └── roadside_trees.py
├── serializers/
│   ├── __init__.py
│   ├── waste_collection.py
│   ├── greenhouses.py
│   └── roadside_trees.py
├── viewsets/
│   ├── __init__.py
│   ├── waste_collection.py
│   ├── greenhouses.py
│   └── roadside_trees.py
├── renderers/
│   ├── __init__.py
│   ├── waste_collection.py
│   ├── greenhouses.py
│   └── roadside_trees.py
├── admin.py
├── signals.py
├── tasks.py
├── utils.py
├── algorithms.py                    # Merged from flexibi_nantes + flexibi_hamburg
├── router.py                        # DRF router for all source-type APIs
├── urls.py                          # All source-type URL patterns
├── templates/
│   ├── sources_explorer.html
│   ├── sources_list.html            # Legacy (kept for external links)
│   └── sources/                     # Source-type-specific templates
│       ├── waste_collection/        # Renamed from soilcom/
│       ├── greenhouses/             # Renamed from flexibi_nantes/
│       └── roadside_trees/          # Renamed from flexibi_hamburg/ (if any)
├── static/
│   └── (merged from all three apps)
├── tests/
│   ├── __init__.py
│   ├── test_waste_collection_models.py
│   ├── test_waste_collection_views.py
│   ├── test_waste_collection_forms.py
│   ├── test_waste_collection_filters.py
│   ├── test_waste_collection_serializers.py
│   ├── test_waste_collection_signals.py
│   ├── test_waste_collection_review_cascade.py
│   ├── test_waste_collection_versioning_views.py
│   ├── test_greenhouse_views.py
│   ├── test_greenhouse_serializers.py
│   ├── test_roadside_trees_views.py
│   └── ...
└── migrations/
    └── (new migrations using SeparateDatabaseAndState)
```

## 4. Database Migration Strategy

Django names tables as `<app_label>_<model_name>`. Moving models from
`case_studies.soilcom` to `sources` would change table names (e.g.,
`soilcom_collection` → `sources_collection`).

**Strategy: Keep existing table names using `db_table` Meta option.**

```python
class Collection(NamedUserCreatedObject):
    class Meta:
        db_table = "soilcom_collection"  # Preserve existing table name
```

This avoids data migration entirely. The tables stay where they are in the
database; only the Python code moves to a new app.

For the Django migration history, use `SeparateDatabaseAndState` to tell Django
the models moved without actually altering the database:

```python
# sources/migrations/0002_move_waste_collection_models.py
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("sources", "0001_initial"),
        ("soilcom", "NNNN_last_migration"),
    ]

    state_operations = [
        migrations.CreateModel(
            name="Collection",
            fields=[...],  # Copy from soilcom migration
            options={"db_table": "soilcom_collection"},
        ),
        # ... all other models
    ]

    operations = [
        migrations.SeparateDatabaseAndState(state_operations=state_operations),
    ]
```

Combined with a corresponding migration in `soilcom` that removes the models
from its state (also using `SeparateDatabaseAndState` with `database_operations=[]`).

## 5. URL Migration Strategy

Current URL mounting in `brit/urls.py`:

```python
path("waste_collection/", include("case_studies.soilcom.urls")),
path("case_studies/nantes/", include("case_studies.flexibi_nantes.urls")),
path("case_studies/hamburg/", include("case_studies.flexibi_hamburg.urls")),
path("sources/", include("sources.urls")),
```

Target:

```python
path("sources/", include("sources.urls")),
# Keep old URL prefixes as redirects for backwards compatibility
```

**URL name preservation:** All existing URL names (`collection-list`,
`greenhouse-list`, `HamburgRoadsideTrees`, etc.) are preserved unchanged.
Only the import paths change. This means no template or reverse() changes
are needed for URL names.

**URL prefix migration:** The URL prefixes change:
- `/waste_collection/...` → `/sources/waste_collection/...`
- `/case_studies/nantes/...` → `/sources/greenhouses/...`
- `/case_studies/hamburg/...` → `/sources/roadside_trees/...`

Old prefixes get `RedirectView` patterns for backwards compatibility.

## 6. Cross-App Import Updates

External files that import from the three apps (outside their own code/tests):

| File | Current import | New import |
|---|---|---|
| `sources/views.py` | `from case_studies.soilcom.models` | `from sources.models` |
| `sources/views.py` | `from case_studies.flexibi_nantes.models` | `from sources.models` |
| `maps/tasks.py` | `from case_studies.soilcom.models` | `from sources.models` |
| `maps/tasks.py` | `from case_studies.flexibi_hamburg.models` | `from sources.models` |
| `maps/tasks.py` | `from case_studies.soilcom.serializers` | `from sources.serializers` |
| `maps/tasks.py` | `from case_studies.flexibi_hamburg.serializers` | `from sources.serializers` |
| `maps/utils.py` | `from case_studies.soilcom.models` | `from sources.models` |
| `utils/file_export/registry_init.py` | all three apps | `from sources.*` |
| `utils/object_management/views.py` | `from case_studies.soilcom.models` | `from sources.models` |
| `utils/object_management/tests/*` (6 files) | `from case_studies.soilcom.models` | `from sources.models` |
| `utils/tests/test_serializers.py` | `from case_studies.soilcom.models` | `from sources.models` |
| `layer_manager/tests/test_models.py` | `from case_studies.flexibi_hamburg.models` | `from sources.models` |
| `brit/urls.py` | `include("case_studies.*.urls")` | `include("sources.urls")` |
| `brit/settings/*.py` | `case_studies.soilcom` in INSTALLED_APPS | `sources` |

## 7. Implementation Phases

### Bridge Phase: adapter-first transition (current)

- [x] Scaffold nested domain apps under `sources`
- [x] Add selector adapters for shared source-domain entrypoints
- [x] Add GeoJSON helper adapters for shared map entrypoints
- [x] Add export adapters for shared file-export entrypoints
- [x] Add URL adapters for existing Hamburg, Nantes, and waste-collection
  mount points
- [x] Add inventory-algorithm adapters and route inventory resolution through
  them
- [x] Add Hamburg and Nantes model adapters and rewire shared imports/tests to
  use them
- [x] Add a waste-collection model adapter and rewire remaining shared imports
  and tests to it
- [x] Add serializer adapter modules and rewire shared imports to them
- [x] Add filter and renderer adapter modules where shared code still imports
  `case_studies.*` directly
- [x] Reduce remaining shared direct imports to a small, intentional set before
  starting `SeparateDatabaseAndState` model moves
- [x] Move the first domain URL/view/router ownership slice into `sources`
  while preserving legacy compatibility
- [x] Extend URL/view/router ownership into the Nantes greenhouse domain while
  preserving legacy compatibility
- [x] Extend URL/view/router ownership into the waste-collection domain while
  preserving legacy compatibility
- [x] Add forms/task adapters where `sources`-owned views still imported
  directly from `case_studies.*`
- [x] Add viewset adapters where `sources`-owned routers still imported
  directly from `case_studies.*`

### Near-term next steps

1. Collapse the remaining intentional compatibility re-exports only after the
   migration-shim phase can be retired without breaking fresh database setup.
2. Move the last legacy-only greenhouse and waste-collection runtime seams
   (notably signal/admin/management-command ownership) fully into `sources` so
   the empty `case_studies` apps can be deleted rather than shimmed.
3. Convert the remaining legacy URL prefixes into pure redirects once the
   canonical entrypoints live only under `sources`.
4. Trim any remaining direct `case_studies.*` imports behind `sources`
   adapters and keep the full Docker `web` suite green as those seams are
   removed.
5. Update the remaining documentation/README surfaces and then remove the
   legacy shim apps/packages at the end of the migration-history transition.

### Phase A: Prepare the sources/ app structure

- [x] Convert `sources/models.py` to `sources/models/__init__.py` package
- [x] Convert `sources/views.py` to `sources/views/__init__.py` package
- [x] Create empty sub-module files (forms/, filters/, serializers/, etc.)
- [x] Verify tests still pass (no functional changes yet)

### Phase B: Move flexibi_hamburg (smallest, lowest risk)

- [x] Move models to `sources/models/roadside_trees.py` with `db_table` Meta
- [x] Move views, filters, serializers, viewsets, renderers, algorithms
- [x] Move templates from `flexibi_hamburg/` to `sources/roadside_trees/`
- [x] Move static files
- [x] Move tests
- [x] Create `SeparateDatabaseAndState` migrations in both apps
- [x] Update `brit/urls.py` — merge Hamburg URLs into `sources/urls.py`
- [ ] Update all external imports (maps/tasks.py, registry_init.py, etc.)
- [x] Add redirect patterns for old `/case_studies/hamburg/` URLs
- [ ] Update `INSTALLED_APPS`
- [ ] Run full test suite

### Phase C: Move flexibi_nantes (medium size)

- [x] Move models to `sources/models/greenhouses.py` with `db_table` Meta
- [x] Move views, forms, filters, serializers, viewsets, renderers, algorithms
- [x] Move templates and static files
- [ ] Move tests
- [x] Create `SeparateDatabaseAndState` migrations
- [ ] Update `brit/urls.py` — merge Nantes URLs into `sources/urls.py`
- [ ] Update all external imports
- [ ] Add redirect patterns for old `/case_studies/nantes/` URLs
- [x] Run full test suite

### Phase D: Move soilcom (largest, highest risk)

- [x] Move models to `sources/models/waste_collection.py` with `db_table` Meta
- [x] Move views, forms, filters, serializers, viewsets, renderers
- [ ] Move signals, tasks, utils
- [x] Move templates and static files
- [ ] Move tests (~8,300 lines)
- [x] Create `SeparateDatabaseAndState` migrations
- [ ] Update `brit/urls.py` — merge waste collection URLs into `sources/urls.py`
- [ ] Update all external imports (maps, utils, sources, layer_manager)
- [ ] Add redirect patterns for old `/waste_collection/` URLs
- [x] Run full test suite

Current incremental status for Phase D:

- [x] Move API `viewsets` into `sources.waste_collection`
- [x] Move export `renderers` into `sources.waste_collection`
- [x] Move waste-flyer Celery `tasks` into `sources.waste_collection`
- [x] Move `serializers` into `sources.waste_collection`
- [x] Move `filters` into `sources.waste_collection`
- [x] Move `forms` into `sources.waste_collection`

### Phase E: Clean up

- [ ] Remove empty `case_studies/flexibi_hamburg/` app after replacing the
  legacy migration-module shim with source-owned migration history
- [ ] Remove empty `case_studies/flexibi_nantes/` app after moving model
  ownership and any remaining admin/runtime registration out of the legacy app
- [ ] Remove empty `case_studies/soilcom/` app after moving model ownership,
  signal registration, and any remaining admin/runtime registration out of the
  legacy app
- [ ] Remove `case_studies/` package if no other apps remain (check closecycle)
- [ ] Update documentation, READMEs
- [ ] Verify all old URLs redirect correctly

## 8. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Broken migrations | Blocks deployment | Use `db_table` to avoid renaming tables. Test with `--run-syncdb`. |
| ContentType / Permission records reference old app_label | Auth breaks | Write data migration to update `django_content_type` rows. |
| Generic foreign keys reference old ContentType IDs | Data integrity | Include in the ContentType migration. |
| Admin registered under old app | Admin 404s | Move admin registrations to `sources/admin.py`. |
| Celery tasks reference old module paths | Tasks fail silently | Update task imports in `tasks.py` and any `CELERY_*` settings. |
| Template namespacing (`soilcom/...`) | Template 404s | Keep old template directory names OR update all `template_name` references. |
| Migration dependency ordering | `makemigrations` fails | Carefully set `dependencies` in `SeparateDatabaseAndState` migrations. |

## 9. ContentType and Permission Migration

When models move apps, `django_content_type` rows still reference the old
`app_label`. This affects:

- Object permissions (`auth_permission.content_type_id`)
- Generic foreign keys (`GeoDataset.data_content_type`)
- Admin log entries (`django_admin_log.content_type_id`)

A data migration must update these:

```python
def update_content_types(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    # Update soilcom → sources
    ContentType.objects.filter(app_label="soilcom").update(app_label="sources")
    # Update flexibi_nantes → sources
    ContentType.objects.filter(app_label="flexibi_nantes").update(app_label="sources")
    # Update flexibi_hamburg → sources
    ContentType.objects.filter(app_label="flexibi_hamburg").update(app_label="sources")
```

**Important:** This must run AFTER the `SeparateDatabaseAndState` migrations
and BEFORE any code that looks up permissions by the new app label.

## 10. Order of Operations (Per Phase)

For each app being moved:

1. Create target files in `sources/` (models, views, etc.)
2. Create `SeparateDatabaseAndState` migration in `sources/` (adds models to state)
3. Create `SeparateDatabaseAndState` migration in old app (removes models from state)
4. Create ContentType update migration in `sources/`
5. Update `INSTALLED_APPS` (add sources if not present, remove old app)
6. Update `brit/urls.py`
7. Update all external imports
8. Move templates and static files
9. Move tests
10. Run full test suite
11. Commit
