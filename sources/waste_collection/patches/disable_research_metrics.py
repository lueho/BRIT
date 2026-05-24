"""Disable expensive metric loading on the research list serializer."""

from __future__ import annotations

from types import MethodType
from typing import Any, Callable

from sources.waste_collection import serializers as wc_serializers


def _make_empty_method(instance: Any) -> Callable[[Any, Any], list[Any]]:
    def _empty_method(_self: Any, user: Any = None) -> list[Any]:  # noqa: ANN401
        return []

    return MethodType(_empty_method, instance)


def _temporarily_disable_metric_queries(instance: Any):
    attr_names = (
        "collectionpropertyvalues_for_display",
        "aggregatedcollectionpropertyvalues_for_display",
    )
    originals = {}
    for name in attr_names:
        originals[name] = (
            name in instance.__dict__,
            instance.__dict__.get(name),
        )
        instance.__dict__[name] = _make_empty_method(instance)
    return originals


def _restore_metric_queries(instance: Any, originals: dict[str, tuple[bool, Any]]):
    for name, (had_instance_attr, value) in originals.items():
        if had_instance_attr:
            instance.__dict__[name] = value
        else:
            instance.__dict__.pop(name, None)


def _patch_collection_research_serializer() -> None:
    if getattr(wc_serializers.CollectionResearchSerializer, "_metrics_patch_applied", False):
        return

    original_to_representation = wc_serializers.CollectionResearchSerializer.to_representation

    def patched_to_representation(self, instance):  # type: ignore[override]
        originals = _temporarily_disable_metric_queries(instance)
        try:
            return original_to_representation(self, instance)
        finally:
            _restore_metric_queries(instance, originals)

    wc_serializers.CollectionResearchSerializer.include_collection_metrics = False
    wc_serializers.CollectionResearchSerializer.to_representation = patched_to_representation  # type: ignore[assignment]
    wc_serializers.CollectionResearchSerializer._metrics_patch_applied = True  # type: ignore[attr-defined]


_patch_collection_research_serializer()
