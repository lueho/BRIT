# Breadcrumb Navigation Target-State Plan
 
 - **Status**: Active roadmap; Phases 1, 2, and 4 landed on `feat/sticky-breadcrumbs`; Phase 3 nested-domain and custom-page work is the next slice
 - **Date**: 2026-04-21
 - **Last updated**: 2026-04-21
 - **Scope**: shared breadcrumb/page-chrome behavior across `base.html`, shared CRUD templates, explorer/dashboard pages, nested source-domain pages, static/error pages, and supporting view/model metadata needed to make breadcrumbs logical and stable throughout BRIT
 
 ## Documentation Boundary
 
 - **This document is the single authoritative roadmap for breadcrumb navigation in BRIT**
  It owns the target information architecture for breadcrumbs, the rollout order, progress tracking, and the definition of done for making breadcrumb navigation consistent across the application.
 
 - **Current-state breadcrumb behavior is documented in `brit/README.md`**
  The `brit` core-module README is the authoritative as-is reference for the shared breadcrumb rail, current template behavior, and known current limitations.
 
 - **Related records remain supporting architecture records, not parallel roadmap documents**
  Use the shared module UX guidance and existing module-specific target-state plans as supporting constraints. This roadmap specifically owns breadcrumb hierarchy, label changes, fallback-behavior changes, and rollout sequencing.
 
 ## 1. Context
 
 BRIT has grown over time from a mix of module-specific CRUD pages, explorer dashboards, plugin-mounted source domains, and a few custom detail experiences. As a result, breadcrumb navigation is currently inconsistent in both structure and quality.

Examples of the current mismatch include:

- some list pages render `BRIT > Explorer > <Entity>` while corresponding detail pages render only `BRIT > <Entity> > <Object>`
- some nested source-domain pages expose only the local entity type, while others expose a parent explorer level
- some pages rely on raw model metadata or fallback route names for breadcrumb labels, producing awkward labels such as `Privacypolicy`, `Redirect`, or grammatically incorrect plurals
- some detail pages assume every object exposes a `name` field, which breaks for models that use a different human display field
- some pages use user-facing labels such as `Inventories`, while the breadcrumb exposes an internal entity label such as `Scenarios`
- the browser title and breadcrumb fallback logic are currently coupled loosely enough that some pages can show `BRIT | None`

 The recently introduced sticky breadcrumb rail in `base.html` makes breadcrumb navigation visible across a much larger part of the application. That increases the importance of getting both the hierarchy and the labels right.
 
 This roadmap turns breadcrumb navigation from a template convenience into an explicit BRIT-wide information-architecture concern.
 
 This document translates that direction into a repo-specific target-state and rollout plan.
 
 ## 2. Target State to Reach
 
 The desired end state is not merely that every page has some breadcrumb. The target state is that breadcrumbs consistently communicate where the user is in BRIT's information architecture and give helpful return paths.

### 2.1 One shared hierarchy model

Breadcrumbs should follow one consistent model:

- `BRIT`
- module or area
- optional subsection or entity group
- optional entity list
- current object or action

Target outcome:

- explorer pages show the module, not a generic placeholder
- entity lists show the module plus the user-facing entity label
- detail pages show the same path as the list page, plus the current object
- create/edit pages show the same structural path, plus the action label

### 2.2 Module-first navigation

Breadcrumbs should prefer stable module labels over transient UI labels such as `Explorer` or `Dashboard`.

Target outcome:

- `BRIT > Materials`
- `BRIT > Maps`
- `BRIT > Sources`
- `BRIT > Bibliography`
- `BRIT > Inventories`
- `BRIT > Processes`
- `BRIT > Review`

rather than:

- `BRIT > Explorer`
- `BRIT > Processes Dashboard`
- `BRIT > Maps Explorer`

Explorer or dashboard wording may remain in page titles, but breadcrumbs should stay structural and concise.

### 2.2.1 Model-owned singular and plural labels

For model-backed CRUD pages, human-facing singular and plural labels should be owned by the models themselves.

Target outcome:

- shared views can safely read canonical singular and plural labels from model metadata
- irregular plurals such as `categories`, `properties`, `policies`, `statuses`, and invariant forms such as `series` are defined explicitly in model `Meta`
- breadcrumb fixes do not require page-specific pluralization patches when a model label changes later

### 2.3 Human-owned labels, not naive fallbacks

Breadcrumb labels should come from explicit human-facing metadata rather than from route names, naive pluralization, or assumptions that every model exposes `name`.

Target outcome:

