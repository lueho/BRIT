"""Helpers for external review-bot integrations.

This module provides:
- Serializers for reviewable objects (domain data only)
- Validation of the structured draft response contract

BRIT intentionally does not call external LLM providers directly.
Context assembly for LLM consumption is the responsibility of the MCP layer.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.contrib.contenttypes.models import ContentType

from .models import ReviewAction

logger = logging.getLogger(__name__)


class ReviewResponseError(Exception):
    """Raised when the review-bot response cannot be parsed or validated."""


def build_review_context(
    obj: Any,
    *,
    include_history: bool = True,
    history_limit: int = 15,
) -> dict[str, Any]:
    """Serialize all authoritative domain data for a reviewable object."""
    content_type = ContentType.objects.get_for_model(obj.__class__)
    context: dict[str, Any] = {
        "object": {
            "content_type_id": content_type.id,
            "object_id": obj.pk,
            "app_label": obj._meta.app_label,
            "model": obj._meta.model_name,
            "verbose_name": str(obj._meta.verbose_name),
            "display_name": str(obj),
            "publication_status": getattr(obj, "publication_status", None),
            "owner_id": getattr(obj, "owner_id", None),
            "submitted_at": _serialize_value(getattr(obj, "submitted_at", None)),
            "approved_at": _serialize_value(getattr(obj, "approved_at", None)),
        },
        "fields": _serialize_model_fields(obj),
        "related_display": _serialize_related_display(obj),
        "sources": _serialize_m2m_sources(obj),
    }

    # CPV-specific enrichments
    if _is_collection_property_value(obj):
        context["parent_collection"] = _serialize_parent_collection(obj)
        if not getattr(obj, "is_derived", False):
            context["value_timeline"] = _serialize_cpv_timeline(obj)

    # Collection-specific enrichments
    if _is_collection(obj):
        context["flyers"] = _serialize_collection_flyers(obj)

    if include_history:
        history = (
            ReviewAction.for_object(obj)
            .select_related("user")
            .order_by("-created_at", "-id")[:history_limit]
        )
        context["review_history"] = [
            {
                "action": action.action,
                "comment": action.comment,
                "user_id": action.user_id,
                "username": action.user.username,
                "created_at": _serialize_value(action.created_at),
            }
            for action in history
        ]

    return context


def validate_draft_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize the LLM draft payload contract."""
    required_keys = {
        "summary",
        "decision_hint",
        "confidence",
        "risk_flags",
        "comment_markdown",
        "evidence",
    }
    missing = required_keys.difference(payload.keys())
    if missing:
        missing_keys = ", ".join(sorted(missing))
        raise ReviewResponseError(
            f"Review-bot response missing required keys: {missing_keys}."
        )

    decision_hint = str(payload["decision_hint"]).strip().lower()
    allowed_decisions = {"approve", "reject", "needs_human_review"}
    if decision_hint not in allowed_decisions:
        raise ReviewResponseError(
            "decision_hint must be one of: approve, reject, needs_human_review."
        )

    try:
        confidence = float(payload["confidence"])
    except (TypeError, ValueError) as exc:
        raise ReviewResponseError("confidence must be numeric.") from exc

    if confidence < 0.0 or confidence > 1.0:
        raise ReviewResponseError("confidence must be between 0 and 1.")

    risk_flags = payload["risk_flags"]
    if not isinstance(risk_flags, list):
        raise ReviewResponseError("risk_flags must be a list.")

    evidence = payload["evidence"]
    if not isinstance(evidence, list):
        raise ReviewResponseError("evidence must be a list.")

    return {
        "summary": str(payload["summary"]).strip(),
        "decision_hint": decision_hint,
        "confidence": confidence,
        "risk_flags": [str(flag).strip() for flag in risk_flags if str(flag).strip()],
        "comment_markdown": str(payload["comment_markdown"]).strip(),
        "evidence": evidence,
    }


def _is_collection_property_value(obj: Any) -> bool:
    """Check whether *obj* is a CollectionPropertyValue instance."""
    return (
        obj._meta.app_label in {"soilcom", "waste_collection"}
        and obj._meta.model_name == "collectionpropertyvalue"
    )


