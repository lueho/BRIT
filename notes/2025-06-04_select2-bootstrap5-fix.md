# Task: Fix Select2 Bootstrap 5 Compatibility Issue

## Problem
Select2 fields (like the Catchment form field) have incorrect height due to conflicting styles:
- Select2 base styles set `height: 28px` 
- Bootstrap 5 theme uses `min-height: calc(1.5em + .75rem + 2px)`
- This causes visual misalignment with other form controls

## Root Cause
1. django-autocomplete-light and django-crispy-forms have known compatibility issues with style/JS loading order
2. The project is mid-migration from Bootstrap 4 to 5, causing style conflicts
3. Select2 Bootstrap 5 theme is not fully overriding base styles

## Solution
Add SCSS overrides to ensure Select2 fields match Bootstrap 5 form control heights:

```scss
// Select2 Bootstrap 5 height fix
.select2-container--bootstrap-5 {
  .select2-selection--single {
    height: auto !important;  // Remove fixed 28px height
    min-height: calc(1.5em + .75rem + 2px);  // Match Bootstrap 5 form-control
  }
}
```

## Implementation Steps
1. [x] Document the issue
2. [x] Add fix to _forms.scss
3. [ ] Test across different form contexts
4. [ ] Verify autocomplete functionality still works
5. [ ] Check responsive behavior

## Fix Applied
Added SCSS overrides in `brit/static/scss/_forms.scss`:
- Removed hardcoded 28px height from select2 single selection
- Set min-height to match Bootstrap 5 form controls
- Fixed text vertical alignment with proper padding and line-height
- Centered the dropdown arrow vertically
- **Enforced `box-sizing: border-box;` on Select2 containers, selections, and rendered elements to correctly calculate width including padding/borders.**
- **Reinforced `width: 100% !important;` and `max-width: 100% !important;` on Select2 elements within `.card-body` and other relevant contexts to prevent width overflow.**
- **Modified `utils/forms.py` in `apply_select2_theme` function to set `data-width: "style"` (was `"resolve"`) for Select2 widgets. This prevents Select2 JavaScript from overriding CSS width and ensures it respects the 100% width set in SCSS.**
- **Added `min-width: auto !important;` to SCSS rules for Select2 containers to override a default `min-width: 20em;` from base Select2 styles, which was causing overflow when 100% width was less than 20em.**

## Notes
- The Live Sass Compiler will automatically compile the SCSS changes
- The fix targets `.select2-container--bootstrap-5` to avoid affecting any legacy Select2 instances
- Form media loading order is already handled in templates via `{{ form.media }}` blocks

## Related
- Bootstrap 5 migration task: notes/2025-06-03_bootstrap5-migration-task.md
- Frontend design goals: Remove sb-admin-2 theme dependencies
