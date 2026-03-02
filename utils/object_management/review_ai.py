"""Helpers for external review-bot integrations.

This module provides:
- Context builders for reviewable objects
- Validation of the structured draft response contract

BRIT intentionally does not call external LLM providers directly.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.contrib.contenttypes.models import ContentType

from .models import ReviewAction


class LLMReviewResponseError(Exception):
    """Raised when the LLM response cannot be parsed or validated."""


def build_llm_review_context(
    obj: Any,
    *,
    include_history: bool = True,
    history_limit: int = 15,
) -> dict[str, Any]:
    """Build a structured context payload for LLM review drafting."""
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
    }

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
        raise LLMReviewResponseError(
            f"LLM response missing required keys: {missing_keys}."
        )

    decision_hint = str(payload["decision_hint"]).strip().lower()
    allowed_decisions = {"approve", "reject", "needs_human_review"}
    if decision_hint not in allowed_decisions:
        raise LLMReviewResponseError(
            "decision_hint must be one of: approve, reject, needs_human_review."
        )

    try:
        confidence = float(payload["confidence"])
    except (TypeError, ValueError) as exc:
        raise LLMReviewResponseError("confidence must be numeric.") from exc

    if confidence < 0.0 or confidence > 1.0:
        raise LLMReviewResponseError("confidence must be between 0 and 1.")

    risk_flags = payload["risk_flags"]
    if not isinstance(risk_flags, list):
        raise LLMReviewResponseError("risk_flags must be a list.")

    evidence = payload["evidence"]
    if not isinstance(evidence, list):
        raise LLMReviewResponseError("evidence must be a list.")

    return {
        "summary": str(payload["summary"]).strip(),
        "decision_hint": decision_hint,
        "confidence": confidence,
        "risk_flags": [str(flag).strip() for flag in risk_flags if str(flag).strip()],
        "comment_markdown": str(payload["comment_markdown"]).strip(),
        "evidence": evidence,
    }


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
