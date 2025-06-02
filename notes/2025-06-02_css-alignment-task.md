# Task: Unify and Modularize CSS/SCSS (Phase out sb-admin-2)

- [x] Review notes/docs for prior context
- [x] Inventory CSS/SCSS/mobile/sb-admin-2 files
- [ ] Audit recent changes in mobile.css for overlap with sb-admin-2 and SCSS
- [ ] Propose plan for modularizing mobile styles (move to SCSS, use variables, etc.)
- [ ] Recommend approach for reducing direct overrides and specificity issues
- [ ] Outline steps for removing sb-admin-2/Bootstrap dependencies from markup and styles
- [ ] Document any new mobile/responsive patterns in notes/frontend/
- [ ] Summarize session and update MADR if design direction changes
- [ ] Run tests and check for regressions
- [ ] Clean up obsolete CSS, notes, and update docs
- [ ] Commit with clear summary and rationale
- [ ] Push branch, open PR, confirm CI is green

## Context
- Goal: Migrate to a fully custom design system, eliminate sb-admin-2/Bootstrap dependencies, and keep mobile/responsive styles maintainable and modular.
- Current: mobile.css overrides sb-admin-2 but is not modular; SCSS structure is in place for custom system.
- Next: Modularize mobile styles, reduce specificity wars, document patterns, and phase out sb-admin-2.
