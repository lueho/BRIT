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

---

## 8. Primary List View: Description & Learning Content

### 8.1 Problem Statement

When a user first arrives at a module via the sidebar, they land on the primary model list. In some modules this list includes contextual information (a brief description of the module and links to learning materials); in others it is a bare data table. The modules that do provide context use two incompatible patterns, leading to an inconsistent first impression.

### 8.2 Existing Patterns (Status Quo)

Three patterns currently coexist in the codebase:

#### Pattern A: Standalone Landing Page

**Used by:** Materials (`featured_sample_list.html`, `featured_materials_list.html`), Sources (`sources_list.html`)

The sidebar links to a **separate** page that extends `base.html` directly. This page shows:
- A description card (left column) explaining the module
- A learning material card (right column) linking to external lectures
- Below: a grid of featured/curated items (not the full filterable list)

The actual filterable list (`sample_filter.html`, `sampleseries_filter.html`) is reached via a secondary "see as list" link in the card footer.

**Problems:**
1. Adds an **extra click** between sidebar and the real, filterable data
2. Description and learning content are **not available** when the user navigates directly to the filtered list (e.g. via a bookmark or back-link)
3. Featured items are displayed as a **card grid** without filters, pagination, or scope toggles — a different interaction model than every other list in the application
4. Learning content is **duplicated** (identical HOOU links appear in both `featured_sample_list.html` and `sources_list.html`)

#### Pattern B: Learning Sidebar Tab in Filtered List

**Used by:** Waste Collection (`collection_filter.html`), Greenhouses (`greenhouse_filter.html`)

The primary list view extends `filtered_list.html` and overrides `{% block learning_pane_body %}` to populate the Learning tab in the sidebar. The `filtered_list.html` base template auto-hides the Learning tab via JavaScript when no content is provided.

**Advantages:**
1. **No extra click** — contextual content is alongside the data
2. Uses existing `filtered_list.html` sidebar tab infrastructure
3. Learning tab **auto-hides** via JS when empty (graceful degradation)
4. Content is available regardless of how the user reached the list

**Limitations:**
1. No module **description** visible on first load — only learning resources in a sidebar tab
2. Learning resources in a tab that is not active by default — easy to miss

#### Pattern C: Plain Filtered List (No Context)

**Used by:** Processes (`processtype_filter.html`), Inventories (`scenario_filter.html`), Bibliography (`source_filter.html`), CLOSECYCLE (`showcase_filter.html`), Maps

The primary list view extends `filtered_list.html` but explicitly empties the Learning tab:
```django
{% block learning_tab_button %}{% endblock learning_tab_button %}
{% block learning_tab_pane %}{% endblock learning_tab_pane %}
```

No description, no learning resources. The user sees only a data table with filters.

### 8.3 Current State Per Module

| Module | Sidebar target | Pattern | Description? | Learning? |
|---|---|---|---|---|
| **Materials** | `sample-list-featured` | A (standalone) | ✅ in landing page | ✅ in landing page |
| **Sources** | `sources-list` | A (standalone) | ✅ in landing page | ✅ in landing page |
| **Waste Collection** | `collection-list` | B (sidebar tab) | ❌ | ✅ in sidebar tab |
| **Greenhouses** (Nantes) | `greenhouse-list` | B (sidebar tab) | ❌ | ✅ in sidebar tab |
| **Processes** | `processtype-list` | C (bare) | ❌ | ❌ |
| **Inventories** | `scenario-list` | C (bare) | ❌ | ❌ |
| **Bibliography** | `source-list` | C (bare) | ❌ | ❌ |
| **CLOSECYCLE** | `showcase-list` | C (bare) | ❌ | ❌ |
| **Maps** | `maps_list` | C (bare) | ❌ | ❌ |

### 8.4 Optimized Design Pattern

Combine the best aspects of all three patterns into a single, consistent approach that works within the existing `filtered_list.html` infrastructure.

#### 8.4.1 Concept: Intro Banner + Learning Sidebar Tab

```
filtered_list.html
├── {% block list_intro %}              ← NEW optional block
│   ├── Module description (1–2 sentences)
│   └── Quick-access links (Explorer, Map view, etc.)
├── List card (existing)
│   ├── Header with scope/view/explorer toggles
│   ├── Filterable data table
│   └── Pagination
└── Sidebar (existing)
    ├── Filters tab (active by default)
    ├── Options tab (Create, Explorer, Export)
    └── Learning tab (auto-hidden when empty)
        └── External resources, lectures, courses
```

