"""Policy-safe persistence for programmatic collection evidence writes.

These helpers back the public CPV/ACPV create-or-reuse API endpoints. They
exist because the trusted workbook importer is not an authorization
boundary: it deletes generated rows by data key, attaches references to
arbitrary existing records, and submits generated rows independently. The
service functions here authorize every reference through the shared core
(``decide``/``visible_queryset``/``content_mutation``/``perform_transition``),
lock the actor and all parents before writing, and never touch, reuse, or
submit generated projections.
"""

from dataclasses import dataclass
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from utils.object_management.policy import decide, visible_queryset
from utils.object_management.services import (
    content_mutation,
    perform_transition,
    record_creation,
)
from utils.properties.models import Property, Unit

from .models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionPropertyValue,
    WasteFlyer,
)

FLYER_URL_MAX_LENGTH = 2083


@dataclass(frozen=True)
class EvidenceMutationResult:
    value: "CollectionPropertyValue | AggregatedCollectionPropertyValue"
    created: bool
    submitted: bool
    flyers_created: int


def _locked_actor(actor):
    """Reload and lock the active actor row; missing or inactive is denied.

    ``FOR NO KEY UPDATE`` serializes same-actor API calls without blocking
    the FK key-share checks a concurrent ``content_mutation`` needs when
    inserting ``ReviewAction`` rows that reference the actor — a plain
    ``FOR UPDATE`` user lock deadlocks against that ordering.
    """
    if getattr(actor, "pk", None) is None or not getattr(
        actor, "is_authenticated", False
    ):
        raise PermissionDenied("authentication_required")
    try:
        fresh = get_user_model().objects.select_for_update(no_key=True).get(pk=actor.pk)
    except get_user_model().DoesNotExist as exc:
        raise PermissionDenied("authentication_required") from exc
    if not fresh.is_active:
        raise PermissionDenied("authentication_required")
    return fresh


def resolve_evidence_definitions(actor, *, property_id, unit_name):
    """Resolve the measurement property and unit for a mutation request.

    The property must exist and be readable by the actor. The unit must be
    an accessible exact-name match; inaccessible private units with the same
    name neither shadow an accessible row nor leak, and more than one
    accessible same-name unit fails closed rather than guessing.
    """
    prop = Property.objects.filter(pk=property_id).first()
    if prop is None:
        raise ValidationError(
            {"property_id": [f"Property id={property_id} not found."]}
        )
    if not decide(actor, "read", prop).allowed:
        raise PermissionDenied("The referenced property is not accessible.")

    units = visible_queryset(actor, Unit.objects.filter(name=unit_name)).order_by("pk")
    if not units.exists():
        raise ValidationError({"unit_name": [f"Unit '{unit_name}' not found."]})
    if units.count() > 1:
        raise ValidationError({"unit_name": [f"Unit '{unit_name}' is ambiguous."]})
    return prop, units[0]


def flyer_title(url):
    """Short flyer title derived from the URL hostname (max 255 chars)."""
    try:
        hostname = urlparse(url).hostname or url
    except Exception:
        hostname = url
    return hostname[:255]


def _usable_flyer_urls(flyer_urls):
    """Ordered, de-duplicated flyer URLs within the stored length limit."""
    urls = []
    for url in flyer_urls or []:
        if not url or len(url) > FLYER_URL_MAX_LENGTH or url in urls:
            continue
        urls.append(url)
    return urls


def _preflight_references(actor, sources, flyer_urls):
    """Authorize every referenced source and flyer URL without writing."""
    for source in sources or []:
        if not decide(actor, "read", source).allowed:
            raise PermissionDenied("The referenced source is not accessible.")
    for url in _usable_flyer_urls(flyer_urls):
        existing = WasteFlyer.objects.filter(url=url).order_by("pk").first()
        if existing is not None:
            if not decide(actor, "read", existing).allowed:
                raise PermissionDenied("The referenced flyer is not accessible.")
        elif not decide(actor, "create", WasteFlyer).allowed:
            raise PermissionDenied("You do not have permission to add waste flyers.")


def resolve_flyer(actor, url):
    """Find-or-create a flyer the actor may reference.

    The existing-row lookup and the read/create decision run before any
    write attempt; the post-resolution recheck handles a lost race to an
    unreadable row so the surrounding transaction can roll back.
    """
    existing = WasteFlyer.objects.filter(url=url).order_by("pk").first()
    if existing is not None:
        if not decide(actor, "read", existing).allowed:
            raise PermissionDenied("The referenced flyer is not accessible.")
    elif not decide(actor, "create", WasteFlyer).allowed:
        raise PermissionDenied("You do not have permission to add waste flyers.")
    flyer, created = WasteFlyer.objects.get_or_create_by_url(
        url=url,
        defaults={
            "owner": actor,
            "title": flyer_title(url),
            "publication_status": "private",
        },
    )
    if created:
        record_creation(actor, flyer)
    elif not decide(actor, "read", flyer).allowed:
        raise PermissionDenied("The referenced flyer is not accessible.")
    return flyer, int(created)