- model-backed pages use a canonical display label and list label
- irregular plurals and compound nouns are handled explicitly
- static pages and error pages provide user-facing labels
- fallback route-name humanization becomes a last-resort safety net, not a normal UX path

### 2.4 Support for nested domains

Some areas of BRIT require more than one level below the module.

Examples:

- `BRIT > Sources > Waste Collection > Collections > <Collection>`
- `BRIT > Maps > Geo datasets > <Dataset>`
- `BRIT > Bibliography > Reference sources > <Source>`

Target outcome:

- nested source-domain modules no longer flatten into generic `Collections` or local plugin labels only
- plugin-mounted domains can participate in the same breadcrumb contract as core apps

### 2.5 Stable object display labels

Detail breadcrumbs must not assume `object.name` is always the correct display field.

Target outcome:

- every detail page can render a non-empty current-item breadcrumb label
- models such as `Author`, `Source`, and other non-`name` objects expose a clear breadcrumb display value
- shared detail templates use a general display-label contract instead of one hardcoded attribute

### 2.6 Shared page-chrome consistency

Browser titles, visible page titles, and breadcrumbs should be aligned without being identical.

Target outcome:

- titles never render `None`
- breadcrumb labels are short and structural
- page titles can remain more descriptive without forcing the breadcrumb to match word-for-word

## 3. Principles and Constraints

### 3.1 Breadcrumbs should express information architecture, not implementation detail

Do not expose:

- route names
- redirect view names
- technical model naming
- internal URL aliases such as `dashboard`, `explorer`, `list-owned`, or `review`

unless these are translated into deliberate user-facing labels.

### 3.2 Prefer explicit module and section labels over inference

Inference is acceptable only as a compatibility or safety fallback. The long-term direction should be explicit human-facing labels.

### 3.3 Keep the structure stable across list, detail, and form pages

A user should not mentally lose a level when moving from list to detail.

The correct fix is not to add generic `Explorer` everywhere. The correct fix is to use the same module and section structure on both sides.

### 3.4 One primary hierarchy per page

Breadcrumbs should represent one navigational path, not a mixed blend of:

- module hierarchy
- CRUD state
- arbitrary related-object chains

Custom rich breadcrumbs are acceptable only when they clearly follow a canonical hierarchy.

### 3.5 Special pages need explicit handling

Static pages, error pages, review dashboards, and plugin-mounted pages should not rely on raw template fallbacks.

### 3.6 Roll out additively before deleting compatibility logic

The safest sequence is:

- define the new breadcrumb contract
- add explicit metadata and shared helpers
- migrate high-traffic/shared pages first
- only then retire brittle fallback behavior where safe

## 4. Progress Snapshot

### 4.1 Documentation boundary status

- **Current state now has one home**
  - `brit/README.md` is the authoritative as-is reference for breadcrumb behavior.

- **Planning and progress now have one home**
  - this roadmap is the authoritative target-state and rollout document.

- **Supporting UX records remain secondary**
  - broader navigation and module-entry guidance may still live in supporting UX documents, but breadcrumb-specific rollout decisions should be recorded here.

### 4.2 Already-landed implementation precursors

- **Shared sticky breadcrumb rail exists**
  - `brit/templates/base.html` now provides one shared sticky breadcrumb rail through `page_chrome` and `breadcrumbs` blocks.

- **Shared list and detail templates already participate**
  - `brit/templates/filtered_list.html` and `brit/templates/detail_with_options.html` already render breadcrumbs through shared template logic.

- **Selected pages already provide explicit breadcrumbs**
  - major explorer/dashboard pages and selected form pages already override `breadcrumbs` explicitly instead of relying only on the base fallback.

- **Custom sample detail still uses its own rail intentionally**
  - `materials/templates/materials/sample_detail_v2.html` keeps a custom sticky sample-detail rail and suppresses the shared base rail for that page.

### 4.3 Remaining blockers before the target state

- shared list pages still expose the generic `Explorer` crumb
- shared detail pages still assume `object.name`
- some pages still fall through to weak title or route-name labels
- nested source-domain paths are still inconsistent
- page-title behavior is still weak enough to produce `BRIT | None` on some pages
- sticky sidebars (`.filter-sticky` on `filtered_list.html`, `detail_with_options.html`, and `simple_list_card.html`) still only offset for the 56px topbar and slide underneath the sticky breadcrumb rail when scrolling

### 4.4 Known layout regressions introduced by the sticky rail

