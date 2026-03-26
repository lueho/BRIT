"""API endpoints for review workflow actions and review context access."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ReviewAction
from .permissions import UserCreatedObjectPermission
from .review_context import build_review_context
from .views import ReviewDashboardView


class ReviewQueueAPIView(APIView):
    """Return review items visible to the current user in a JSON format."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """List review queue items using existing dashboard logic."""
        django_request = getattr(request, "_request", request)
        dashboard_view = ReviewDashboardView()
        dashboard_view.request = django_request
        dashboard_view.paginate_by = 50
        dashboard_view._available_models_cache = None

        items = dashboard_view.collect_review_items()
        payload = [self._serialize_item(request.user, item) for item in items]

        return Response({"count": len(payload), "results": payload})

    def _serialize_item(self, user, item):
        """Serialize one review queue object into API-safe primitives."""
        content_type = ContentType.objects.get_for_model(item.__class__)
        review_detail_url = reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": content_type.id,
                "object_id": item.pk,
            },
        )

        my_last_comment = (
            ReviewAction.objects.filter(
                content_type=content_type,
                object_id=item.pk,
                action=ReviewAction.ACTION_COMMENT,
                user=user,
            )
            .order_by("-created_at")
            .values_list("created_at", flat=True)
            .first()
        )

        return {
            "content_type_id": content_type.id,
            "object_id": item.pk,
            "app_label": item._meta.app_label,
            "model": item._meta.model_name,
            "verbose_name": str(item._meta.verbose_name),
            "name": str(item),
            "owner_id": getattr(item, "owner_id", None),
            "publication_status": getattr(item, "publication_status", None),
            "submitted_at": getattr(item, "submitted_at", None),
            "lastmodified_at": getattr(item, "lastmodified_at", None),
            "my_last_comment_at": my_last_comment,
            "review_detail_url": review_detail_url,
        }


class AddReviewCommentAPIView(APIView):
    """Create a review comment entry for an object in the workflow."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, content_type_id: int, object_id: int):
        """Create a ``ReviewAction`` comment after permission checks."""
        obj = _get_review_object(content_type_id=content_type_id, object_id=object_id)
        permission = UserCreatedObjectPermission()
        django_request = getattr(request, "_request", request)
        if not permission.has_comment_permission(django_request, obj):
            return Response(
                {"detail": "You do not have permission to comment on this object."},
                status=status.HTTP_403_FORBIDDEN,
            )

        comment = str(
            request.data.get("comment") or request.data.get("message") or ""
        ).strip()
        if not comment:
            return Response(
                {"detail": "comment is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        action = ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(obj.__class__),
            object_id=obj.pk,
            action=ReviewAction.ACTION_COMMENT,
            comment=comment,
            user=request.user,
        )

        return Response(
            {
                "id": action.id,
                "action": action.action,
                "comment": action.comment,
                "user_id": action.user_id,
                "created_at": action.created_at,
            },
            status=status.HTTP_201_CREATED,
        )


class ReviewContextAPIView(APIView):
    """Return review context for external consumers outside BRIT."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, content_type_id: int, object_id: int):
        """Build a context payload for external review processing."""
        obj = _get_review_object(content_type_id=content_type_id, object_id=object_id)
        permission = UserCreatedObjectPermission()
        django_request = getattr(request, "_request", request)

        if not permission.has_comment_permission(django_request, obj):
            return Response(
                {
                    "detail": (
                        "You do not have permission to access review context "
                        "for this object."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        include_history = _to_bool(request.query_params.get("include_history", True))

        raw_history_limit = request.query_params.get("history_limit", 15)
        try:
            history_limit = int(raw_history_limit)
        except (TypeError, ValueError):
            return Response(
                {"detail": "history_limit must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        context = build_review_context(
            obj,
            include_history=include_history,
            history_limit=max(1, min(history_limit, 50)),
        )
        collection_update = _serialize_collection_update_context(request.user, obj)
        if collection_update is not None:
            context["collection_update"] = collection_update

        return Response(
            {
                "content_type_id": content_type_id,
                "object_id": object_id,
                "context": context,
            },
            status=status.HTTP_200_OK,
        )


def _get_review_object(*, content_type_id: int, object_id: int):
    """Resolve and return the review object addressed by content type and id."""
    content_type = get_object_or_404(ContentType, pk=content_type_id)
    model_class = content_type.model_class()
    if model_class is None:
        raise Http404("No model is registered for this content type.")
    return get_object_or_404(model_class, pk=object_id)


def _serialize_collection_update_context(user, obj):
    """Return owner-gated update hints for collection review items."""
    if not (
        obj._meta.app_label in {"soilcom", "waste_collection"}
        and obj._meta.model_name == "collection"
    ):
        return None

    is_owner = bool(
        user
        and getattr(user, "is_authenticated", False)
        and getattr(obj, "owner_id", None) == getattr(user, "id", None)
    )
    if not is_owner:
        return {
            "available": False,
            "detail": "Only the collection owner may use the programmatic update endpoint.",
        }

    waste_category = getattr(obj, "effective_waste_category", None)
    valid_from = getattr(obj, "valid_from", None)
    return {
        "available": True,
        "update_url": reverse("api-waste-collection-update", kwargs={"pk": obj.pk}),
        "expected_identity": {
            "expected_catchment": str(obj.catchment),
            "expected_catchment_id": getattr(obj.catchment, "pk", None),
            "expected_waste_category": str(waste_category) if waste_category else "",
            "expected_waste_category_id": getattr(waste_category, "pk", None),
            "expected_collection_system": str(obj.collection_system),
            "expected_collection_system_id": getattr(obj.collection_system, "pk", None),
            "expected_publication_status": getattr(obj, "publication_status", None),
            "expected_valid_from": valid_from.isoformat() if valid_from else None,
        },
        "mutable_fields": [
            "collector",
            "frequency",
            "fee_system",
            "sorting_method",
            "allowed_materials",
            "forbidden_materials",
            "sources",
            "flyer_urls",
            "established",
            "connection_type",
            "min_bin_size",
            "required_bin_capacity",
            "required_bin_capacity_reference",
            "comments",
            "description",
        ],
    }


def _to_bool(value):
    """Convert common request payload values to a boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off", ""}
    return bool(value)