def _requested_reference_pks(sources, flyer_urls):
    """Persisted source/flyer pks the request asks to link (new URLs return
    a sentinel so an unflyered URL always counts as a relation delta)."""
    pks = {source.pk for source in sources or []}
    has_new_flyer = False
    for url in _usable_flyer_urls(flyer_urls):
        flyer = WasteFlyer.objects.filter(url=url).order_by("pk").first()
        if flyer is None:
            has_new_flyer = True
        else:
            pks.add(flyer.pk)
    return pks, has_new_flyer


def _apply_new_relations(actor, record, sources, flyer_urls):
    """Attach only not-yet-linked references; flyers are resolved under the
    active write boundary. Returns the number of newly created flyers."""
    linked = set(record.sources.values_list("pk", flat=True))
    new_sources = [s for s in sources or [] if s.pk not in linked]
    for source in new_sources:
        if not decide(actor, "read", source).allowed:
            raise PermissionDenied("The referenced source is not accessible.")
    if new_sources:
        record.sources.add(*new_sources)
    flyers_created = 0
    flyers = []
    for url in _usable_flyer_urls(flyer_urls):
        flyer, created = resolve_flyer(actor, url)
        flyers_created += created
        if flyer.pk not in linked:
            flyers.append(flyer)
    if flyers:
        record.sources.add(*flyers)
    return flyers_created


def _submit_if_requested(actor, record, submit_for_review):
    """Submit a raw evidence row for review when asked and lifecycle-eligible.

    Only owner/admin may submit; an editor grant never silently submits
    another owner's draft. Already review/published/archived rows are left
    untouched so idempotent reuse emits no duplicate submission event.
    """
    if not submit_for_review:
        return record, False
    if record.publication_status not in ("private", "declined"):
        return record, False
    fresh = perform_transition(actor, record, "submit")
    return fresh, True


def create_or_reuse_collection_property_value(
    actor,
    *,
    collection,
    measurement_property,
    unit,
    year,
    average,
    standard_deviation=None,
    sources=(),
    flyer_urls=(),
    submit_for_review=True,
):
    """Create or reuse a raw ``CollectionPropertyValue`` under policy.

    The write anchors to the requested collection's stored ``version_anchor``
    under row locks; a stale anchor denies rather than writing against a
    reparented context. Reuse only returns a record the actor can read;
    generated projections are never candidates and never returned.
    """
    with transaction.atomic():
        fresh_actor = _locked_actor(actor)

        if not decide(fresh_actor, "read", collection).allowed:
            raise PermissionDenied("The referenced collection is not accessible.")
        requested_anchor = collection.version_anchor or collection
        lock_ids = sorted({collection.pk, requested_anchor.pk})
        locked = {
            row.pk: row
            for row in Collection.objects.select_for_update(no_key=True)
            .filter(pk__in=lock_ids)
            .order_by("pk")
        }
        locked_target = locked.get(collection.pk)
        if locked_target is None:
            raise PermissionDenied("invalid_parent")
        actual_anchor = locked_target.version_anchor or locked_target
        if actual_anchor.pk != requested_anchor.pk:
            raise PermissionDenied("invalid_parent")
        locked_anchor = locked.get(actual_anchor.pk)
        if locked_anchor is None:
            raise PermissionDenied("invalid_parent")
        for locked_root in (locked_target, locked_anchor):
            if not decide(fresh_actor, "read", locked_root).allowed:
                raise PermissionDenied("The referenced collection is not accessible.")

        decision = decide(
            fresh_actor,
            "create",
            CollectionPropertyValue,
            parent=locked_anchor,
        )
        if not decision.allowed:
            raise PermissionDenied(decision.reason)

        if not decide(fresh_actor, "read", measurement_property).allowed:
            raise PermissionDenied("The referenced property is not accessible.")
        if not decide(fresh_actor, "read", unit).allowed:
            raise PermissionDenied("The referenced unit is not accessible.")
        _preflight_references(fresh_actor, sources, flyer_urls)

        existing = (
            visible_queryset(
                fresh_actor,
                CollectionPropertyValue.objects.filter(
                    collection=locked_anchor,
                    property=measurement_property,
                    unit=unit,
                    year=year,
                    is_derived=False,
                ),
            )
            .order_by("pk")
            .select_for_update(no_key=True)
            .first()
        )

        flyers_created = 0
        if existing is None:
            record = CollectionPropertyValue.objects.create(
                name=f"{locked_anchor.name} {measurement_property.name} {year}",
                owner=fresh_actor,
                publication_status="private",
                collection=locked_anchor,
                property=measurement_property,
                unit=unit,
                year=year,
                average=average,
                standard_deviation=standard_deviation,
                is_derived=False,
            )
            flyers_created = _apply_new_relations(
                fresh_actor, record, sources, flyer_urls
            )
            record_creation(fresh_actor, record)
            created = True
        else:
            if not decide(fresh_actor, "read", existing).allowed:
                raise PermissionDenied("The existing record is not accessible.")
            requested_pks, has_new_flyer = _requested_reference_pks(sources, flyer_urls)
            linked = set(existing.sources.values_list("pk", flat=True))
            if has_new_flyer or not requested_pks <= linked:
                with content_mutation(
                    fresh_actor, existing, action="edit"
                ) as locked_record:
                    flyers_created = _apply_new_relations(
                        fresh_actor, locked_record, sources, flyer_urls
                    )
                record = locked_record
            else:
                record = existing
            created = False

        record, submitted = _submit_if_requested(fresh_actor, record, submit_for_review)
        record.refresh_from_db()
        return EvidenceMutationResult(
            value=record,
            created=created,
            submitted=submitted,
            flyers_created=flyers_created,
        )