- **Sticky sidebars slide under the breadcrumb rail**
  - `.filter-sticky` uses `top: calc(56px + 1rem)` and does not account for the `.page-breadcrumb-rail` height (`min-height: 3rem`, sticky at `top: 56px`, `z-index: 1030`).
  - When users scroll, the filter/options sidebar partially disappears under the breadcrumb rail.
  - Fix direction: introduce shared CSS custom properties (`--brit-topnav-height`, `--brit-breadcrumb-rail-height`) and have every sticky sibling of the rail compute its offset from those variables. This keeps the rail height authoritative in one place and allows future sticky siblings to participate without re-deriving the offset.
  - Scope: `brit/static/css/filtered-list.css` and its minified output. Custom detail pages that suppress the shared rail (for example `materials/sample_detail_v2.html`) intentionally remain out of scope.

### 4.5 Phase status

| Phase | Status | Notes |
|---|---|---|
| Phase 0 - information architecture and audit baseline | Complete | The target hierarchy has been documented and the as-is reference has been separated into `brit/README.md`. |
| Phase 1 - shared breadcrumb data contract | Complete | `utils.views.build_breadcrumb_context` and `BreadcrumbContextMixin` provide the shared module/section/object/action contract; shared list/detail/form templates delegate to the base contract via `{% firstof %}`. |
| Phase 2 - major module normalization | Complete | Bibliography, Inventories, Maps, Materials, Processes, Sources, Utilities, and Sources > Waste Collection landing views all render module-first breadcrumbs through the shared contract. |
| Phase 3 - nested domains and custom detail experiences | Not started | No canonical nested-domain breadcrumb contract beyond `Sources > Waste Collection` is implemented yet. |
| Phase 4 - static/review/error cleanup | Complete | Static pages (home, about, learning, privacy policy) and the content review dashboard render deliberate breadcrumbs. Home page and error pages (403/404/500) deliberately suppress the shared rail; home page displays "Bioresource Information Tool" as the card header to compensate for the missing rail context. |
| Phase 5 - regression hardening and cleanup | Partial | Focused breadcrumb tests cover shared list/detail/form, module landing pages, the nested Sources > Waste Collection contract, the review dashboard, static pages, error pages, and the sticky-offset CSS contract; broader coverage remains to be added. |

## 5. Gap Summary

The gap summary below is derived from the current-state implementation documented in `brit/README.md` together with the roadmap baseline and observed breadcrumb defects.

| Goal | Current state | Gap to close |
|---|---|---|
| Stable module-first breadcrumb hierarchy | Many lists use a generic `Explorer` crumb | Add explicit module labels and use them in shared list/detail/form breadcrumbs |
| Human-facing labels throughout | Some pages rely on model metadata or route fallback | Introduce explicit breadcrumb label contracts for modules, sections, and objects |
| Consistent list/detail depth | Lists and details often expose different parent levels | Share the same module and section path between list, detail, and action pages |
| Robust detail-item labels | Shared detail breadcrumb assumes `object.name` | Add a general object display-label strategy for shared detail templates |
| Nested-domain support | Source-domain/plugin pages expose inconsistent depth | Add explicit subsection support for nested domains such as `Sources > Waste Collection` |
| Static/error page quality | Some pages show fallback labels like `Privacypolicy` or `Redirect` | Add explicit breadcrumb handling for static, review, and error pages |
| Page-title consistency | Some pages can render `BRIT | None` | Harden shared page-title and breadcrumb context rules |

## 6. Recommended BRIT Implementation Strategy

### 6.1 Define an explicit breadcrumb contract

BRIT should standardize a small shared breadcrumb contract rather than relying on whichever context variables happen to exist.

Recommended concepts:

- `breadcrumb_module_label`
- `breadcrumb_module_url`
- `breadcrumb_section_label`
- `breadcrumb_section_url`
- `breadcrumb_object_label`
- `breadcrumb_action_label`
- optional explicit `breadcrumb_items` for pages that need full manual control

The exact variable names may change, but the shared contract should separate:

- module identity
- subsection/entity identity
- current object/action identity

### 6.2 Add explicit model-facing label helpers

Shared CRUD pages need one authoritative place to get human-facing labels.

Recommended direction:

- give shared list/detail views a canonical way to expose user-facing singular/plural breadcrumb labels
- stop depending on implicit pluralization or raw `_meta` defaults where they are not good enough
- treat explicit model `verbose_name` and `verbose_name_plural` metadata as the default source of truth for model-backed list labels, especially for irregular plurals
- provide a separate display-label helper for models whose detail label is not `name`

### 6.3 Keep `dashboard_url` as a link source, not as the label source

