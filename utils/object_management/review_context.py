"""Helpers for review context serialization and draft validation.

This module provides:
- Serializers for reviewable objects (domain data only)
- Validation of the structured draft response contract

Context assembly beyond BRIT is the responsibility of the caller.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from .models import ReviewAction
from .review_hooks import get_review_context_enrichments

logger = logging.getLogger(__name__)


class ReviewResponseError(Exception):
    """Raised when a review response cannot be parsed or validated."""


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
        "review_feedback": _serialize_review_feedback(
            obj,
            history_limit=history_limit,
        ),
    }

    context.update(get_review_context_enrichments(obj))

    if include_history:
        history = (
            ReviewAction.for_object(obj)
            .select_related("user")
            .order_by("-created_at", "-id")[:history_limit]
        )
        context["review_history"] = [
            _serialize_review_action(action) for action in history
        ]

    return context


def _serialize_review_feedback(obj: Any, *, history_limit: int) -> dict[str, Any]:
    latest_submission = getattr(obj, "latest_submission_action", None)
    latest_feedback = getattr(obj, "latest_review_feedback_action", None)

    feedback_actions: list[dict[str, Any]] = []
    if latest_submission is not None and getattr(obj, "owner_id", None):
        actions = (
            ReviewAction.for_object(obj)
            .select_related("user")
            .exclude(user_id=obj.owner_id)
            .exclude(action=ReviewAction.ACTION_SUBMITTED)
            .filter(
                Q(created_at__gt=latest_submission.created_at)
                | Q(
                    created_at=latest_submission.created_at,
                    id__gt=latest_submission.id,
                )
            )
            .order_by("-created_at", "-id")[:history_limit]
        )
        feedback_actions = [_serialize_review_action(action) for action in actions]

    return {
        "has_feedback": latest_feedback is not None,
        "latest_submission": _serialize_review_action(latest_submission),
        "latest_feedback_action": _serialize_review_action(latest_feedback),
        "feedback_actions_since_submission": feedback_actions,
    }


def _serialize_review_action(action: ReviewAction | None) -> dict[str, Any] | None:
    if action is None:
        return None

    return {
        "action": action.action,
        "comment": action.comment,
        "user_id": action.user_id,
        "username": action.user.username,
        "created_at": _serialize_value(action.created_at),
    }


def validate_draft_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize the draft payload contract."""
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
            f"Review response missing required keys: {missing_keys}."
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
