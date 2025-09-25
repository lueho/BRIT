# Publication dependency management

This guide explains the publication dependency model implemented in the last four commits and how to work with it as a developer.

It covers the following:
- What a dependency is and where the rules live
- Pre‑publish checks that gate review/approval
- Automatic status cascading to children
- UI checklist for resolving issues
- Safe visibility of child relations on public pages
- How to onboard new models to the dependency system


## Overview

User editable domain objects in BRIT inherit from `utils/object_management/models.py:UserCreatedObject`. They participate in a review workflow with these statuses:
- `private`
- `review`
- `published`
- `declined`
- `archived`

Publication dependencies ensure that:
- An object cannot be submitted or approved while it references unpublished dependencies.
- When a parent transitions (e.g., to review/published), configured children automatically follow to the same status.
- Public pages of published objects render only published child data to avoid leaks.

The system is registry‑driven and lives in `utils/object_management/publication.py`.


## Registry and rule types

File: `utils/object_management/publication.py`

Key types:
- `RelationRule(accessor: str, label: str | None = None, optional: bool = False)`
  - Declares how to access a related object or collection on the model (attribute name, property, or manager).
  - `optional=True` means missing relation is not a blocking error.
- `DependencyConfig(requires_published: Sequence[RelationRule], follows_parent: Sequence[RelationRule])`
  - `requires_published`: relations that must exist and be in `published` state before submit/approval.
  - `follows_parent`: relations whose `publication_status` must mirror the parent when it changes.

The global `REGISTRY` maps `(app_label, model_name)` → `DependencyConfig`. Example (abridged):

```python
REGISTRY = {
    ("materials", "sample"): DependencyConfig(
        requires_published=(
            RelationRule("material", label="material"),
            RelationRule("series", label="sample series", optional=True),
            RelationRule("timestep", label="timestep", optional=True),
            RelationRule("sources", label="source"),
        ),
        follows_parent=(
            RelationRule("properties", label="material property value"),
            RelationRule("compositions", label="composition"),
        ),
    ),
    ("materials", "composition"): DependencyConfig(
        requires_published=(
            RelationRule("group", label="component group"),
            RelationRule("fractions_of", label="reference component", optional=True),
        ),
        follows_parent=(RelationRule("shares", label="weight share"),),
    ),
    ("materials", "weightshare"): DependencyConfig(
        requires_published=(RelationRule("component", label="component"),),
    ),
    ("materials", "materialpropertyvalue"): DependencyConfig(
        requires_published=(RelationRule("property", label="material property"),),
    ),
    ("materials", "sampleseries"): DependencyConfig(
        requires_published=(
            RelationRule("material", label="material"),
            RelationRule("temporal_distributions", label="temporal distribution"),
        ),
    ),
    ("distributions", "timestep"): DependencyConfig(
        requires_published=(RelationRule("distribution", label="temporal distribution"),),
    ),
    ("bibliography", "source"): DependencyConfig(
        requires_published=(RelationRule("licence", label="licence", optional=True),),
    ),
}
```

Accessors can be:
- A direct FK attribute (`material`, `group`)
- An optional FK (`series`, `timestep`)
- A reverse manager/ManyToMany (`properties`, `compositions`, `shares`, `sources`)
- A property that returns a value or queryset


## Pre‑publish checks

Function: `prepublish_check(obj, target_status: str | None = None) -> PrepublishReport`

- Collects dependency issues before state transitions.
- Returns `PrepublishReport` with:
  - `blocking`: missing or unpublished `requires_published` relations
  - `needs_sync`: `follows_parent` relations whose status differs from `target_status`
- Handles both single objects and querysets via `_resolve_related()`.
- Uses `_is_published()` to test `publication_status == STATUS_PUBLISHED` when present.

Human‑readable formatting:
- `PrepublishReport.format_blocking_message(obj, action)` builds a localized message with bullet points suitable for raising as `ValidationError`.

Where it’s enforced: `utils/object_management/models.py:UserCreatedObject`
- `submit_for_review()` calls `prepublish_check(self, target_status=self.STATUS_REVIEW)` and raises `ValidationError` if `report.has_blocking()`.
- `approve(user=...)` calls `prepublish_check(self, target_status=self.STATUS_PUBLISHED)` with the same gating.

Review action views handle these errors centrally:
- `utils/object_management/views.py:BaseReviewActionView.handle_review_action_post()` catches `ValidationError`, flashes the error, and redirects to the Checklist UI (see below) with a helpful link and preserved `next`.


## Cascading publication status

Function: `cascade_publication_status(obj, target_status: str, acting_user: object | None = None)`

- Ensures all `follows_parent` relations adopt the parent’s new `publication_status`.
- Recurses depth‑first and uses a `visited` set of `(app_label, model_name, pk)` to prevent cycles.
- Applies field updates via `_apply_status_change(child, target_status, acting_user)`:
  - `publication_status`: set to `target_status`
  - `submitted_at`: set on `review`, cleared on `private`/`declined`
  - `approved_at`/`approved_by`: set on `published`, cleared otherwise
  - Saves with minimal `update_fields` for efficiency