The current `dashboard_url` pattern is useful for navigation, but it should not force the breadcrumb label to be `Explorer`.

Recommended direction:

- keep URL linkage from the view layer
- add an explicit module label alongside it
- let shared templates render `BRIT > <Module> > <Entity>`

### 6.4 Support explicit overrides for nested domains

Some pages should provide more structure than generic CRUD templates can infer.

This especially applies to:

- `sources` domain pages and plugins
- review/moderation pages
- custom detail experiences such as `sample_detail_v2`
- static pages and error templates

### 6.5 Decouple breadcrumb display labels from browser-title strings

A browser title can remain more descriptive, for example `BRIT | Materials Explorer`, while the breadcrumb should stay shorter, for example `BRIT > Materials`.

### 6.6 Add regression tests and click-through verification

Breadcrumb work is deceptively easy to break because it spans many templates and context patterns.

Recommended validation layers:

- targeted template/view tests for shared list/detail rendering
- assertions for representative module pages
- assertions for detail pages whose display field is not `name`
- browser-level click-through verification of the major navigable paths

## 7. Phased Delivery Plan

## Phase 0 - Freeze the breadcrumb information architecture and audit the current surfaces

Goal: stop treating breadcrumbs as incidental template text and make the future structure explicit.

Deliverables:

- define the canonical breadcrumb hierarchy for BRIT
- inventory current breadcrumb entry points and fallback behavior
- inventory representative broken labels and broken page-title cases
- classify pages into:
  - shared CRUD pages
  - explorer/dashboard pages
  - nested source-domain pages
  - review/admin pages
  - static/error pages
  - custom rich-detail pages

Success criteria:

- one written target hierarchy exists
- the main defect classes are enumerated
- module-by-module ownership of remaining work is visible

## Phase 1 - Introduce the shared breadcrumb data contract

Goal: make the shared templates capable of rendering correct breadcrumbs without per-page hacks.

Deliverables:

- add explicit module/section/object/action breadcrumb context support in shared templates
- update shared list and detail templates to use those labels
- replace the hardcoded shared `Explorer` label with real module labels
- harden shared page-title logic so `None` is not rendered
- introduce a general object display-label path for shared detail pages

Primary file targets:

- `brit/templates/base.html`
- `brit/templates/filtered_list.html`
- `brit/templates/detail_with_options.html`
- shared view mixins that currently provide `header`, `title`, `dashboard_url`, or object metadata
- model helpers where a general display-label contract is best owned at the model layer

Success criteria:

- shared list pages render `BRIT > <Module> > <Entity>`
- shared detail pages render `BRIT > <Module> > <Entity> > <Object>` where appropriate
- shared detail pages no longer require `object.name`
- page titles no longer render `None`

## Phase 2 - Normalize the major module landing pages and CRUD families

Goal: apply the shared contract consistently to the highest-traffic core apps.

Deliverables:

- normalize explorer/dashboard breadcrumbs for:
  - `materials`
  - `maps`
  - `sources`
  - `bibliography`
  - `inventories`
  - `processes`
  - `utils` where it remains a user-facing area
- decide the canonical module label versus entity label for each app
- fix known user-facing label problems such as:
  - irregular plurals
  - entity names that should be displayed differently in breadcrumbs
  - module/entity conflation such as `Inventories` versus `Scenarios`

Success criteria:

- the main explorer pages use a stable module-first breadcrumb structure
- list/detail/form paths are consistent within each major app
- the most obvious label-quality defects are removed

## Phase 3 - Handle nested domains, plugins, and custom detail experiences

Goal: make breadcrumb depth consistent across pages that cannot be solved by generic CRUD conventions alone.

Deliverables:

- define canonical nested paths for source-domain pages, for example:
  - `BRIT > Sources > Waste Collection > Collections > <Collection>`
  - `BRIT > Sources > Greenhouses > <Greenhouse>` or another deliberate equivalent if case-study ownership should remain visible
- normalize plugin-mounted domains so they expose the same breadcrumb contract as core apps
- review custom pages such as `sample_detail_v2` and decide whether they should follow:
  - module-first entity hierarchy
  - parent-object hierarchy
  - or an explicitly richer custom path

Success criteria:

- similar source-domain pages use similar breadcrumb depth
- plugin-mounted pages no longer feel structurally separate from the rest of the app
- custom rich breadcrumbs follow a clearly documented hierarchy rather than one-off intuition

## Phase 4 - Fix static pages, review pages, and error states