#### 8.4.2 The `list_intro` Block

Add a new `{% block list_intro %}{% endblock list_intro %}` to `filtered_list.html`, placed **above** the list card (before the `<div class="row">`). When overridden, it renders a compact, dismissible intro banner:

```html
{% block list_intro %}
<div class="alert alert-light border shadow-sm mb-3 d-flex align-items-start" role="region" aria-label="Module introduction">
  <div class="flex-grow-1">
    <strong><i class="fas fa-leaf me-1"></i> Materials</strong>
    <p class="mb-0 small text-muted">
      Define and analyze heterogeneous materials from biogeneous residues.
      Explore compositions with respect to different separation methods.
    </p>
  </div>
  <button type="button" class="btn-close ms-3" data-bs-dismiss="alert" aria-label="Dismiss"></button>
</div>
{% endblock list_intro %}
```

**Design decisions:**
- **Compact**: 2–3 lines max, does not push the data table off-screen
- **Dismissible**: uses Bootstrap alert dismiss so returning users can hide it
- **Non-intrusive**: uses `alert-light` styling, blending with the page rather than demanding attention
- **Optional**: the base block is empty, so modules without a description are unaffected

#### 8.4.3 The Learning Sidebar Tab

The `filtered_list.html` Learning tab infrastructure already exists and auto-hides when empty. Each module's primary list template should override `{% block learning_pane_body %}` with:

1. A **featured resource** card (the most relevant external learning material)
2. A **resource list** with links to additional lectures/courses

Use the component pattern already established in `soilcom/includes/learning_materials.html`:

```html
{% block learning_pane_body %}
  {% include "<module>/includes/learning_materials.html" %}
{% endblock learning_pane_body %}
```

Each module that has learning resources creates a `<module>/includes/learning_materials.html` partial. This keeps the content reusable across list views, detail views, and map views within the same module.

#### 8.4.4 Deprecation of Standalone Landing Pages (Pattern A)

Once the intro banner and learning tab are in place for Materials and Sources:

1. Move the description text from `featured_sample_list.html` into `sample_filter.html`'s `{% block list_intro %}`
2. Move the learning links from `featured_sample_list.html` into `sample_filter.html`'s `{% block learning_pane_body %}`
3. Redirect `sample-list-featured` → `sample-list` (or keep as alias for backwards compatibility)
4. Same for `sampleseries-list-featured` and `sources-list`

The Sources module (`sources_list.html`) is a special case — it functions as a hub page linking to sub-modules (Waste Collection, Greenhouses) rather than a data list. This page may remain as a static overview or evolve into a proper explorer page. Evaluate separately.

### 8.5 Improvement Plan

#### Phase 1: Infrastructure (filtered_list.html changes)

| Step | Description | Effort |
|---|---|---|
| 1.1 | Add `{% block list_intro %}{% endblock %}` to `filtered_list.html` above the list card | Tiny |
| 1.2 | Verify the Learning tab auto-hide JS works correctly for all modules | Tiny |

#### Phase 2: Populate Learning Content

For each module's primary list template, override `{% block learning_pane_body %}` and remove the explicit learning tab emptying (`{% block learning_tab_button %}{% endblock %}`).

| Step | Module | Primary list template | Learning content source | Effort |
|---|---|---|---|---|
| 2.1 | Waste Collection | `collection_filter.html` | Already done ✅ | — |
| 2.2 | Greenhouses | `greenhouse_filter.html` | Already done ✅ | — |
| 2.3 | Materials (Samples) | `sample_filter.html` | Move from `featured_sample_list.html` | Small |
| 2.4 | Processes | `processtype_filter.html` | Write new content (link to HOOU bioresource lectures) | Small |
| 2.5 | Bibliography | `source_filter.html` | Write new content (citation guidelines, data licensing) | Small |
| 2.6 | Inventories | `scenario_filter.html` | Write new content (inventory methodology, scenario workflow) | Small |
| 2.7 | CLOSECYCLE | `showcase_filter.html` | Write new content (CLOSECYCLE project overview) | Small |
| 2.8 | Maps | `maps/geodataset_filter.html` or equivalent | Write new content (GIS data sources, NUTS regions) | Small |

#### Phase 3: Add Intro Banners

For each module's primary list template, override `{% block list_intro %}` with a concise module description.

