# MapMixin, FilteredMapMixin, and GeoDataset Workflow (Current and Proposed)

## 1. Current Workflow

### a. Dataset Identification
- Datasets are represented by the `GeoDataset` model.
- Each `GeoDataset` has a `model_name` field (CharField, with choices) used for identification.
- The `FilteredMapMixin` and related views (e.g., `GeoDataSetPublishedFilteredMapView`) use `model_name` to look up datasets:
  ```python
  GeoDataset.objects.get(model_name=self.model_name)
  ```
- This means dataset logic is tightly coupled to string names, which must be hardcoded in views, URLs, and templates.

### b. Admin Registration
- `GeoDataset` is registered in the Django admin using a standard `ModelAdmin`.
- Datasets must be created/managed via the admin or programmatically, and their `model_name` must match what is expected in the codebase.

### c. Map Configuration
- The `FilteredMapMixin.get_map_configuration()` method fetches the map configuration for a dataset:
  ```python
  dataset = self.get_dataset()
  if dataset.map_configuration:
      return dataset.map_configuration
  else:
      return MapConfiguration.objects.get(name='Default Map Configuration')
  ```
- This allows each dataset to have a specific map configuration, or fall back to a default.

### d. Limitations
- **Hardcoding**: Each new dataset requires code changes to reference its `model_name`.
- **Fragility**: Typos or renames in `model_name` can break lookups.
- **Scalability**: Not scalable for many datasets or dynamic registration.

---

## 2. Proposed Workflow: Use Primary Key (`pk`) for Dataset Identification

### a. Dataset Identification by PK
- Instead of `model_name`, use the primary key (`pk`) of each `GeoDataset` for identification.
- Update all lookups to use `GeoDataset.objects.get(pk=...)`.
- Example change in `FilteredMapMixin`:
  ```python
  def get_dataset(self):
      return GeoDataset.objects.get(pk=self.kwargs.get('pk'))
  ```
- This allows dataset URLs and views to be generic, e.g., `/maps/geodatasets/<pk>/map/`.

### b. Admin Registration
- Datasets are still registered and managed through the Django admin.
- No need to set or maintain a `model_name`.

### c. Map Configuration
- Unchanged: Each `GeoDataset` can still have a `map_configuration` ForeignKey.

### d. Benefits
- **No Hardcoding**: No need to change code for new datasets—just create them in the admin.
- **Robustness**: PKs are unique and stable, reducing the risk of lookup errors.
- **Scalability**: Supports any number of datasets without code changes.
- **Dynamic URLs**: Enables generic views and URLs for all datasets.

---

## 3. Required Changes for Migration

- Remove the `model_name` field from the `GeoDataset` model (after migration).
- Update all code that references `model_name` for dataset lookup to use `pk` instead.
- Update URL patterns to include `<int:pk>` for dataset-specific views.
- Update templates and frontend code to use dataset PKs in links and API calls.
- (Optional) Provide a data migration to convert existing `model_name` references to PK-based references.

---

## 3a. GeoDataset Metadata Fields (2025-04-26 Update)

As of 2025-04-26, the following metadata fields are now present on the `GeoDataset` model and required for all datasets:
- `table_name` (CharField): Name of the underlying spatial table.
- `geometry_field` (CharField): Name of the geometry column.
- `display_fields` (CharField): Comma-separated list of fields to display.
- `filter_fields` (CharField): Comma-separated list of fields available for filtering.

**These fields are validated by automated tests and must be set for each dataset.**

### Example registration (admin):
- Table name: `my_new_trees`
- Geometry field: `geom`
- Display fields: `name`
- Filter fields: `species,height`

All new datasets must have these fields populated. See `maps/tests/test_geodataset_metadata.py` for test coverage.

---

## 4. Example: Updated FilteredMapMixin

