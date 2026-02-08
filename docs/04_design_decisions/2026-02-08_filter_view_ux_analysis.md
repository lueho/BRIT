# Filter View UX Analysis & Improvement Proposals

**Date:** 2026-02-08  
**Status:** Proposal  
**Scope:** All `filtered_list.html`-based views and `simple_list_card.html`-based views

---

## 1. Executive Summary

The filter views follow a consistent two-column layout (8/4 grid) with a results table on the left and a sticky sidebar with Filters / Options / Learning tabs on the right. The architecture is solid and extensible, but several UX pain points exist around **redundant status signaling**, **information density**, **discoverability of actions**, **empty states**, **pagination**, and **mobile ergonomics**. This document catalogs each finding and proposes concrete improvements.

---

## 2. Publication Status Badges — Role & Necessity

### Current Behavior

Every row in a `UserCreatedObject` list shows a pill-shaped badge (Private / Review / Published / Rejected / Archived) via `status_actions_cell.html` → `review_status_badge.html`, alongside a three-dot action dropdown.

### Analysis

| Scope | Badge adds value? | Rationale |
|---|---|---|
| **Published list** (`list_type='published'`) | **No** — all items are published by definition. The badge is pure visual noise. | The scope toggle already tells the user "these are published items." |
| **Private list** (`list_type='private'`) | **Yes, partially** — items can be Private, In Review, or Declined. The badge disambiguates. | But it competes for attention with the actions dropdown, and the status information could be communicated more efficiently. |
| **Review list** (`list_type='review'`) | **Minimal** — all items are in review by definition. Badge is near-redundant, though it maintains visual consistency. | Moderators already know the context from the scope toggle. |

### Proposals

1. **Hide status badges in single-status scopes.** In the Published and Review scopes, every badge says the same thing. Suppress the badge when `list_type` is `published` or `review`. This reclaims horizontal space and reduces cognitive load.
2. **Keep badges in the Private ("My") scope**, where items genuinely have mixed statuses. Consider making the badge the *primary* visual element and moving the action dropdown into it (click badge → popover with actions), or at minimum reducing badge + dropdown to a single compact element.
3. **Alternative: icon-only badges in compact views.** Replace the text badge with just the icon (`🔒`, `🔍`, `🌐`, `✗`, `📦`) and rely on a tooltip for the label. This saves ~60 px per row.

---

## 3. Information Display in the Results Table

### Current Behavior

The base `filtered_list.html` template shows three columns: **Name**, **Description**, **Status/Actions**. Several child templates override this to show richer, more domain-specific content (e.g., `collection_filter.html` shows catchment + waste category + collector + year in a two-line cell).

### Findings

- **The default "Description" column is low value.** In models where `description` is long, it's truncated awkwardly. In models where it's empty or generic, the column wastes space. Only the overridden templates (materials, collections) have solved this by replacing it with contextual metadata.
- **No truncation in the default template.** `{{ object.description }}` renders the full field. Long descriptions push the Status/Actions column off-screen, especially on tablets.
- **Inconsistent table classes.** Some templates use `table modern-table`, others use `table table-responsive-stack`, others just `table`. This leads to inconsistent hover, striping, and responsive behavior.
- **No result count in the base template.** The overridden templates (`collection_filter.html`, `sample_filter.html`, `material_list.html`) each manually add `Showing X-Y of Z results`. This should be in the base.
- **No empty state in `filtered_list.html`.** Unlike `simple_list_card.html` which has `{% empty %} No objects available`, `filtered_list.html` renders a table with headers but zero rows and no feedback message.

### Proposals