| Step | Module | Template | Description text source | Effort |
|---|---|---|---|---|
| 3.1 | Materials (Samples) | `sample_filter.html` | Adapt from `featured_sample_list.html` | Tiny |
| 3.2 | Processes | `processtype_filter.html` | Write new (1–2 sentences about process types) | Tiny |
| 3.3 | Bibliography | `source_filter.html` | Write new (1–2 sentences about sources/citations) | Tiny |
| 3.4 | Inventories | `scenario_filter.html` | Write new (1–2 sentences about scenarios) | Tiny |
| 3.5 | Waste Collection | `collection_filter.html` | Write new (1–2 sentences about biowaste collection data) | Tiny |
| 3.6 | CLOSECYCLE | `showcase_filter.html` | Write new (1–2 sentences about circular economy showcases) | Tiny |
| 3.7 | Maps | primary list template | Write new (1–2 sentences about geodatasets) | Tiny |

#### Phase 4: Deprecate Standalone Landing Pages

| Step | Description | Effort |
|---|---|---|
| 4.1 | Update Materials sidebar link from `sample-list-featured` → `sample-list` | Tiny |
| 4.2 | Keep `sample-list-featured` URL as redirect to `sample-list` for backwards compatibility | Tiny |
| 4.3 | Keep `sampleseries-list-featured` URL as redirect to `sampleseries-list` | Tiny |
| 4.4 | Evaluate Sources module: convert `sources_list.html` to a proper explorer, or merge hub links into Home | Medium |

### 8.6 Summary

The optimized pattern is: **every primary list view provides its own context**. A brief intro banner above the table orients first-time visitors, the Learning sidebar tab offers deeper educational resources, and the Options tab provides the Explorer back-link. No intermediate landing pages, no duplicated content, no inconsistent interaction models. A user arriving at any module via the sidebar sees the same layout: intro → data → sidebar with filters, options, and learning.

---

## 9. Hub Pages: Concept and Recommendations

### 9.1 Problem Statement

Some pages in the application act as **hubs** — they don't show data themselves but instead group and link to related sub-modules. The Sources page (`sources_list.html`) is the primary example. With the completion of Phases 1–4 (intro banners, learning tabs, sidebar entries for all modules), the role of hub pages needs to be re-evaluated: do they still serve a purpose, and if so, what should the standardized pattern be?

### 9.2 Inventory of Page Types

The application currently has five distinct page types:

| Type | Purpose | Template pattern | Examples |
|---|---|---|---|
| **Home page** | Global hub: links to all top-level modules with cover images and descriptions | `home.html` extends `base.html` | Home |
| **Explorer** | Module-internal catalog: enumerates entity types within a single Django app with counts and browse links | `*_dashboard.html` extends `base.html` | Materials Explorer, Processes Explorer, Waste Collection Explorer, Bibliography Explorer, Inventories Explorer, Maps Explorer |
| **Hub page** | Cross-module aggregator: groups related modules/apps under a conceptual theme with descriptions and cover images | `sources_list.html` extends `base.html` | Sources |
| **Primary list view** | Filterable data table with intro banner, learning sidebar, and scope toggles | `*_filter.html` extends `filtered_list.html` | Sample list, Process type list, Collection list, etc. |
| **Learning page** | Centralized learning resource catalog: HOOU courses and lectures with cover images | `learning.html` extends `base.html` | Learning |

### 9.3 Analysis of the Sources Hub Page

The Sources page currently serves three functions:

1. **Domain description** — Explains the concept of bioresource sources (two paragraphs)
2. **Learning resources** — Links to HOOU lectures (identical to those now in learning sidebar tabs)
3. **Sub-module navigation** — Cards with cover images linking to Waste Collection and Greenhouses

**Redundancies after Phase 1–4:**
- Function 1 is now handled by **intro banners** on each sub-module's primary list view
- Function 2 is now handled by **learning sidebar tabs** on each sub-module's primary list view
- Function 3 is partially redundant because:
  - Waste Collection has its own **sidebar entry** under Case Studies
  - CLOSECYCLE has its own **sidebar entry** under Case Studies
  - Greenhouses is accessible from the Waste Collection explorer or sidebar
  - The **Home page** already links to Sources (and could link to sub-modules directly)

**What Sources still provides:**
- A conceptual grouping: "these are all models describing how bioresources are generated"
- An intermediate navigation layer between Home and the sub-module lists