```python
class FilteredMapMixin(MapMixin):
    template_name = 'filtered_map.html'

    def get_dataset(self):
        return GeoDataset.objects.get(pk=self.kwargs.get('pk'))

    def get_region_feature_id(self):
        return self.get_dataset().region_id

    def get_map_configuration(self):
        dataset = self.get_dataset()
        if dataset.map_configuration:
            return dataset.map_configuration
        else:
            return MapConfiguration.objects.get(name='Default Map Configuration')
```

---

## 5. Summary Table

| Aspect                | Current (model_name)             | Proposed (pk)           |
|-----------------------|----------------------------------|-------------------------|
| Dataset Lookup        | By model_name (string)           | By pk (int)             |
| Admin Registration    | Must set model_name              | No extra step           |
| URL Structure         | Hardcoded per dataset            | Generic with <pk>       |
| Scalability           | Manual, not scalable             | Automatic, scalable     |
| Error Risk            | High (typos, renames)            | Low (unique pk)         |

---

## 6. Migration Checklist (updated)
- [x] Add `table_name`, `geometry_field`, `display_fields`, `filter_fields` to `GeoDataset` model.
- [x] Create and apply migration.
- [x] Update and pass all model/tests for new fields (see `test_geodataset_metadata.py`).
- [ ] Remove or migrate away from `model_name` field (future step).
- [ ] Refactor all code and templates to use PK-based lookups (future step).

---

## 7. Implications and Mitigation Strategies

### Implications

1. **URL/Route Changes**
   - All dataset-related URLs must change from hardcoded or name-based to generic PK-based routes.
   - Any external integrations, bookmarks, or API consumers using the old URLs will break.

2. **Codebase Refactoring**
   - All lookups, logic, and template references to `model_name` must be updated to use `pk`.
   - Any custom logic relying on `model_name` (e.g., permissions, filtering, analytics) will need review and refactoring.

3. **Model Changes**
   - Removing `model_name` is a breaking change.
   - Migrations must ensure no data loss and that all references are safely removed.

4. **Backward Compatibility**
   - Existing links using `model_name` will become invalid, resulting in 404 errors for users or scripts relying on them.
   - API endpoints or consumers using `model_name` will break unless a fallback or redirect is provided.

5. **Data Migration and Integrity**
   - Any business logic, reports, or exports using `model_name` must be updated.
   - A migration script may be needed to ensure all references are updated atomically.

6. **Admin and User Experience**
   - Admins no longer need to set `model_name`, reducing manual errors.
   - If `model_name` was used for display or filtering, alternatives (like verbose names or slugs) may be needed for usability.
   - URLs will be less descriptive (e.g., `/maps/geodatasets/5/` instead of `/maps/geodatasets/my-dataset/`), which may impact readability and SEO.

7. **Testing and Deployment Risks**
   - All CRUD, map, and filter views must be thoroughly tested for PK-based logic.
   - Automated and manual tests must cover both the migration and the new code paths.
   - A staged deployment with feature flags or a fallback mechanism is recommended.
   - Rollback plans should be in place in case of unforeseen issues.

### Mitigation Strategies

- **URL Redirects:** Implement HTTP 301/302 redirects from old `model_name`-based URLs to new PK-based URLs for a transition period.
- **Deprecation Warnings:** Warn users and API consumers about the change in advance.
- **Migration Scripts:** Write and test migration scripts to update all references safely.
- **Alternative Identifiers:** If human-readable URLs are important, consider adding a `slug` field for optional use in URLs.
- **Comprehensive Testing:** Increase test coverage for all affected views, templates, and APIs.
- **Documentation:** Update all internal and external documentation to reflect the new workflow.
- **Rollback Plan:** Prepare a rollback plan in case the migration causes critical issues.

---

## 10. Dynamic `filterset_class` Strategy (2025-04-26 Deep Dive)

### 10.1 Objectives
*   Each **map view must filter on the underlying data table**, *not* on the `GeoDataset` meta-table.
*   Avoid hard-coding: the same view must work for every dataset registered in `GeoDataset`.
*   Security: only the columns explicitly listed in `GeoDataset.filter_fields` are exposed for filtering.