4. **Replace the default "Description" column with a two-line cell pattern.** Make the base template use the pattern already proven in the overrides: a bold primary line (name/link) and a muted secondary line (truncated description or key metadata). This eliminates the dedicated Description column and makes every list more scannable.
5. **Add `|truncatewords:15` or `|truncatechars:80`** to any remaining description output to prevent layout breakage.
6. **Standardize table classes.** Use `table modern-table` everywhere in `filtered_list.html`-based views. Define a single responsive wrapper pattern.
7. **Move the result count into `filtered_list.html`.** Add `Showing {{ page_obj.start_index }}–{{ page_obj.end_index }} of {{ page_obj.paginator.count }} results` just above the table in the base template. Remove it from all overrides.
8. **Add an empty state to `filtered_list.html`.** After the `{% for %}` loop, add `{% empty %}` with a friendly message like "No items match your filters" and a link to reset filters.

---

## 4. Discoverability & Intuitiveness of Actions and Options

### 4a. The Three-Dot Dropdown

- **Strength:** Consolidates all actions (View, Edit, Delete, Submit for Review, Approve, Reject, Withdraw, Archive) into a single menu. Policy-based visibility (`{% object_policy %}`) means users only see what they can do.
- **Weakness:** The three-dot button gives zero affordance about *what* actions are available. A moderator looking at the review list has no way to know an item is approvable without opening every dropdown. In high-throughput review workflows this is a significant friction point.

### Proposals

9. **Add a quick-approve button for the review scope.** In `list_type='review'`, surface a small green ✓ button directly in the row (outside the dropdown) for the most common action. The dropdown remains for less frequent actions (Reject, Comment, View Details).
10. **Consider batch actions for moderators.** Checkbox-based selection + toolbar for Approve/Reject multiple items. This is a substantial feature but would dramatically improve review throughput.

### 4b. The Scope Toggle (Published / My / Review)

- **Strength:** Clear segmented button group, well-placed in the card header, properly aria-labeled.
- **Weakness: "My" is ambiguous.** "My" what? "My items"? "My bookmarks"? A new user might not immediately understand this shows *items they own*. The tooltip says "Show only my items" which helps, but the label itself is weak.
- **Weakness: Filters are lost on scope switch.** The scope toggle links strip `publication_status` and `id` params but keep other filters. This is mostly correct, but the user gets no visual confirmation that their filters carried over. If a filter narrows results to zero in the new scope, the user sees an empty list with no explanation.

### Proposals

11. **Rename "My" to "Mine" or "My Items".** Slightly more explicit. Or use an icon (`👤`) prefix to create the association with ownership.
12. **Show a toast/alert when scope switch results in zero items.** E.g., "No items match your current filters in this scope. [Reset filters]"

### 4c. The View Toggle (List / Map)

- **Good:** Only appears when a map URL exists for the current model.
- **Issue:** The toggle is a button group next to the scope toggle next to the Explorer button. On narrower large screens (992–1200 px), these three control groups wrap and create a cluttered header.

### Proposal

13. **Merge the view toggle into a single icon-button pair** (list icon / map icon) without text labels, with tooltips. This saves ~80 px and reduces visual competition with the scope toggle.

### 4d. The Sidebar Tabs (Filters / Options / Learning)

- **Issue: The "Options" tab is hard to discover.** The "Create new" button, Explorer link, and export actions are behind a secondary tab. Users who land on the Filters tab may never discover these. Creating a new object is a *primary* action, not an option.
- **Issue: The Learning tab auto-hides via JS if empty.** This is clever, but on pages where it *does* have content, there's no visual hint of what it contains. A user unfamiliar with the system has no reason to click "Learning."
- **Issue: Unauthenticated users see no sidebar content in `simple_list_card.html`.** The Options tab is wrapped in `{% if user.is_authenticated %}`, so anonymous users see an empty sidebar card with no tabs at all.

### Proposals

14. **Surface the "Create new" button above the sidebar tabs**, always visible, not behind Options. It's the most important action after filtering. The Options tab should contain *secondary* options (export, Explorer link, aggregation tools).
15. **Add a badge count or subtitle to the Learning tab** when it has content, e.g., "Learning (3)" or a small dot indicator.
16. **For anonymous users, show a minimal sidebar** with a "Log in to create and manage items" prompt instead of an empty card.

