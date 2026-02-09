# Module UX Harmonization Guideline

**Date:** 2026-02-09  
**Status:** Proposal  
**Scope:** All user-facing modules in BRIT

---

## 1. Executive Summary

BRIT has grown organically across multiple research projects (FLEXIBI, SOILCOM, CLOSECYCLE). Each module was built at different times, by different contributors, and to serve different domain needs. While a solid shared infrastructure exists (`utils/object_management`, base templates like `detail_with_options.html`, `filtered_list.html`, `simple_list_card.html`), the *user-facing guidance*—how a user discovers, navigates, and operates within a module—varies significantly. This document catalogs the inconsistencies and proposes a harmonized guideline.

### 1.1 Key Conceptual Distinction: Explorer vs. Dashboard

The current codebase uses "dashboard" to refer to pages that are really **model explorers** — catalog pages that list all entity types in a module with icons, descriptions, and counts. A true **dashboard** would show activity, metrics, or status information (e.g., "3 items pending review", "last updated 2 days ago"). This document distinguishes:

- **Explorer**: A model catalog that enumerates all entity types in a module. Useful for power users and developers. Currently implemented in Materials, Processes, and Waste Collection. *Not ideal as an entry point* because it exposes the full data model, which overwhelms users who just want to work with the module's core functionality.
- **Dashboard**: A user-centric landing page showing relevant activity and status. Does not yet exist in the codebase.
- **Primary model list**: The list view of the module's central model — the one entity that everything else revolves around. *This is the natural entry point* for most users.

### 1.2 Primary Models per Module

Every module has one (sometimes two) **primary models** that represent the core user-facing entity. Supporting models (categories, properties, lookup tables) exist to describe or classify the primary model but are not what users come to the module for.

| Module | Primary model(s) | Supporting models |
|---|---|---|
| **Materials** | Sample, SampleSeries | Material, MaterialCategory, Component, ComponentGroup, AnalyticalMethod, MaterialProperty, Composition |
| **Maps** | GeoDataSet, Catchment | Attribute, AttributeValue, Region, Location, NutsRegion |
| **Waste Collection** | Collection | Collector, CollectionSystem, WasteCategory, WasteComponent, FeeSystem, Frequency, WasteFlyer, CollectionCatchment |
| **Bibliography** | Source | Author, Licence |
| **Processes** | ProcessType | ProcessGroup, MechanismCategory |
| **Inventories** | Scenario | InventoryAlgorithm |
| **CLOSECYCLE** | Showcase | — |
| **Nantes** | Greenhouse, Culture | GrowthCycle |
| **Hamburg** | *(map views only)* | — |

---

## 2. Current Module Inventory & Entry-Point Analysis

### 2.1 How Users Reach Each Module

| Module | Sidebar link target | Home card target | Entry experience |
|---|---|---|---|
| **Maps** | `maps_list` (geodataset filter list) | `maps_list` | Lands directly on a filtered data list |
| **Materials** | `sample-list-featured` (featured samples) | `sample-list-featured` | Lands on a curated "featured" view — a special list |
| **Sources** | `sources-list` (static template page) | `sources-list` | Lands on a hand-crafted overview page with cards |
| **Processes** | `processes-dashboard` (explorer dashboard) | `processes-dashboard` | Lands on a structured explorer dashboard |
| **Inventories** | `scenario-list` (scenario filter list) | `scenario-list` | Lands directly on a filtered data list |
| **Bibliography** | `source-list` (source filter list) | `source-list` | Lands directly on a filtered data list |
| **Waste Collection** | *(not in sidebar)* | *(not on home)* | Reachable from Sources page or direct URL |
| **CLOSECYCLE** | *(not in sidebar)* | *(not on home)* | Reachable from home News card or direct URL |
| **Hamburg** | *(not in sidebar)* | *(not on home)* | Only via Maps sub-routes or direct URL |
| **Nantes** | *(not in sidebar)* | *(not on home)* | Only via Maps sub-routes or direct URL |

