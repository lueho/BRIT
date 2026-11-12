"""Measurement precedence within an already-authorized CPV queryset."""

from django.db.models import Exists, IntegerField, OuterRef, Q, Value
from django.db.models.functions import Coalesce

from utils.object_management.policy import visible_queryset


def visible_measurement_queryset(user, queryset):
    """Authorize first, then apply measurement precedence without broadening."""
    return preferred_measurement_queryset(visible_queryset(user, queryset))


def preferred_measurement_queryset(queryset):
    """Keep visible manual evidence ahead of generated copies of the same key.

    Authorization must precede this narrowing step: an unreadable manual row
    must never suppress a readable projection. Keep all visible manual rows.
    """
    normalized = queryset.annotate(
        _measurement_year=Coalesce("year", Value(-1), output_field=IntegerField()),
    )
    manual = normalized.filter(
        is_derived=False,
        collection_id=OuterRef("collection_id"),
        property_id=OuterRef("property_id"),
        _measurement_year=OuterRef("_measurement_year"),
        unit_id=OuterRef("unit_id"),
    )
    return normalized.annotate(_has_visible_manual=Exists(manual)).filter(
        Q(is_derived=False) | Q(is_derived=True, _has_visible_manual=False)
    )
