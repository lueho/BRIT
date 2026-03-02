"""API endpoints for review workflow actions and external bot context access."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ReviewAction
from .permissions import UserCreatedObjectPermission
from .review_ai import build_llm_review_context
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
        payload = [self._serialize_item(item) for item in items]

        return Response({"count": len(payload), "results": payload})

    def _serialize_item(self, item):
        """Serialize one review queue object into API-safe primitives."""
        content_type = ContentType.objects.get_for_model(item.__class__)
        review_detail_url = reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": content_type.id,
                "object_id": item.pk,
            },
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
    """Return review context for external bots to process outside BRIT."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, content_type_id: int, object_id: int):
        """Build context payload for external review automation."""
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

        context = build_llm_review_context(
            obj,
            include_history=include_history,
            history_limit=max(1, min(history_limit, 50)),
        )

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
    return get_object_or_404(model_class, pk=object_id)


def _to_bool(value):
    """Convert common request payload values to a boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off", ""}
    return bool(value)