### 2.2 Explorer / Overview Page Availability

| Module | Has explorer? | Style | Sidebar entry point |
|---|---|---|---|
| Materials | ✅ `materials-dashboard` | **Modern**: icon cards with counts, grouped sections, hover effects | `sample-list-featured` (primary model list) |
| Processes | ✅ `processes-dashboard` | **Modern**: same card style as Materials | `processes-dashboard` (explorer!) |
| Waste Collection | ✅ `wastecollection-dashboard` | **Modern**: same card style as Materials | *(not in sidebar)* |
| Bibliography | ✅ `bibliography-dashboard` | **Legacy**: plain cards with text, `card-footer` buttons | `source-list` (primary model list) |
| Maps | ✅ `maps-dashboard` | **Legacy**: plain cards with text, `card-footer` buttons, only 2 of ~6 entities | `maps_list` (primary model list) |
| Inventories | ❌ | — | `scenario-list` (primary model list) |
| Sources | ❌ (static page serves as overview) | Hand-coded overview | `sources-list` (static page) |

**Key findings:**
1. Three modules use the modern explorer card pattern, two use a legacy card pattern, and three have no explorer at all.
2. The term "dashboard" is used in the codebase but these pages are really **model explorers** (entity catalogs), not dashboards in the activity/metrics sense.
3. Most sidebar links already point to the **primary model list** — Materials (→ Samples), Maps (→ GeoDataSets), Inventories (→ Scenarios), Bibliography (→ Sources). The exception is Processes, which enters on the explorer. This inconsistency is notable: *Materials already does it right by linking to Samples, not to the explorer.*

---

## 3. Identified Inconsistencies

### 3.1 Navigation Architecture

| Issue | Details |
|---|---|
| **Inconsistent entry points** | Some modules enter on a dashboard (Processes), some on a featured list (Materials), some on a raw filter list (Maps, Inventories, Bibliography), and one on a static page (Sources). A user switching between modules has no predictable mental model of "what happens when I click a module." |
| **Missing sidebar entries** | Waste Collection (one of the largest modules) is not in the sidebar. Case studies (CLOSECYCLE, Hamburg, Nantes) are not in the sidebar. Users must know specific URLs or find them through Sources/Maps. |
| **Dual URL mounting** | Case studies are mounted twice: under `maps/` *and* under `case_studies/` (Hamburg, Nantes). This creates duplicate routes to the same content. |

### 3.2 Explorer Design

| Issue | Details |
|---|---|
| **Conceptual mislabeling** | All explorer pages are called "dashboards" in URL names and templates (`materials-dashboard`, `processes-dashboard`, `wastecollection-dashboard`). They are model catalogs, not dashboards. This creates a misleading mental model — users might expect activity or status information. |
| **Two explorer generations** | Materials, Processes, and Waste Collection use the modern explorer card style with inline CSS for `.explorer-card`, `.explorer-icon`, `.explorer-section-heading`. Bibliography and Maps use a legacy card style with `card-footer` buttons. |
| **Duplicated CSS** | The modern explorer card styles are copy-pasted identically in `materials_dashboard.html`, `processes_dashboard.html`, and `wastecollection_dashboard.html` rather than extracted into a shared stylesheet or partial. |
| **Incomplete Maps explorer** | The Maps explorer only shows 2 entity types (Datasets, Catchments) but the module manages 6+ entity types (GeoDataSets, Attributes, Regions, Catchments, Locations, NutsRegions). |
| **Explorer as entry point is overwhelming** | Processes enters on the explorer, showing all entity types. A new user doesn't know which one to click. The Materials module handles this better — the sidebar links directly to the primary model (Samples), and the explorer is reachable as a secondary navigation option. |

### 3.3 URL Naming Conventions