---

## 5. Filter Form UX

### 5a. Accordion Groups

The `CollectionFilterFormHelper` uses a crispy-forms Accordion with a "Filters" group (default open) and "Advanced filters" group (default closed). This is a good progressive-disclosure pattern.

- **Issue:** The accordion group labels ("Filters" and "Advanced filters") are generic. Users don't know what's inside without expanding.
- **Issue:** The `scope` field is hidden (`HiddenInput`) inside the "Advanced filters" accordion. If a user somehow opens it, they see a gap in the form.

### Proposals

17. **Name accordion groups descriptively.** E.g., "Location & waste type" / "Collection properties" instead of "Filters" / "Advanced filters."
18. **Move hidden fields (scope, id) entirely out of the accordion** and into a separate hidden-fields block that doesn't consume visual space inside any group.

### 5b. The publication_status Filter

In `CollectionFilterSet.__init__`, `publication_status` is hidden when scope ≠ private. This is correct behavior — but:

- **Issue:** The filter only appears in Private scope, yet is listed in the form helper layout for *all* scopes. This means in Published scope, there's an invisible gap in the "Filters" accordion where publication_status would be.
- **Issue:** When visible in Private scope, `publication_status` appears as a default Django select widget. Users may not understand the terminology (what's the difference between "Private" scope and "Private" publication status?).

### Proposals

19. **Remove `publication_status` from the accordion layout entirely.** Instead, render it as a small inline filter chip row above the table (like the chips already used in `collection_filter.html`), or as a dedicated small toggle inside the "My" scope view.
20. **Relabel `publication_status` to "Status"** and use more user-friendly labels: "Draft" (instead of Private), "Under Review", "Published", "Needs Changes" (instead of Declined), "Archived."

---

## 6. Pagination

### Current Behavior

Two different pagination implementations:
- `filtered_list.html`: inline `{% block list_pagination %}` with `param_replace` tag (preserves filter params).  
- `simple_list_card.html` and `partials/_pagination.html`: simpler version that does **not** preserve filter params on page navigation (`?page=N` only).

### Findings

- **`_pagination.html` loses filter state on page change.** Clicking "next" goes to `?page=2`, discarding all active filter params. This is a **critical bug** for any view using this partial with filters.
- **No page-size selector.** The page size is hardcoded at 10 (`paginate_by = 10`). Users dealing with hundreds of items have no way to show more per page.
- **Pagination is unstyled.** The `<span class="step-links">` with raw text links ("« first", "previous", "next", "last »") looks dated compared to the rest of the Bootstrap 5 UI.

### Proposals

21. **Fix `_pagination.html` to use `param_replace` or equivalent** to preserve query parameters across page changes.
22. **Style pagination as Bootstrap 5 pagination component** (`<nav><ul class="pagination">…</ul></nav>`).
23. **Add a page-size selector** (10 / 25 / 50 / All) in the Options tab, stored as a query param.

---

## 7. Mobile & Responsive Behavior

### Findings

- **Column layout flips correctly** (sidebar moves above content on mobile via `order-1`/`order-2`). Good.
- **The scope toggle + view toggle + Explorer button** create a very wide header on mobile, often wrapping to 2–3 lines.
- **Table rows with badge + dropdown** are wide. The `actions-column` doesn't collapse gracefully on small screens. The `mobile-no-label` class hides the data-label on mobile, but the badge text still takes space.
- **Sidebar is not collapsible on mobile.** It sits above the results, taking up the entire first screen. Users must scroll past it to see results.

### Proposals

24. **Make the sidebar collapsible on mobile** with an expand/collapse toggle. Default to collapsed, showing only "Filters (3 active)" as a summary.
25. **On mobile, move the scope toggle below the card header** as a full-width segmented control.
26. **On mobile, use icon-only badges** for status to conserve horizontal space.

---

## 8. Accessibility

### Findings

- **Good:** Scope toggles have `aria-pressed`, `aria-disabled`, `role="button"`. Sidebar tabs use proper `role="tablist"`/`role="tab"`/`role="tabpanel"`.
- **Issue:** Clickable table rows in `filtered_list.html` use `onclick="window.location=…"`. This is not keyboard-accessible (no `onkeypress`), and screen readers won't announce these as links. The `tabindex="0"` helps keyboard focus but doesn't trigger on Enter.
- **Issue:** The three-dot dropdown's `aria-label="More actions"` is generic. It should include the object name for screen readers.

### Proposals

27. **Add `onkeydown` handler** to clickable `<tr>` elements to navigate on Enter/Space, or preferably make the entire row link via CSS (`<a>` wrapping the `<tr>` content) rather than `onclick`.
28. **Include object name in the dropdown aria-label:** `aria-label="Actions for {{ object.name }}"`.

---

## 9. Consistency Across Templates

18 templates extend `filtered_list.html`. They override various blocks with varying levels of completeness:

| Pattern | Templates using it | Issue |
|---|---|---|
| Result count above table | collection, sample, material, review dashboard | Not in base; each copies the same snippet |
| Two-line cell (bold name + muted metadata) | collection, sample, material | Not in base; remaining templates show flat Name/Description |
| Filter chips | collection only | Should be generalized |
| Learning tab emptied via block override | sample, material | Should use the JS auto-hide already in base |

### Proposals

29. **Extract repeated patterns into the base template or reusable includes:**
    - Result count → base template
    - Two-line cell → define a `_list_row_cell.html` include with `{{ primary_text }}` and `{{ secondary_text }}` slots
    - Filter chips → generic include driven by filter form data
30. **Audit all 18 templates** and consolidate overrides. Many exist solely to add result counts or change column headers; with base improvements they could be eliminated.

---

## 10. Summary of Proposals (Priority Order)

| # | Proposal | Impact | Effort |
|---|---|---|---|
| 8 | Add empty state to `filtered_list.html` | High | Low |
| 21 | Fix `_pagination.html` to preserve filter params | High | Low |
| 1 | Hide status badges in single-status scopes | Medium | Low |
| 7 | Move result count into base template | Medium | Low |
| 5 | Add description truncation | Medium | Low |
| 20 | Relabel publication_status values | Medium | Low |
| 27 | Fix keyboard accessibility on clickable rows | High | Medium |
| 14 | Surface "Create new" above sidebar tabs | Medium | Medium |
| 4 | Adopt two-line cell as default pattern | Medium | Medium |
| 22 | Restyle pagination as Bootstrap 5 component | Medium | Medium |
| 16 | Show sidebar prompt for anonymous users | Medium | Low |
| 6 | Standardize table classes | Low | Low |
| 28 | Improve dropdown aria-labels | Medium | Low |
| 11 | Rename "My" to "My Items" or "Mine" | Low | Low |
| 13 | Use icon-only view toggle | Low | Low |
| 3 | Icon-only badges in compact mode | Low | Medium |
| 17 | Descriptive accordion group names | Low | Low |
| 18 | Move hidden fields out of accordion groups | Low | Low |
| 9 | Quick-approve button for review scope | High | Medium |
| 24 | Collapsible sidebar on mobile | Medium | High |
| 29 | Extract reusable template includes | Medium | High |
| 15 | Badge count on Learning tab | Low | Low |
| 12 | Toast on zero-result scope switch | Low | Medium |
| 23 | Page-size selector | Low | Medium |
| 10 | Batch actions for moderators | High | High |
| 25 | Full-width scope toggle on mobile | Low | Medium |
| 19 | publication_status as inline chips | Medium | Medium |
| 26 | Icon-only badges on mobile | Low | Medium |
| 30 | Template consolidation audit | Medium | High |