Goal: eliminate technical fallbacks from user-visible breadcrumbs on non-CRUD pages.

Deliverables:

- add explicit breadcrumb labels for:
  - privacy-policy and other static pages
  - review/moderation dashboards
  - 404 and other error templates where breadcrumbs are shown
- decide when breadcrumbs should be omitted entirely on exceptional pages rather than forced through the base fallback
- remove reliance on raw route-name humanization for user-facing pages

Success criteria:

- no important page renders a breadcrumb like `Privacypolicy` or `Redirect`
- review/moderation pages expose a clear area label such as `Review`
- error states either show a user-facing breadcrumb or deliberately suppress it

## Phase 5 - Regression hardening, cleanup, and documentation alignment

Goal: make breadcrumb quality sustainable instead of one more brittle template layer.

Deliverables:

- add or expand test coverage for representative breadcrumb cases
- verify all primary nav paths through manual click-through and, where possible, automated assertions
- document the breadcrumb contract for future contributors
- reduce or isolate remaining fallback-only behavior
- ensure new pages follow the contract by default rather than inventing breadcrumb strings ad hoc

Success criteria:

- breadcrumb regressions are caught in tests for shared patterns
- a future contributor can add a new page by following one documented contract
- fallback behavior exists only as compatibility or safety behavior, not as the dominant UX path

## 8. Recommended Ordering of Immediate Work

| Order | Slice | Reason |
|---|---|---|
| 1 | Phase 1 shared breadcrumb contract | biggest leverage across the app and prerequisite for clean module rollout |
| 2 | Phase 2 major module normalization | removes the most visible user inconsistency quickly |
| 3 | Phase 4 static/review/error cleanup | low implementation complexity, high polish value, and closes embarrassing fallback leaks |
| 4 | Phase 3 nested-domain and custom-page normalization | important but depends on explicit structural decisions for source-domain ownership |
| 5 | Phase 5 regression hardening and cleanup | should follow once the new contract is stable enough to lock down |

Notes on ordering:

- Phase 3 and Phase 4 can be swapped if plugin-mounted source-domain inconsistency becomes the highest product pain.
- The first implementation slice should stay focused on shared templates and view metadata rather than trying to solve every page manually at once.
- The tester-reported defects should be treated as acceptance examples for early phases, but they should not dictate the long-term hierarchy if they merely preserve a weak `Explorer` abstraction.

## 9. Non-Goals

This roadmap should explicitly avoid the following mistakes.

- **Do not standardize on `Explorer` as the universal middle crumb**
  - the point is to expose real module structure, not to preserve a generic placeholder everywhere

- **Do not let route names or Django defaults become the long-term label contract**
  - technical names are acceptable only as temporary fallbacks

- **Do not force every page into a deep breadcrumb if the information architecture does not justify it**
  - nested depth should reflect real structure, not artificial symmetry

- **Do not mix multiple competing hierarchies on one page without documenting the canonical one**
  - especially on custom detail pages with rich related-object context

- **Do not solve browser-title issues by making breadcrumbs verbose**
  - page titles and breadcrumb labels should be aligned, but they do not have to be identical

## 10. Definition of Done for the Target State

Breadcrumb navigation can be considered materially aligned across BRIT when all of the following are true:

- every important user-facing page either renders a deliberate breadcrumb or intentionally suppresses breadcrumbs for a documented reason
- shared list pages use a real module label rather than a generic `Explorer` crumb
- shared detail pages do not depend on `object.name` alone
- list, detail, and create/edit pages in the same module expose the same structural hierarchy
- nested source-domain pages expose a deliberate, documented path rather than ad hoc depth
- static, review, and error pages no longer expose technical fallback labels
- browser titles do not render `None`
- representative breadcrumb behavior is covered by focused tests and click-through verification
- future pages can adopt the breadcrumb contract without reintroducing manual string duplication or template-local hacks

## 11. Immediate Next Slice

If work should continue now, the best next implementation slice is:

1. define the explicit shared breadcrumb contract for module, section, object, and action labels
2. refactor `filtered_list.html` and `detail_with_options.html` to use that contract instead of `Explorer` and `object.name`
3. wire the contract into the main view mixins and fix the highest-signal label defects in one core module each from `materials`, `bibliography`, `maps`, and `inventories`
4. add focused regression tests for:
   - irregular plural labels
   - non-`name` detail objects
   - pages that previously rendered `BRIT | None`
   - pages that previously fell through to raw route-name labels

That slice is small enough to be implemented safely and large enough to validate the breadcrumb architecture before deeper nested-domain cleanup begins.
