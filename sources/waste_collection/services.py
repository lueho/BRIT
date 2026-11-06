"""Policy-safe waste-collection reference helpers.

Flyer lookup and creation delegate to shared authorization and audit services.
"""

from urllib.parse import urlparse

from django.core.exceptions import PermissionDenied
from django.db import transaction

from utils.object_management.policy import is_active_actor
from utils.object_management.services import (
    _fresh_actor,
    authorize_create,
    content_mutation,
    record_creation,
    validate_references,
)

from .frequency_service import COUNT_FIELDS
from .models import CollectionCountOptions, CollectionSeason, WasteFlyer


def flyer_title(url):
    """Return a short title derived from the URL hostname (max 255 chars)."""
    try:
        hostname = urlparse(url).hostname or url
    except Exception:
        hostname = url
    return hostname[:255]


def resolve_flyer(actor, url):
    """Return ``(flyer, created)`` for ``url`` as ``actor``.

    Reuse follows the existing URL manager's selection semantics. Existing
    flyers require their own read access; new ones require create capability
    before persistence. Recheck the resolved row and fresh actor afterwards,
    so a lost race or revoked permission rolls back the compound operation.
    """
    with transaction.atomic():
        actor = _fresh_actor(actor)
        if not is_active_actor(actor):
            raise PermissionDenied("inactive_actor")
        existing = WasteFlyer.objects.filter(url=url).order_by("id").first()
        if existing is not None:
            validate_references(actor, existing)
            return existing, False
        actor = authorize_create(actor, WasteFlyer)
        flyer, created = WasteFlyer.objects.get_or_create_by_url(
            url,
            defaults={
                "owner": actor,
                "title": flyer_title(url),
                "publication_status": "private",
            },
        )
        actor = _fresh_actor(actor)
        if not is_active_actor(actor):
            raise PermissionDenied("inactive_actor")
        if created:
            actor = authorize_create(actor, WasteFlyer)
            record_creation(actor, flyer)
            return flyer, True
        validate_references(actor, flyer)
        return flyer, False


def resolve_frequency_season(actor, row):
    """Return the ``CollectionSeason`` matching *row* as *actor*.

    Reuse follows the season's unique ``(distribution, first_timestep,
    last_timestep)`` key. An existing match must be a readable reference —
    a hidden or foreign-private match fails closed rather than being
    silently reused. When nothing matches, creating the season requires
    the actor's own ``add_collectionseason`` capability; the new row is
    actor-owned/private and audit-recorded. The create and its audit are
    one atomic unit, so a failed creation event persists nothing.
    """
    with transaction.atomic():
        actor = _fresh_actor(actor)
        if not is_active_actor(actor):
            raise PermissionDenied("inactive_actor")
        validate_references(
            actor,
            (row["distribution"], row["first_timestep"], row["last_timestep"]),
        )
        try:
            season = CollectionSeason.objects.get(
                distribution=row["distribution"],
                first_timestep=row["first_timestep"],
                last_timestep=row["last_timestep"],
            )
        except CollectionSeason.DoesNotExist:
            actor = authorize_create(actor, CollectionSeason)
            # A concurrent request may insert the same key after the miss
            # above; get_or_create reuses its row instead of failing.
            season, created = CollectionSeason.objects.get_or_create(
                distribution=row["distribution"],
                first_timestep=row["first_timestep"],
                last_timestep=row["last_timestep"],
                defaults={"owner": actor, "publication_status": "private"},
            )
            if created:
                record_creation(actor, season)
                return season, True
        validate_references(actor, season)
        return season, False


def save_frequency_schedule(actor, frequency, rows):
    """Persist the season/count-option schedule for *frequency* as *actor*.

    Replaces the generic M2M formset save: each row resolves its season
    through ``resolve_frequency_season`` (governed reuse-or-create), then
    the matching ``CollectionCountOptions`` row is created, updated, or
    deleted through its own governed boundary. Existing options that are
    no longer referenced are removed through their own delete
    authorization; unrelated seasons elsewhere are never touched.
    """
    with transaction.atomic():
        actor = _fresh_actor(actor)
        if not is_active_actor(actor):
            raise PermissionDenied("inactive_actor")

        seen_season_ids = set()
        seasons = []
        for row in rows:
            season, _ = resolve_frequency_season(actor, row)
            seen_season_ids.add(season.pk)
            seasons.append(season)
            try:
                options = CollectionCountOptions.objects.get(
                    frequency=frequency, season=season
                )
            except CollectionCountOptions.DoesNotExist:
                actor = authorize_create(actor, CollectionCountOptions)
                validate_references(actor, (frequency, season))
                options = CollectionCountOptions.objects.create(
                    owner=actor,
                    frequency=frequency,
                    season=season,
                    standard=row["standard"],
                    option_1=row["option_1"],
                    option_2=row["option_2"],
                    option_3=row["option_3"],
                    publication_status="private",
                )
                record_creation(actor, options)
                continue
            changed = any(
                getattr(options, field) != row[field] for field in COUNT_FIELDS
            )
            if changed:
                with content_mutation(actor, options) as locked:
                    for field in COUNT_FIELDS:
                        setattr(locked, field, row[field])
                    locked.save(update_fields=list(COUNT_FIELDS))
            else:
                validate_references(actor, (options, season))

        for options in (
            CollectionCountOptions.objects.filter(frequency=frequency)
            .exclude(season_id__in=seen_season_ids)
            .order_by("pk")
        ):
            with content_mutation(actor, options, action="delete") as locked:
                locked.delete()
        return seasons
