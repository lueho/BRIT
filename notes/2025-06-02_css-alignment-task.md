# Task: Unify and Modularize CSS/SCSS (Phase out sb-admin-2)

- [x] Review notes/docs for prior context
- [x] Inventory CSS/SCSS/mobile/sb-admin-2 files
- [x] Determine classification: global vs collection-specific for each mobile.css rule
- [x] Move global styles to scss/partials/_mobile_global.scss
- [x] Move collection-specific styles to scss/partials/_collections.scss
- [x] Refactor selectors using SCSS variables and responsive mixins
- [x] Remove integrated rules from mobile.css
- [ ] Test collection views at various breakpoints
- [ ] Document new mobile patterns in notes/frontend/
- [ ] Audit recent changes in mobile.css for overlap with sb-admin-2 and SCSS
- [ ] Recommend approach for reducing direct overrides and specificity issues
- [ ] Outline steps for removing sb-admin-2/Bootstrap dependencies from markup and styles
- [ ] Summarize session and update MADR if design direction changes
- [ ] Run tests and check for regressions
- [ ] Clean up obsolete CSS, notes, and update docs
- [ ] Commit with clear summary and rationale
- [ ] Push branch, open PR, confirm CI is green

- [ ] Integrate `brit.css` custom rules into SCSS
  - [ ] Inventory and categorize rules in `brit.css`
  - [ ] Merge card styles into `_cards.scss`
  - [ ] Merge table styles into `_tables.scss`
  - [ ] Merge dropdown styles into `_dropdowns.scss`
  - [ ] Merge badge & review-status styles into `_user-created-objects.scss`
  - [ ] Move utility classes into `_utilities.scss` or new partials
  - [ ] Remove `brit.css` from the build pipeline
  - [ ] Test UI across breakpoints
  - [ ] Update documentation in `notes/frontend/`

## Context
- Goal: Migrate to a fully custom design system, eliminate sb-admin-2/Bootstrap dependencies, and keep mobile/responsive styles maintainable and modular.
- Current: mobile.css overrides sb-admin-2 but is not modular; SCSS structure is in place for custom system.
- Next: Modularize mobile styles, reduce specificity wars, document patterns, and phase out sb-admin-2.