| Pattern | Example modules | Notes |
|---|---|---|
| `<entity>/` (list) | Most modules | ✅ Consistent |
| `<entity>/user/` (private list) | Most modules | ✅ Consistent |
| `<entity>/create/` | Most modules | ✅ Consistent |
| `<entity>/<pk>/` (detail) | Most modules | ✅ Consistent |
| `<entity>/<pk>/update/` | Most modules | ✅ Consistent |
| `<entity>/<pk>/delete/modal/` | Most modules | ⚠️ Some use `delete/` without `modal/` (compositions, locations, geodatasets, scenarios) |
| `<entity>/<pk>/modal/` (modal detail) | Most modules | ⚠️ Missing trailing slash in some URLs (`components/create/modal`, `sample_series/create/modal`, `attributes/<pk>/delete/modal`) |
| URL name pattern | `<entity>-<action>` | ⚠️ Some names use underscores: `seasonal_distribution_create`, `add_scenario_configuration`, `scenario_update_config`, `remove_algorithm_from_scenario` |
| Map view names | `NutsRegion`, `HamburgRoadsideTrees`, `WasteCollection`, `Showcase` | ⚠️ PascalCase names mixed with kebab-case for all other URL names (see §3.3.1) |

#### 3.3.1 Why Map URL Names Are CamelCase (Historical Reason)

The CamelCase URL names for map views (`NutsRegion`, `HamburgRoadsideTrees`, `NantesGreenhouses`, `WasteCollection`, `Showcase`) exist because the `GeoDataset` model uses a `model_name` field to create a **shared identifier** that ties together several systems:

1. **`GIS_SOURCE_MODELS`** (`maps/models.py`) — a hardcoded choices tuple of CamelCase names
2. **`GeoDataset.model_name`** — a CharField storing the identifier, constrained to `GIS_SOURCE_MODELS` choices
3. **`GeoDataset.get_absolute_url()`** — does `reverse(f"{self.model_name}")`, so the **URL name must exactly match the stored `model_name` value**
4. **`FilteredMapMixin.get_dataset()`** — looks up a `GeoDataset` row by `model_name`
5. **`MapMixin.get_map_configuration()`** — uses `model.__name__` (naturally CamelCase) to look up `ModelMapConfiguration`
6. **API basename auto-discovery** — constructs `api-{model_name.lower()}` for DRF router lookups

The chain is: Python class name → stored in DB → used as URL name via `reverse()`. The URL names were made CamelCase because `get_absolute_url()` reuses the DB-stored `model_name` directly as the URL name argument to `reverse()`.

**Is this still necessary?** No. The coupling is accidental, and the `model_name` field already has a `# TODO remove when switch to generic view is done` comment. Moreover, `"WasteCollection"` is not even a real model class name (the model is `Collection`) — it's really a **dataset identifier** that happens to look like a class name. The decoupling path:

- **Option A**: Add a `map_url_name` field (or property) to `GeoDataset` that stores the kebab-case URL name, and update `get_absolute_url()` to use it instead of `model_name`.
- **Option B**: Add a mapping dict/method that translates `model_name` → kebab-case URL name, keeping the DB field as-is but decoupling the URL layer.
- Either option allows renaming URL names to kebab-case (`nuts-region-map`, `hamburg-roadside-trees-map`, etc.) without changing the DB schema or breaking `ModelMapConfiguration` lookups.

### 3.4 List View Patterns

| Issue | Details |
|---|---|
| **Two base list templates** | `filtered_list.html` (with django-filter sidebar) vs `simple_list_card.html` (basic table). Some entities use FilterView, others use ListView. The choice appears to depend on the entity's complexity, but the criteria are undocumented. |
| **Scope toggle** | Both templates include Published/Mine/Review toggles — this is well-harmonized. ✅ |
| **Dashboard back-link** | `simple_list_card.html` supports a `dashboard_url` context variable for an "Explorer" button. `filtered_list.html` does not — users who enter via a dashboard have no way back except the browser Back button or re-clicking the sidebar. |
| **List-Map toggle** | Both templates support it — well-harmonized. ✅ |