def _is_collection(obj: Any) -> bool:
    """Check whether *obj* is a Collection instance."""
    return (
        obj._meta.app_label in {"soilcom", "waste_collection"}
        and obj._meta.model_name == "collection"
    )


def _serialize_m2m_sources(obj: Any) -> list[dict[str, Any]]:
    """Serialize the ``sources`` M2M relation into JSON-safe dicts."""
    if not hasattr(obj, "sources"):
        return []
    sources = obj.sources.select_related().order_by("pk")
    return [
        {
            "id": src.pk,
            "type": getattr(src, "type", None),
            "title": getattr(src, "title", ""),
            "abbreviation": getattr(src, "abbreviation", ""),
            "url": getattr(src, "url", None),
            "url_valid": getattr(src, "url_valid", None),
            "url_checked": _serialize_value(getattr(src, "url_checked", None)),
            "url_valid_is_advisory": True,
            "doi": getattr(src, "doi", None),
            "abstract": getattr(src, "abstract", None),
            "year": getattr(src, "year", None),
        }
        for src in sources
    ]


def _serialize_related_display(obj: Any) -> dict[str, str | None]:
    """Resolve FK ids to human-readable display strings."""
    display: dict[str, str | None] = {}
    for field in obj._meta.fields:
        if not field.is_relation:
            continue
        related_obj = getattr(obj, field.name, None)
        if related_obj is not None:
            display[field.name] = str(related_obj)
        else:
            display[field.name] = None
    return display


def _serialize_cpv_timeline(obj: Any) -> list[dict[str, Any]]:
    """Return historical values for the same property on the same collection chain.

    Helps agents assess plausibility by comparing a value against its trend
    across years. Only called for non-derived CollectionPropertyValues.
    """
    try:
        collection = obj.collection
        chain_ids = collection.version_chain_ids
        model_class = obj.__class__
        siblings = (
            model_class.objects.filter(
                collection_id__in=chain_ids,
                property_id=obj.property_id,
                is_derived=False,
            )
            .exclude(pk=obj.pk)
            .select_related("unit")
            .order_by("year", "pk")
        )
        return [
            {
                "id": sibling.pk,
                "year": sibling.year,
                "average": sibling.average,
                "standard_deviation": sibling.standard_deviation,
                "unit": str(sibling.unit) if sibling.unit else None,
                "publication_status": getattr(sibling, "publication_status", None),
            }
            for sibling in siblings
        ]
    except Exception:
        logger.debug("Could not build CPV timeline for %s", obj.pk, exc_info=True)
        return []


def _serialize_parent_collection(obj: Any) -> dict[str, Any]:
    """Serialize the parent collection of a CPV with its sources and flyers."""
    try:
        collection = obj.collection
        return {
            "id": collection.pk,
            "name": str(collection),
            "sources": _serialize_m2m_sources(collection),
            "flyers": _serialize_collection_flyers(collection),
        }
    except Exception:
        logger.debug(
            "Could not serialize parent collection for CPV %s",
            obj.pk,
            exc_info=True,
        )
        return {}


def _serialize_collection_flyers(obj: Any) -> list[dict[str, Any]]:
    """Serialize the ``flyers`` M2M on a Collection."""
    if not hasattr(obj, "flyers"):
        return []
    return [
        {
            "id": flyer.pk,
            "url": getattr(flyer, "url", None),
            "url_valid": getattr(flyer, "url_valid", None),
            "url_checked": _serialize_value(getattr(flyer, "url_checked", None)),
            "url_valid_is_advisory": True,
            "title": getattr(flyer, "title", ""),
        }
        for flyer in obj.flyers.order_by("pk")
    ]


def _serialize_model_fields(obj: Any) -> dict[str, Any]:
    """Serialize concrete model fields into JSON-compatible values."""
    serialized: dict[str, Any] = {}
    for field in obj._meta.fields:
        if field.is_relation:
            serialized[field.name] = getattr(obj, f"{field.name}_id", None)
            continue
        serialized[field.name] = _serialize_value(getattr(obj, field.name, None))
    return serialized


def _serialize_value(value: Any) -> Any:
    """Convert Python values to JSON-serializable primitives."""
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)