**What Sources doesn't provide:**
- Any data — it's a pure `TemplateView` with no model, no queryset, no filters
- Entity enumeration — unlike explorers, it doesn't list entity types within a single app

### 9.4 Hub Page Design Concept

#### 9.4.1 Decision: Hub Pages Are Not a Necessary Navigation Layer

With the harmonized list views (intro banner + learning tab + sidebar entries), the intermediate hub layer adds friction without adding value. The user can reach every sub-module directly from:
- The **sidebar** (one click from anywhere)
- The **Home page** (cover image cards for all modules)
- The **explorer** of a parent module (if applicable)

Hub pages were necessary when sub-modules lacked their own contextual information. Now that every primary list view is self-describing, the hub is redundant for navigation.

#### 9.4.2 When Hub Pages Make Sense

Hub pages remain justified in **one specific scenario**: when a conceptual grouping has no corresponding Django app but needs a landing page for external linking or marketing purposes. For example:
- A "Sources" landing page linked from a research paper or project website
- A "Case Studies" overview linked from a partner institution

In this case, the hub page serves as an **external entry point**, not an internal navigation layer.

#### 9.4.3 Recommended Pattern for Hub Pages (When Needed)

If a hub page is retained or created, it should follow a standardized template:

```
hub_page.html (extends base.html)
├── Title + brief description (1–2 paragraphs)
├── Sub-module cards (cover image + title + description + link)
│   └── Consistent card style with Home page cards
└── No learning material section (handled by sub-module list views)
```

**Design rules:**
- **No duplicated content**: description and learning material belong in the sub-module's list view, not in the hub
- **Card style matches Home page**: same `card shadow h-100` pattern with `card-img-top` and `card-body`
- **No sidebar entry**: hub pages are reached from the Home page or via direct URL, not from the sidebar
- **URL pattern**: `/<concept>/` (e.g., `/sources/list/`)

### 9.5 Recommendations for Sources

#### Option A: Remove from sidebar, keep as external landing page (Recommended)

1. Remove the "Sources" entry from the sidebar (`_sidebar.html`)
2. Keep the `sources-list` URL and view for backwards compatibility and external links
3. Update the Home page Sources card to link directly to one of:
   - The Waste Collection list (`collection-list`) — if Waste Collection is the primary sub-module
   - Keep linking to `sources-list` — if the conceptual grouping page is valuable for external audiences
4. Add Greenhouses to the sidebar under Case Studies (if it should be a top-level entry point) or leave it accessible via the Waste Collection explorer

**Rationale:** The sidebar should only contain items that lead to data or tools. Sources contains neither — it's a routing page. Users reaching Sources from an external link still get a useful overview; internal users navigate directly via the sidebar.

#### Option B: Convert Sources to an Explorer

If the "sources" concept evolves into a proper Django app with its own entity types (e.g., SourceModel, SourceCategory), then Sources should become an explorer like Materials Explorer — enumerating entity types with counts and browse links.

This is the right path **only if** the data model justifies it. Currently, Sources has no models of its own.

#### Option C: Eliminate Sources entirely

1. Remove from sidebar
2. Redirect `sources-list` → Home page
3. Remove `sources_list.html` template and `SourcesListView`

This is the simplest option but loses the external landing page.

### 9.6 Recommendations for the Learning Page

The Learning page (`learning.html`) is structurally similar to a hub page — it groups external resources with cover images and descriptions. However, it serves a different purpose:

- It's a **catalog** of all learning resources in one place
- Individual modules now have module-specific learning content in their sidebar tabs
- The Learning page provides the **complete collection** and additional context about the HOOU partnership

**Recommendation:** Keep the Learning page as-is. It serves as a centralized reference that complements the per-module learning tabs. The sidebar entry under "Sites" is appropriate — it's a site-wide resource, not a module.

### 9.7 Summary

| Page | Current state | Recommendation |
|---|---|---|
| **Sources** | Sidebar entry → hub page → sub-module lists | Remove from sidebar; keep URL as external landing page |
| **Learning** | Sidebar entry → centralized learning catalog | Keep as-is |
| **Home** | Global hub with module cards | Keep as-is; optionally add Greenhouses card |
| **Explorers** | Module-internal entity catalog | Keep as-is; no changes needed |

The guiding principle: **the sidebar links to places where users can work with data**. Hub pages that only route to other pages should not occupy sidebar real estate. They can exist as external entry points or be eliminated entirely if their content is fully covered by intro banners and learning tabs in the list views they point to.