Where it’s applied: `UserCreatedObject` transitions
- `submit_for_review()` → cascade to `review`
- `withdraw_from_review()` → cascade to `private`
- `approve(user)` → cascade to `published` (propagates `approved_by` where applicable)
- `reject()` → cascade to `declined`
- `archive()` → cascade to `archived`

This makes parent/child consistency explicit and automatic according to the registry.


## UI: Publication Checklist

View: `utils/object_management/views.py:PublicationChecklistView`

Route: `object_management:publication_checklist` at
`/object_management/publication/checklist/<content_type_id>/<object_id>/`

Template: `utils/object_management/templates/object_management/publication_checklist.html`

Behavior:
- Access control via `get_object_policy()`; owner, staff, or moderator may view.
- Computes `report = prepublish_check(obj, target_status)` where `target_status` defaults to `published` or can be overridden with `?target=...`.
- Renders:
  - Blocking dependencies (red) with `DependencyIssue.describe()`
  - Items requiring status sync (yellow) that will auto‑update during the action
  - Contextual actions the user is allowed to perform (Edit, Submit, Withdraw, Approve, Reject)
- Integrated with review actions: failed submit/approve links here automatically, preserving `next`.


## Safe visibility on public pages

To prevent leakage of unpublished child data when a parent is public, the materials models expose filtered accessors and serializers consume them only when the parent is `published`.

Models: `materials/models.py`
- `Sample.visible_sources`
- `Sample.visible_properties`
- `Sample.visible_compositions`
- `Composition.visible_shares`

Serializers: `materials/serializers.py`
- `SampleModelSerializer.to_representation()` switches `compositions`, `properties`, and `sources` to the `visible_*` accessors when `instance.is_published`.
- `CompositionModelSerializer` and `CompositionDoughnutChartSerializer` read `obj.visible_shares`.

Views/templates:
- `materials/views.py:SampleDetailView` uses `visible_compositions` for chart data.
- `materials/templates/materials/sample_detail.html` iterates `object.visible_sources`, `object.visible_properties`, and each `composition.visible_shares` in the table view.

Performance:
- `SampleDetailView.queryset` uses `select_related` and `prefetch_related` for the relations used by the `visible_*` accessors.


## How to add a model to the dependency system

1. Define relationships on your model (`FK`, `M2M`, reverse relations) and ensure related models that should publish independently also inherit from `UserCreatedObject`.
2. Add a `DependencyConfig` entry to `REGISTRY` in `utils/object_management/publication.py`:
   - Put required references in `requires_published` (use `optional=True` for non‑required relations).
   - Put child collections that must mirror status in `follows_parent`.
3. If the model renders child data publicly, add filtered accessors similar to `visible_*` in your model for safe public rendering.
4. Update serializers to use `visible_*` when the parent is `published`.
5. Verify submit/approve flows:
   - Submitting or approving should raise a `ValidationError` with a clear message if dependencies are missing/unpublished.
   - The Checklist should load and display the issues.
6. Tests (optional per project policy): see `utils/object_management/tests/test_publication.py` for examples.


## Programmatic usage examples

- Pre‑flight check in custom logic:

```python
from utils.object_management.publication import prepublish_check

report = prepublish_check(my_obj, target_status=my_obj.STATUS_PUBLISHED)
if report.blocking:
    raise ValidationError(report.format_blocking_message(my_obj, "approve"))
```

- Manual cascade (typically not needed outside transitions):

```python
from utils.object_management.publication import cascade_publication_status

cascade_publication_status(my_obj, my_obj.STATUS_REVIEW, acting_user=request.user)
```


## Common pitfalls

- Missing registry entry: `prepublish_check()`/`cascade_publication_status()` will no‑op silently. Ensure your model is registered.
- Accessor name mismatch: `RelationRule.accessor` must match the attribute/property/manager on the model.
- Rendering leaks: when adding public pages, always use `visible_*` accessors if the parent can be published.
- Parentheses in templates: do not use parentheses in `{% if %}` conditions; use simple boolean logic or nested blocks.


## Related files

- `utils/object_management/publication.py` – registry, rules, checks, and cascade engine
- `utils/object_management/models.py` – `UserCreatedObject` transitions wire checks and cascades
- `utils/object_management/views.py` – Review action views and `PublicationChecklistView`
- `utils/object_management/templates/object_management/publication_checklist.html` – Checklist UI
- `materials/models.py` – safe visibility helpers on `Sample` and `Composition`
- `materials/serializers.py` – serializers consuming `visible_*`
- `materials/views.py` – `SampleDetailView` prefetch and charts using visible compositions
- `materials/templates/materials/sample_detail.html` – public page consuming visible data


## Changelog summary (last four commits)

- perf(materials): prefetch sample detail relations; respect `visible_shares`
- test(publication): ensure nested serializers receive request context
- feat(publication): add `PublicationChecklistView` and route; render only visible compositions on `SampleDetailView`
- feat(publication): enforce dependency checks and cascade publication status, add registry and safe visibility helpers