### 10.2 Architecture Overview
1. **Dynamic Model Accessor** (Package 3)
   *  `get_dynamic_model(geodataset)` returns (and caches) a Django model wrapper for the dataset’s `table_name`.
   *  Uses Django’s [`connection.introspection.get_table_description()`] to introspect columns and types.
   *  Result is cached with `lru_cache(maxsize=256)` keyed by `(schema, table_name)`.

2. **FilterSet Factory** (NEW) – `get_dynamic_filterset(geodataset)`
   *  Splits `geodataset.filter_fields` into a list \["species", "height", ...].
   *  Dynamically builds a `django_filters.FilterSet` subclass:
      ```python
      def get_dynamic_filterset(dataset):
          model = get_dynamic_model(dataset)
          allowed_fields = [f.strip() for f in dataset.filter_fields.split(',') if f.strip()]
          class Meta:
              model = model
              fields = allowed_fields
          attrs = { 'Meta': Meta }
          return type(f'DynamicFilterSet{dataset.pk}', (django_filters.FilterSet,), attrs)
      ```
   *  Cached with `lru_cache(maxsize=256)` keyed by `dataset.pk`.

3. **View Integration**
   *  In `FilteredMapMixin` override `get_filterset_class`:
     ```python
     def get_filterset_class(self):
         dataset = self.get_dataset()
         return get_dynamic_filterset(dataset)
     ```

4. **Serializer Integration** (Package 4)
   *  Dynamic DRF serializer created similarly using `display_fields`.

5. **Template & JS Impact**
   *  No changes; the generic view emits the correct filtered GeoJSON.

### 10.3 Second- & Third-Order Effects
| Area | Effect | Mitigation |
|------|--------|-----------|
| **DB Performance** | Filtering on arbitrary columns needs indexes | Add admin validation: warn if chosen `filter_fields` are **not indexed**. |
| **Security** | Dynamic model exposes raw table; risk of over-exposure | Whitelist only `filter_fields`, enforce `__all__ = ()` for serializer except permitted display fields. |
| **Migrations** | Existing datasets may have empty `filter_fields` → no filter | Provide default (`id`) or prompt admin to set fields before enabling generic path. |
| **Permissions** | Current per-model permissions must apply to dynamic model | Use `GenericDatasetPermissionMixin` that resolves underlying model and re-maps perms. |
| **Caching** | Per-dataset filtersets cached; memory footprint | 256-entry LRU is <1 MiB; monitor. |
| **Testing** | Need matrix tests across all datasets | Implement `DatasetMatrixTestCase` that asserts list/map endpoints work with filters. |
| **API Versioning** | Field names in query params vary by dataset | Document per-dataset filter params in `/api/datasets/<pk>/schema/`. |

### 10.4 Pass-2 Critical Review Changes
* Added **admin validation** for index presence.
* Ensured **filter_fields** empty-string fallback does not expose all columns.
* Clarified permission remapping.

### 10.5 Pass-3 Final Audit
* Re-checked backward compatibility under `ENABLE_GENERIC_DATASET=False` – legacy code path unchanged.
* Verified that **no migrations** modify existing tables; only Django model wrappers.
* Confirmed that serializer + filterset factories are side-effect-free and safe to import at runtime.

> **Outcome:** The architecture now meets the requirement to filter on the underlying data table via dynamic `filterset_class`, while controlling exposure, performance, and compatibility.

---

## 11. Implementation Progress Log (2025-04-26)

### Step 1: Dynamic Model Accessor
- Implemented `get_dynamic_model(dataset)` in `maps/dynamic_model.py`.
- Utility generates a Django model for any table referenced by a `GeoDataset`, exposing only the fields listed in its metadata.
- **Tested** with a dedicated test case: confirmed it can query, introspect, and retrieve data from a registered table.

