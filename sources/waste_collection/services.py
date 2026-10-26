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
    record_creation,
    validate_references,
)

from .models import WasteFlyer


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
