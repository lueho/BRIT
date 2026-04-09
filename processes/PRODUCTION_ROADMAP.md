# Processes Module - Roadmap

This file tracks future development only.
Current module behavior belongs in `README.md`.

## Near-term cleanup

### 1. Documentation and surface cleanup

- Keep `README.md` as the only current-behavior document for the module
- Keep this roadmap focused on future work only

### 2. Canonical route and template cleanup

- Review whether duplicate route aliases should remain supported long-term
- Remove or archive inactive mock/demo templates if they are no longer part of the supported module surface
- Reduce any remaining duplication between dashboard, explorer, and process-type naming

## Workflow and moderation improvements

### 3. Moderation ergonomics

- Add group-based setup guidance or automation for process moderators
- Add a dedicated moderation/dashboard view if the review workload grows
- Consider batch moderation actions for larger review queues

### 4. Workflow visibility

- Add audit-oriented review summaries where useful
- Add optional notifications for newly submitted or changed review items

## User experience improvements

### 5. Dashboard and explorer polish

- Refine the dashboard so it better highlights recent activity, category coverage, and process counts
- Improve discoverability between categories, processes, and process variants

### 6. Form and editing improvements

- Improve inline editing UX for materials, parameters, links, resources, and references
- Add more contextual guidance for complex process forms where needed
- Refine autocomplete behavior and result presentation if larger datasets make selection harder

## Data presentation and exports

### 7. Export support

- Add CSV and/or PDF export for process detail and list views if users need distributable records
- Consider comparison-oriented exports for process variants or categories

### 8. Visualization

- Add process-flow or hierarchy visualizations if they become useful for analysis
- Consider grouped parameter summaries or material-flow visual aids on detail pages

## Automation and integrations

### 9. Background tasks and derived outputs

- Add Celery-backed tasks only where operations become slow enough to justify async handling
- Add derived summaries or reports if downstream modules need them

### 10. Integration opportunities

- Evaluate whether processes should expose stronger links into inventories, maps, or scenario workflows
- Expand the API only when a concrete integration requires more endpoints or better schema documentation

## Maintenance rule

- Completed work should move into `README.md` when it changes current behavior
- Historical implementation detail should not be reintroduced as separate long-form module docs