def create_or_reuse_aggregated_collection_property_value(
    actor,
    *,
    collections,
    measurement_property,
    unit,
    year,
    average,
    standard_deviation=None,
    sources=(),
    flyer_urls=(),
    submit_for_review=True,
):
    """Create or reuse an ``AggregatedCollectionPropertyValue`` under policy.

    The dedup key spans the collections M2M, which no constraint can cover;
    the actor row is locked first so same-actor requests serialize, and all
    parent rows are locked in ascending-pk order before the create decision.
    """
    parent_ids = sorted({collection.pk for collection in collections or []})
    if not parent_ids:
        raise ValidationError({"collections": ["At least one collection is required."]})

    with transaction.atomic():
        fresh_actor = _locked_actor(actor)

        locked_parents = list(
            Collection.objects.select_for_update(no_key=True)
            .filter(pk__in=parent_ids)
            .order_by("pk")
        )
        if len(locked_parents) != len(parent_ids):
            raise PermissionDenied("invalid_parent")

        decision = decide(
            fresh_actor,
            "create",
            AggregatedCollectionPropertyValue,
            parent=locked_parents,
        )
        if not decision.allowed:
            raise PermissionDenied(decision.reason)

        if not decide(fresh_actor, "read", measurement_property).allowed:
            raise PermissionDenied("The referenced property is not accessible.")
        if not decide(fresh_actor, "read", unit).allowed:
            raise PermissionDenied("The referenced unit is not accessible.")
        _preflight_references(fresh_actor, sources, flyer_urls)

        existing = None
        for candidate in (
            AggregatedCollectionPropertyValue.objects.filter(
                owner=fresh_actor,
                property=measurement_property,
                unit=unit,
                year=year,
            )
            .order_by("pk")
            .prefetch_related("collections")
        ):
            candidate_ids = sorted(c.pk for c in candidate.collections.all())
            if candidate_ids != parent_ids:
                continue
            locked_candidate = (
                AggregatedCollectionPropertyValue.objects.select_for_update(no_key=True)
                .filter(pk=candidate.pk)
                .first()
            )
            if locked_candidate is None:
                continue
            locked_ids = sorted(
                locked_candidate.collections.values_list("pk", flat=True)
            )
            if locked_candidate.owner_id != fresh_actor.pk or locked_ids != parent_ids:
                continue
            existing = locked_candidate
            break
        if existing is not None and not decide(fresh_actor, "read", existing).allowed:
            raise PermissionDenied("The existing record is not accessible.")

        flyers_created = 0
        if existing is None:
            record = AggregatedCollectionPropertyValue.objects.create(
                name=f"Aggregated {measurement_property.name} {year}",
                owner=fresh_actor,
                publication_status="private",
                property=measurement_property,
                unit=unit,
                year=year,
                average=average,
                standard_deviation=standard_deviation,
            )
            record.collections.set(locked_parents)
            flyers_created = _apply_new_relations(
                fresh_actor, record, sources, flyer_urls
            )
            record_creation(fresh_actor, record)
            created = True
        else:
            requested_pks, has_new_flyer = _requested_reference_pks(sources, flyer_urls)
            linked = set(existing.sources.values_list("pk", flat=True))
            if has_new_flyer or not requested_pks <= linked:
                with content_mutation(
                    fresh_actor, existing, action="edit"
                ) as locked_record:
                    flyers_created = _apply_new_relations(
                        fresh_actor, locked_record, sources, flyer_urls
                    )
                record = locked_record
            else:
                record = existing
            created = False

        record, submitted = _submit_if_requested(fresh_actor, record, submit_for_review)
        record.refresh_from_db()
        return EvidenceMutationResult(
            value=record,
            created=created,
            submitted=submitted,
            flyers_created=flyers_created,
        )