### Step 2: Dynamic FilterSet Factory
- Implemented `get_dynamic_filterset(dataset)` in `maps/dynamic_model.py`.
- Utility generates a `django_filters.FilterSet` for the dynamic model, exposing only the fields listed in `GeoDataset.filter_fields`.
- Defensive fallback: if `filter_fields` is empty, only exposes `id`.
- **Tested**: Confirmed that only the allowed fields are exposed and that filtering works as expected on the dynamic model.

### Next Step
- Integrate these utilities into the map view logic (FilteredMapMixin) so each dataset map view uses the correct filterset and model.
- Add/expand tests to ensure the map view only exposes allowed filter fields for any dataset.

---

## Refactoring Plan: Generic, Code-Free Dataset Registration for Map Exploration

### Objective
Enable new spatial datasets to be added and explored on the map by simply creating a new database table and registering it in `GeoDataset`, **without writing any new source code**.

### Architectural Shift: From Per-Model to Generic Handling

#### Current Limitation
- Each new dataset requires a Django model, serializers, views, filtersets, and explicit code registration.

#### Desired Outcome
- Any new spatial table (with required fields) can be registered in `GeoDataset`.
- The system auto-discovers and exposes the dataset on the map with generic filtering, serialization, and viewing.

---

### Implementation Steps

#### 1. Refactor `GeoDataset` Model
- Add fields to store:
  - **Table name** (and optionally schema)
  - **Geometry field name**
  - **Display field(s)**
  - **Filterable fields** (optional)
- Provide admin UI for registering and editing these fields.

#### 2. Dynamic Table Introspection Utility
- Use Django's introspection (`connection.introspection.table_names()`, `apps.get_model`, or a dynamic model factory) to access arbitrary tables.
- Write a generic model accessor that wraps any table with the required geometry and display fields.

#### 3. Generic Serializers, Views, and FilterSets
- Implement generic serializers and views that:
  - Accept a table name and field names from `GeoDataset`.
  - Query, serialize, and filter any registered table dynamically.
  - Use reflection/introspection to generate filtersets on the fly for registered fields.

#### 4. Refactor Map Views
- Update map views to use the generic serializer/view, driven by metadata from `GeoDataset`.
- Remove per-model hardcoding for new datasets.

#### 5. Map UI and API
- Ensure the map UI and API can list all registered datasets from `GeoDataset` and interact with them using the generic backend.

#### 6. Documentation and Table Requirements
- Document the required schema for new tables (e.g., must have a geometry column, optional display/filter fields).
- Provide a checklist for dataset registration:
  1. Add the table to the database.
  2. Register it in `GeoDataset` with the appropriate metadata.
  3. Dataset is immediately available for map exploration.

#### 7. (Optional) Backward Compatibility
- Legacy per-model code can remain for specialized cases.
- Gradually migrate existing datasets to the generic system as needed.

---

### Example Workflow

1. **Add Table:** Create a new PostGIS table (e.g., `my_new_trees`) with required columns.
2. **Register:** In Django admin, create a `GeoDataset` entry:
    - Table name: `my_new_trees`
    - Geometry field: `geom`
    - Display name: "My New Trees"
    - Filter fields: `species`, `height`, etc.
3. **Explore:** The map UI/API automatically includes "My New Trees" for exploration, with generic filtering and display.

---

### Benefits
- **Zero-code onboarding** of new spatial datasets.
- **Consistent** filtering, serialization, and viewing for all datasets.
- **Scalable** architecture for future growth and dataset diversity.

---

## Step-by-Step Refactoring Plan: Towards Generic Dataset Registration

To enable a smooth, incremental migration to a generic, code-free dataset registration system, the following plan breaks the work into small, independent packages. Each package can be completed and tested individually, ensuring the system remains functional at every step.

### **Package 1: Metadata Expansion in GeoDataset**
- **Goal:** Prepare `GeoDataset` to store all metadata needed for dynamic dataset access.
- **Tasks:**
  - Add fields: table name, geometry field, display fields, filter fields.
  - Update admin interface for easy metadata entry.