### 3.5 Detail View Pattern

The `detail_with_options.html` template provides a strong, consistent detail view with:
- ✅ Standardized card layout (8/4 grid with Options + Learning sidebar)
- ✅ Review status badges and workflow actions
- ✅ Policy-driven Edit/Delete/Submit buttons
- ✅ Extensible via template blocks

**This is the best-harmonized part of the UX.** Most modules properly extend this template.

### 3.6 Sidebar Navigation

| Issue | Details |
|---|---|
| **Active state detection** | Uses path-contains matching (`{% if '/maps/' in request.path %}`). This works but is fragile — a URL like `/materials/maps-something/` would incorrectly highlight Maps. |
| **No sub-navigation** | The sidebar is flat. Modules with many entity types (Materials has 8, Waste Collection has 9) give no indication of sub-structure. Users must know to go to the dashboard first. |
| **Missing modules** | Waste Collection, case studies, and Interfaces are absent from the sidebar. |

---

## 4. Proposed Harmonization Guideline

### 4.1 Standard Module Structure — Primary Model as Entry Point

Every user-facing module MUST follow this navigation pattern:

```
Sidebar Link
  → Primary Model List (the main entity users work with)
    → Entity Detail (with options sidebar)
      → Create / Update forms

  Explorer (reachable from list views, for power users)
    → Shows all entity types in the module
    → Links to each entity's list view
```

The key insight: **the entry point is the primary model, not the explorer.** Users come to a module to work with its main entity (Samples, Collections, Scenarios, Sources). The explorer is a secondary navigation tool for users who need to manage supporting models.

**Rules:**

1. **Every module in the sidebar MUST link to its primary model's list view.** This is what Materials already does (→ Samples) and what most other modules do naturally.
2. **Every module SHOULD have an explorer page** that catalogs all entity types. This is reachable from list views via an "Explorer" button, but is NOT the primary entry point.
3. **Every entity list page MUST include an "Explorer" back-link** (the pattern from `simple_list_card.html`) so users can discover supporting models when needed.
4. **Every entity detail page** continues to use `detail_with_options.html`.
5. **Rename "dashboard" to "explorer"** in URL names and templates to avoid confusion with actual dashboards (which would show activity/metrics).

### 4.2 Explorer Template (Model Catalog)

Extract the explorer card pattern into a **reusable partial template** and shared CSS to eliminate copy-pasting:

**Proposed files:**
- `brit/static/css/explorer-cards.css` — shared styles for `.explorer-card`, `.explorer-icon`, `.explorer-section-heading`
- `brit/templates/partials/_explorer_card.html` — reusable card partial accepting: `url`, `icon`, `icon_color`, `title`, `description`, `count`
- `brit/templates/partials/_explorer_section.html` — section heading partial accepting: `icon`, `title`

**All explorers** should then use:
```django
{% include "partials/_explorer_section.html" with icon="fas fa-layer-group" title="Materials & Classification" %}
<div class="row g-3 mb-4">
  {% include "partials/_explorer_card.html" with url=material_list_url icon="fas fa-cubes" ... %}
  {% include "partials/_explorer_card.html" with url=category_list_url icon="fas fa-tags" ... %}
</div>
```

The explorer is valuable for orientation and discoverability, but it should be **one click away** from the primary list, not the landing page itself.

### 4.3 Standard URL Conventions

All modules MUST follow these URL patterns:

