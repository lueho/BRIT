# Task: Overhaul Card/List/Table UI with brit.css

- [x] Search notes/docs for prior UI/CSS context
- [x] Inventory existing brit.css rules
- [ ] Audit current card/table/list markup and classes for sb-admin-2 or Bootstrap remnants
- [ ] Inventory brit.css capabilities and gaps (colors, spacing, typography, etc.)
- [ ] Propose new design tokens/components if needed
- [ ] Redesign review status badges to match brit.css and modern design
- [ ] Update card/table/list markup to use brit.css classes, remove sb-admin-2/Bootstrap dependencies
- [ ] Refactor any remaining sb-admin-2 markup out of templates
- [ ] Update or create documentation on the new design approach
- [ ] Run tests and check for regressions
- [ ] Clean up dead code, obsolete notes, and update MADRs if needed
- [ ] Commit with an imperative, 50-char summary and clear body
- [ ] Push branch, open PR, ensure CI is green

## Context
- Goal: Move to a fully custom design (brit.css), phasing out sb-admin-2/Bootstrap.
- Initial focus: cards, tables, status badges, dropdowns, and detail views.
- Design should be modern, clean, and consistent across the app.

---

## Notes
- brit.css currently contains utility tweaks (e.g. select2, nowrap, .url-cell), but lacks a full design system (colors, spacing, typography, card/table styles).
- Next: Audit markup for Bootstrap/sb-admin-2 classes; propose brit.css enhancements.