- **Result:** Existing code continues to work; new metadata fields are available for future use.

### **Package 2: Dynamic Table Introspection Utility**
- **Goal:** Provide a utility to introspect available tables and their columns.
- **Tasks:**
  - Implement a management command or utility function to list spatial tables and their geometry fields.
  - Optionally, expose this utility in the admin for dataset registration assistance.
- **Result:** Developers/admins can discover and register new tables more easily.

### **Package 3: Generic Model Accessor**
- **Goal:** Enable dynamic access to arbitrary tables as Django models.
- **Tasks:**
  - Write a model factory or use Django's `apps.get_model`/contenttypes to wrap arbitrary tables.
  - Ensure read-only access works for spatial queries.
- **Result:** Can query any registered table via Python code, without a dedicated model class.

### **Package 4: Generic Serializer and FilterSet**
- **Goal:** Serialize and filter arbitrary tables generically.
- **Tasks:**
  - Implement a serializer that uses table/field metadata from `GeoDataset`.
  - Implement a filterset that is generated dynamically from the registered filter fields.
- **Result:** Any registered table can be serialized and filtered with minimal code.

### **Package 5: Generic Map View**
- **Goal:** Provide a map view that uses the generic serializer/view, driven by metadata from `GeoDataset`.
- **Tasks:**
  - Implement a view that takes a `GeoDataset` pk or slug and uses the generic components.
  - Ensure it falls back to legacy views for datasets not yet migrated.
- **Result:** New datasets can be added without code; legacy datasets continue to work.

### **Package 6: UI/UX Enhancements for Admins**
- **Goal:** Make it easy for admins to register and configure new datasets.
- **Tasks:**
  - Improve the Django admin for `GeoDataset` with helpful widgets, validation, and table/field pickers.
  - Add documentation and tooltips for required fields.
- **Result:** Non-developers can register datasets reliably.

### **Package 7: Migration and Cleanup**
- **Goal:** Gradually migrate legacy datasets to the new system and remove obsolete code.
- **Tasks:**
  - For each legacy dataset, update its `GeoDataset` entry and switch to the generic path.
  - Remove dedicated model/view/serializer code once migration is complete.
- **Result:** Codebase is cleaner, with all datasets using the generic registration path.

---

**At every stage, the system remains functional. New features are additive until the final migration and cleanup. This approach minimizes risk and allows for parallel work where possible.**

---

## Package 4 Status (2025-04-26)
- All required metadata fields are present and tested.
- Migration applied and tests pass.
- Plan remains valid: can proceed to PK-based lookups and further refactoring.

---

## Comprehensive Impact Assessment & Risk Mitigation

> *"Measure twice, cut once."*  – Every change must be vetted against the entire codebase to avoid regressions. The following subsections highlight critical areas that **must** be audited or refactored as part of (or in parallel with) the packages above.

### 1. `model_name` Hot-Spots Outside Map Views
A search for `model_name` reveals >500 usages. Not all relate to `GeoDataset`, but any **hard dependency on the `GeoDataset.model_name` lookup** must be updated.

| Area / File Glob | Purpose | Action |
|------------------|---------|--------|
| `maps/views.py` (`FilteredMapMixin.get_dataset`, `MapMixin` logic) | Uses `GeoDataset.objects.get(model_name=...)` | Replace with pk/slug lookup once generic path is ready (Package 5). |
| `case_studies/**/views.py` | Per-dataset map views | Migrate to generic view or keep as legacy until Package 7. |
| `utils/viewsets.py`, `utils/permissions.py`, `utils/models.py` | Permission codenames derived from `obj._meta.model_name` | **Unaffected**, but watch for code that *assumes* a GeoDataset exists with that model_name. |
| Tests under `maps/tests` and `utils/tests` | Fixtures use `model_name` strings | Update fixtures/mocks once GeoDataset migration is applied. |
| Old data migrations (`*/migrations/*.py`) | Hard-coded `model_name=` for `AlterModelOptions` etc. | Leave historic migrations untouched; but add a forward data-migration to populate new metadata fields. |