| Purpose | URL pattern | Name pattern |
|---|---|---|
| Explorer | `explorer/` | `<module>-explorer` |
| Published list | `<entities>/` | `<entity>-list` |
| Private list | `<entities>/user/` | `<entity>-list-owned` |
| Review list | `<entities>/review/` | `<entity>-list-review` |
| Create | `<entities>/create/` | `<entity>-create` |
| Modal create | `<entities>/create/modal/` | `<entity>-create-modal` |
| Detail | `<entities>/<int:pk>/` | `<entity>-detail` |
| Modal detail | `<entities>/<int:pk>/modal/` | `<entity>-detail-modal` |
| Update | `<entities>/<int:pk>/update/` | `<entity>-update` |
| Modal update | `<entities>/<int:pk>/update/modal/` | `<entity>-update-modal` |
| Delete (modal) | `<entities>/<int:pk>/delete/modal/` | `<entity>-delete-modal` |
| Autocomplete | `<entities>/autocomplete/` | `<entity>-autocomplete` |
| Map view | `<entities>/map/` | `<entity>-map` |
| API | `api/` | *(DRF router)* |

**Naming rules:**
- URL names use **kebab-case** only: `scenario-create`, never `scenario_create`
- All URL paths MUST end with a **trailing slash**
- Map view URL names must be kebab-case (`waste-collection-map`), not PascalCase (`WasteCollection`)

### 4.4 Sidebar Navigation Updates

1. **Add missing modules** to the sidebar:
   - Waste Collection (under a "Case Studies" section heading)
   - CLOSECYCLE Showcases (under "Case Studies")
2. **All sidebar links should target the primary model list:**
   - Maps → `geodataset-list` (currently → `maps_list` — already correct, just rename)
   - Materials → `sample-list-featured` (currently → `sample-list-featured` — ✅ already correct)
   - Processes → primary model list (currently → `processes-dashboard` — change to `processtype-list`)
   - Inventories → `scenario-list` (currently → `scenario-list` — ✅ already correct)
   - Bibliography → `source-list` (currently → `source-list` — ✅ already correct)
   - Waste Collection → `collection-list`
3. **Improve active state detection** by using URL namespace prefixes or a context variable instead of string-contains matching.

### 4.5 List View Standardization

| Criterion | Use `filtered_list.html` | Use `simple_list_card.html` |
|---|---|---|
| Entity has filterable fields (ForeignKey, date, choices) | ✅ | |
| Entity is "lookup table" type (few fields, mainly name) | | ✅ |
| Entity benefits from sidebar filter panel | ✅ | |

**Rules:**
1. Both templates MUST provide an `explorer_url` back-link to the module explorer.
2. Both templates MUST show a result count.
3. Both templates MUST show a meaningful empty state message.
4. The choice between filtered and simple must be documented per entity in the module's README.

### 4.6 Home Page Card Standardization

The home page (`home.html`) shows module cards that link to different entry points. Under the new guideline:

- **Every module card links to the primary model list** (same target as sidebar)
- Remove the "Sources" card linking to a static page, or replace it with a link to a primary model list once the Sources module matures
- Add a "Case Studies" section or card that links to CLOSECYCLE/Waste Collection

### 4.7 Case Study Integration

Case studies are currently mounted in confusing ways:
- `case_studies/hamburg/` AND `maps/hamburg/` → same app
- `case_studies/nantes/` AND `maps/nantes/` → same app
- `waste_collection/` → `case_studies.soilcom`
- `closecycle/` → `case_studies.closecycle`

**Proposed consolidation:**
1. Pick ONE canonical URL prefix per case study and redirect the other
2. Recommendation: mount under `case_studies/` and remove from `maps/`
3. Or: give each case study its own top-level prefix but remove the duplicate mounting

---

## 5. Module-Specific Action Items

### 5.1 Maps
- [ ] Upgrade explorer to modern explorer card style
- [ ] Add cards for all entity types: GeoDataSets, Attributes, Attribute Values, Regions, Catchments, Locations
- [ ] Rename `maps-dashboard` → `maps-explorer`
- [ ] Sidebar already links to primary model list (GeoDataSets) — ✅
- [ ] Add `explorer_url` to all list views
- [ ] Remove duplicate case study URL mounting

### 5.2 Materials
- [ ] Sidebar and home already link to primary model (Samples) — ✅ best practice reference
- [ ] Rename `materials-dashboard` → `materials-explorer`
- [ ] Extract explorer card CSS to shared file
- [ ] Add `explorer_url` to all list views

