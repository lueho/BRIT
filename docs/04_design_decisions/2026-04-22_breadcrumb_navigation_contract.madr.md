# MADR: Shared Breadcrumb Navigation Contract (2026-04-22)

## Status
Accepted

## Context
BRIT historically rendered breadcrumbs with per-template strings and model-specific assumptions (for example `object.name`, `Explorer`, or route-name humanization). The resulting trails were inconsistent across modules, occasionally produced `BRIT | None` browser titles, and did not express the nested hierarchy of source-domain plugins (`waste_collection`, `greenhouses`, `roadside_trees`) which logically live under `Sources`.

A single, explicit breadcrumb contract was needed so that:

- list, detail, and CRUD form pages for the same entity share the same path
- source-domain plugins expose their `Sources > <Plugin>` parent without duplication
- page titles and breadcrumbs are derived from the same label metadata
- special pages (home, error pages) can deliberately suppress the shared rail
- future pages can adopt the contract without re-inventing template-local logic

## Decision

### 1. One contract, six named slots
Shared breadcrumb context is produced by `utils.views.build_breadcrumb_context` and exposed to templates through `utils.views.BreadcrumbContextMixin`. The contract is:

| Slot | Purpose |
|---|---|
| `breadcrumb_parent_module_label` / `breadcrumb_parent_module_url` | Optional parent module crumb (e.g. `Sources` for nested plugins). |
| `breadcrumb_module_label` / `breadcrumb_module_url` | Top-level module (e.g. `Materials`, `Sources > Waste Collection`). |
| `breadcrumb_section_label` / `breadcrumb_section_url` | Entity-plural within the module (e.g. `Samples`). |
| `breadcrumb_object_label` / `breadcrumb_object_url` | Current object label (defaults to `object.get_breadcrumb_object_label()` → `str(self)`). |
| `breadcrumb_action_label` | Trailing action crumb on form pages (e.g. `Create`, `Update`). |
| `breadcrumb_page_title` | Browser-title contribution; defaults to the deepest populated breadcrumb label. |

The rendering path is always:

```
BRIT > <parent module> > <module> > <section> > <object> > <action>
```

Missing slots collapse. The deepest populated slot becomes the active crumb.

### 2. Defaults live in `DEFAULT_BREADCRUMB_MODULES`
`utils/object_management/views.py` defines `DEFAULT_BREADCRUMB_MODULES`, which maps each app label to its `label`, `url_name`, and optional `parent_label` / `parent_url_name`. Shared CRUD views consume this mapping to populate the contract automatically. Source-domain plugins (`waste_collection`, `greenhouses`, `roadside_trees`) are registered with `parent_label = "Sources"` so their pages render `BRIT > Sources > <Plugin> > …` without per-view configuration. Setting `url_name` to `None` renders the module crumb as plain text for plugins that do not expose a dashboard.

### 3. Shared CRUD templates delegate to the contract
`brit/templates/base.html`, `brit/templates/filtered_list.html`, and `brit/templates/detail_with_options.html` render crumbs exclusively from the contract slots via `{% firstof %}`. The legacy `object` / `header` / `title` / `breadcrumb_page_title` fallback chain in `base.html` is preserved as a safety net for pages that do not yet adopt the contract, but contract slots unconditionally win over it when populated.

### 4. Sticky offsets are driven by shared CSS custom properties
`brit/static/css/filtered-list.css` owns the canonical sticky offsets:

```css
:root {
  --brit-topnav-height: 56px;
  --brit-breadcrumb-rail-height: 3rem;
  --brit-sticky-offset: calc(var(--brit-topnav-height)
                          + var(--brit-breadcrumb-rail-height) + 1rem);
}
```

Any sticky sibling of the breadcrumb rail (filter sidebars, the `sdv2-rail`, the sample-detail related aside) derives its `top` from these variables rather than hardcoding `56px`, so rail-height changes propagate automatically.

### 5. Explicit suppression is a first-class pattern
Pages that deliberately omit the sticky rail (home page, 403/404/500 error pages) override `{% block page_chrome %}{% endblock page_chrome %}` as empty. Any page that suppresses the rail is expected to compensate in-content (e.g. an inline header or a "← Back to Home" link) so users are never stranded.

### 6. Custom detail experiences compose with the contract
Bespoke detail templates (for example `materials/templates/materials/sample_detail_v2.html`) render the shared rail and layer their own in-page toolbar below it. They do not replace or duplicate the breadcrumb trail.

## Consequences

- Shared list, detail, and form pages across all modules expose a consistent, module-first hierarchy.
- Source-domain plugins surface the `BRIT > Sources > <Plugin>` parent path without per-view code.
- Browser titles never render `None`; they are derived from the same label metadata as the breadcrumbs.
- Sticky layout is resilient to rail-height changes because offsets are CSS-variable-driven.
- Custom detail experiences can keep page-level toolbars without breaking navigation consistency.
- New pages adopt the contract by subclassing `BreadcrumbContextMixin` or the shared CRUD base classes; no template-local breadcrumb logic is needed.

## Alternatives Considered

- **Template-local breadcrumb strings** (status quo before the refactor) — rejected: duplicates knowledge, drifts between related pages, leaks `None` into titles.
- **Model `Meta.breadcrumb_*` attributes** — rejected: over-couples navigation presentation to model metadata and cannot express request-scoped parent information for plugin pages.
- **A single monolithic template tag** — rejected: hides the contract behind template-only logic and makes request-time defaults (e.g. per-user scope) awkward.

## References

- Shared contract implementation: `utils/views.py::build_breadcrumb_context`, `utils/views.py::BreadcrumbContextMixin`
- Default module/plugin mapping: `utils/object_management/views.py::DEFAULT_BREADCRUMB_MODULES`
- Shared rendering templates: `brit/templates/base.html`, `brit/templates/filtered_list.html`, `brit/templates/detail_with_options.html`
- Sticky CSS contract: `brit/static/css/filtered-list.css`
- Current-state reference (operational docs): `brit/README.md#breadcrumb-navigation`
- Regression test suite: `brit/tests/test_templates.py`

---

**This contract is canonical for all future pages. Do not reintroduce template-local breadcrumb strings or duplicate breadcrumb trails in custom detail experiences.**