Add a **code-audit checklist** to Package 1 so every new PR includes a search for `model_name` to confirm no hidden dependency remains.

### 2. Database Migration Strategy
- **Forward migration**: Add new columns to `GeoDataset` (Package 1) with `null=True` initially. Provide a data-migration to back-fill metadata for existing datasets.
- **Backward compatibility**: Keep `model_name` column until all datasets have migrated (Package 7). Mark as `deprecated` in code comments.

### 3. Permissions & AuthN/AuthZ
Generic views must enforce the **same permission rules** currently applied per-model. Add a mixin (`GenericDatasetPermissionMixin`) that:
1. Resolves the dynamic model (Package 3).
2. Calls existing permission helpers with that model.

Include targeted tests in Package 4.

### 4. API Versioning
Switching to a generic endpoint may break client code. Plan:
1. **v1** (legacy) endpoints remain unchanged during migration.
2. Introduce **v2** generic endpoint (`/api/datasets/<pk>/features/`).
3. Deprecate v1 after all stakeholders migrate.

Document this in Package 5 deliverables.

### 5. Performance Considerations
- Dynamic introspection can be costly; cache table metadata (Package 2).
- Ensure spatial indexes exist on geometry fields—add validation step in admin.
- Use `select_related` / `prefetch_related` equivalents cautiously since dynamic models cannot declare FK relations at compile-time.

### 6. CI / Regression Tests
Create a new **DatasetMatrixTestCase** that automatically iterates over all `GeoDataset` records and hits list/detail/map endpoints, asserting 200 responses and valid GeoJSON. Add to Package 4.

### 7. Rollback & Fallback Plan
Every package delivers in a **feature flag** branch:
- Use Django settings `ENABLE_GENERIC_DATASET` (default False).
- Toggle per-environment; rollback means disabling the flag.

### 8. Documentation & Developer Education
Update internal docs, onboarding guides, and code comments with:
- How to register a dataset in admin.
- Field requirements & caveats.
- Migration checklist.

### 9. Timeline & Ownership
Add a Gantt/roadmap section in the project tracker. Each package should have an owner and definition of done.

---

> **Key Take-Away:** Before merging each package, run the *model_name audit*, ensure migrations are reversible, and pass the DatasetMatrix tests. This guarantees that no silent dependency is left behind and the team can proceed confidently.

---

## 12. View-Layer Decision & Recommendation (2025-04-26)

After analysing three options (A: patch `FilteredMapMixin`, B: new `GenericDatasetMapView`, C: hybrid) we have chosen **Approach B – add `GenericDatasetMapView` and gate it behind the `ENABLE_GENERIC_DATASET` flag**.

Key points recorded for posterity:

| Approach | Pros | Cons |
|----------|------|------|
| A – Patch existing mixin | Minimal diff; no URL change | Sudden global switch; downstream code may expect concrete models; harder rollback |
| B – New view + flag | Safe incremental rollout; clear diff; can A/B test; easy rollback | Slight URL dispatcher logic; one extra class to maintain (legacy will be removed later) |
| C – Hybrid branch in mixin | Per-dataset rollout | Added branching complexity; harder to reason about tests |

Cross-cutting impacts (permissions, serializers, templates, testing, monitoring) are captured in the previous note.

**Action items** for this commit series:
1. Implement `GenericDatasetMapView` (inherits `FilteredMapMixin`, `FilterView`).
2. Provide `get_queryset` and `get_filterset_class` using `get_dynamic_model` / `get_dynamic_filterset`.
3. Update `maps/urls.py` to switch the `/geodatasets/<pk>/map/` route to the new view when `settings.ENABLE_GENERIC_DATASET` is `True`.
4. Expand tests to cover both flag states.

---