### 5.3 Bibliography
- [ ] Upgrade explorer to modern explorer card style with counts
- [ ] Rename `bibliography-dashboard` → `bibliography-explorer`
- [ ] Sidebar already links to primary model list (Sources) — ✅
- [ ] Close `</div>` tag missing in `bibliography_dashboard.html` (row not closed)
- [ ] Add `explorer_url` to all list views

### 5.4 Inventories
- [ ] Create a new `inventories-explorer` page
- [ ] Add cards for: Scenarios, Inventory Algorithms
- [ ] Sidebar already links to primary model list (Scenarios) — ✅
- [ ] Add `explorer_url` to scenario list view

### 5.5 Sources
- [ ] Evaluate whether static page should become a proper explorer with data-driven cards and counts
- [ ] Or: merge Sources into the home page as a concept rather than a module

### 5.6 Processes
- [ ] Change sidebar link from `processes-dashboard` → primary model list (`processtype-list`)
- [ ] Rename `processes-dashboard` → `processes-explorer`
- [ ] Extract explorer card CSS to shared file
- [ ] Add `explorer_url` to all list views

### 5.7 Waste Collection (SOILCOM)
- [ ] Add to sidebar navigation, linking to primary model list (Collections)
- [ ] Rename `wastecollection-dashboard` → `wastecollection-explorer`
- [ ] Extract explorer card CSS to shared file
- [ ] Add `explorer_url` to all list views

### 5.8 CLOSECYCLE
- [ ] Add to sidebar navigation, linking to Showcase list
- [ ] Consider creating a small explorer if more entity types are added

### 5.9 URL Cleanup
- [ ] Rename `*-dashboard` URL names to `*-explorer`
- [ ] Rename underscore-based URL names to kebab-case
- [ ] Add missing trailing slashes to modal URLs
- [ ] Rename PascalCase map URL names to kebab-case
- [ ] Remove or redirect duplicate case study URL mounts

---

## 6. Implementation Priority

| Priority | Item | Effort |
|---|---|---|
| **P1** | Extract shared explorer card CSS + partial templates | Small |
| **P1** | Rename `*-dashboard` → `*-explorer` in URLs and templates | Small |
| **P1** | Change Processes sidebar link from explorer → primary model list | Small |
| **P2** | Upgrade Maps and Bibliography explorers to modern style | Medium |
| **P2** | Create Inventories explorer | Medium |
| **P2** | Add `explorer_url` back-links to all list views | Small |
| **P3** | URL naming cleanup (kebab-case, trailing slashes) | Medium (many files, needs redirect mapping) |
| **P3** | Consolidate case study URL mounting | Medium |
| **P3** | Add missing modules to sidebar | Small |
| **P4** | Improve sidebar active-state detection | Small |
| **P4** | Redesign Sources module entry point | Medium |

---

## 7. Summary of the Harmonized User Journey

```
User arrives at Home
  → Sees module cards (Maps, Materials, Sources, Inventories, Bibliography, Processes, ...)
  → Clicks a module card
    → Lands on Primary Model List (the main entity of the module)
      → Clicks an item → Entity Detail (with Options/Learning sidebar)
        → Can Edit, Delete, Submit for Review, Export, etc.
      → Clicks "Create" → adds a new item
      → Clicks "Explorer" → Module Explorer (model catalog)
        → Sees all entity types with icons, descriptions, counts
        → Clicks a supporting entity card → Supporting Entity List
```

The key principle: **users land where they can immediately be productive** (the primary model list), and the explorer is available one click away for when they need to manage supporting data. This mirrors the Materials module's current approach, which already does it right — the sidebar links to Samples, not to the explorer.

This flow is **predictable**, **consistent**, and **task-oriented**. A user who has learned one module's navigation can immediately orient themselves in any other module.
