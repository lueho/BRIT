from __future__ import annotations

import logging
from importlib import import_module

from django.urls import reverse

from utils.object_management.review_context import (
    _serialize_m2m_sources,
    _serialize_value,
)
from utils.object_management.review_hooks import (
    register_breadcrumb_module,
    register_review_context_enricher,
    register_review_search_fields,
    register_review_update_context,
)

logger = logging.getLogger(__name__)


def register_review_hooks() -> None:
    register_breadcrumb_module(
        "waste_collection",
        label="Waste Collection",
        url_name="wastecollection-explorer",
        parent_label="Sources",
        parent_url_name="sources-explorer",
    )
    register_review_context_enricher(
        "waste_collection.collection",
        enrich_collection_review_context,
    )
    register_review_context_enricher(
        "waste_collection.collectionpropertyvalue",
        enrich_collection_property_value_review_context,
    )
    register_review_search_fields(
        "waste_collection.collection",
        ["catchment__name", "waste_category__name", "collection_system__name"],
    )
    register_review_update_context(
        "waste_collection.collection",
        serialize_collection_update_context,
        context_key="collection_update",
    )


def is_collection(obj: object) -> bool:
    return (
        obj._meta.app_label == "waste_collection"
        and obj._meta.model_name == "collection"
    )


def is_collection_property_value(obj: object) -> bool:
    return (
        obj._meta.app_label == "waste_collection"
        and obj._meta.model_name == "collectionpropertyvalue"
    )


def enrich_collection_review_context(obj: object) -> dict[str, object]:
    return {
        "flyers": _serialize_collection_flyers(obj),
        "frequency_display": _serialize_collection_frequency(obj),
    }


def enrich_collection_property_value_review_context(obj: object) -> dict[str, object]:
    context: dict[str, object] = {
        "parent_collection": _serialize_parent_collection(obj),
    }
    if not obj.is_derived:
        context["value_timeline"] = _serialize_cpv_timeline(obj)
    return context


def serialize_collection_update_context(
    user: object,
    obj: object,
) -> dict[str, object] | None:
    if not is_collection(obj):
        return None

    is_owner = bool(user and user.is_authenticated and obj.owner_id == user.id)
    if not is_owner:
        return {
            "available": False,
            "detail": (
                "Only the collection owner may use the programmatic update endpoint."
            ),
        }

    waste_category = obj.effective_waste_category
    valid_from = obj.valid_from
    return {
        "available": True,
        "update_url": reverse("api-waste-collection-update", kwargs={"pk": obj.pk}),
        "expected_identity": {
            "expected_catchment": str(obj.catchment),
            "expected_catchment_id": obj.catchment.pk if obj.catchment else None,
            "expected_waste_category": str(waste_category) if waste_category else "",
            "expected_waste_category_id": waste_category.pk if waste_category else None,
            "expected_collection_system": str(obj.collection_system),
            "expected_collection_system_id": (
                obj.collection_system.pk if obj.collection_system else None
            ),
            "expected_publication_status": obj.publication_status,
            "expected_valid_from": valid_from.isoformat() if valid_from else None,
        },
        "mutable_fields": [
            "collector",
            "frequency",
            "fee_system",
            "bin_configuration",
            "allowed_materials",
            "forbidden_materials",
            "sources",
            "flyer_urls",
            "established",
            "participation_policy",
            "min_bin_size",
            "required_bin_capacity",
            "required_bin_capacity_reference",
            "comments",
            "description",
        ],
    }


def _serialize_cpv_timeline(obj: object) -> list[dict[str, object]]:
    try:
        collection = obj.collection
        siblings = (
            obj.__class__.objects.filter(
                collection_id__in=collection.version_chain_ids,
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
                "publication_status": sibling.publication_status,
            }
            for sibling in siblings
        ]
    except Exception:
        logger.debug("Could not build CPV timeline for %s", obj.pk, exc_info=True)
        return []


def _serialize_parent_collection(obj: object) -> dict[str, object]:
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


def _serialize_collection_flyers(obj: object) -> list[dict[str, object]]:
    return [
        {
            "id": flyer.pk,
            "url": flyer.url,
            "url_valid": flyer.url_valid,
            "url_checked": _serialize_value(flyer.url_checked),
            "url_valid_is_advisory": True,
            "title": flyer.title,
        }
        for flyer in obj.flyers.order_by("pk")
    ]


def _serialize_collection_frequency(obj: object) -> dict[str, object] | None:
    frequency = obj.frequency
    if frequency is None:
        return None
    try:
        schedule_service = _get_collection_frequency_schedule_service()
        if schedule_service is None:
            raise LookupError("Collection frequency schedule service is unavailable")
        rows = schedule_service.rows_from_frequency(frequency)
        display_rows = schedule_service.display_rows(frequency)
        is_year_round = (
            len(display_rows) == 1 and display_rows[0]["segment"] == "All year"
        )
        return {
            "id": frequency.pk,
            "canonical_label": frequency.name,
            "type": frequency.type,
            "schedule_summary": schedule_service.summary(rows),
            "rows": display_rows,
            "is_year_round": is_year_round,
            "summary": display_rows[0]["standard"] if is_year_round else None,
            "options": display_rows[0]["options"] if is_year_round else None,
        }
    except Exception:
        logger.debug(
            "Could not serialize collection frequency for %s",
            obj.pk,
            exc_info=True,
        )
        return {
            "id": frequency.pk,
            "canonical_label": frequency.name,
            "type": frequency.type,
            "schedule_summary": None,
            "rows": [],
            "is_year_round": False,
            "summary": None,
            "options": [],
        }


def _get_collection_frequency_schedule_service():
    try:
        module = import_module("sources.waste_collection.frequency_service")
    except (ImportError, ModuleNotFoundError):
        return None
    try:
        return module.CollectionFrequencyScheduleService
    except AttributeError:
        return None
