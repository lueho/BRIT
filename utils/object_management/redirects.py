from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlparse

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from utils.object_management.models import ReviewAction
from utils.object_management.permissions import get_object_policy

RedirectHandler = Callable[[str | None, str], str]
HandlerSpec = str | RedirectHandler


class ReviewActionRedirectResolver:
    """Centralized redirect logic for review workflow actions."""

    default_action_handlers: dict[Any, HandlerSpec] = {
        ReviewAction.ACTION_WITHDRAWN: "resolve_withdraw_redirect",
    }

    def __init__(
        self,
        request,
        obj,
        action_handlers: Mapping[Any, HandlerSpec] | None = None,
    ) -> None:
        self.request = request
        self.obj = obj
        self.action_handlers: dict[Any, HandlerSpec] = dict(self.default_action_handlers)
        if action_handlers:
            self.action_handlers.update(action_handlers)

    def resolve_withdraw_redirect(self, next_url: str | None, default_url: str) -> str:
        """Determine redirect target after a withdraw action."""
        if not next_url:
            return default_url

        if self._should_redirect_owner_from_review(next_url):
            return self.obj.get_absolute_url()

        return next_url

    def resolve_default_redirect(self, next_url: str | None, default_url: str) -> str:
        """Fallback logic: prefer explicit next URL, otherwise use default."""
        return next_url or default_url

    def resolve_action_redirect(
        self, action: Any, next_url: str | None, default_url: str
    ) -> str:
        handler = self.action_handlers.get(action)
        if handler:
            return self._call_handler(handler, next_url, default_url)
        return self.resolve_default_redirect(next_url, default_url)

    def _call_handler(
        self, handler: HandlerSpec, next_url: str | None, default_url: str
    ) -> str:
        if isinstance(handler, str):
            handler_callable = getattr(self, handler, None)
            if handler_callable is None:
                raise AttributeError(
                    f"ReviewActionRedirectResolver has no handler named '{handler}'"
                )
        else:
            handler_callable = handler

        return handler_callable(next_url, default_url)

    def _should_redirect_owner_from_review(self, next_url: str) -> bool:
        """Return True when owner should avoid landing on review detail."""
        try:
            policy = get_object_policy(self.request.user, self.obj, request=self.request)
            if not (
                policy.get("is_owner")
                and not (policy.get("is_in_review") or policy.get("is_declined"))
            ):
                return False

            review_path = self._get_review_detail_path()
            return urlparse(next_url).path == review_path
        except Exception:
            return False

    def _get_review_detail_path(self) -> str:
        return reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(
                    self.obj.__class__
                ).id,
                "object_id": self.obj.pk,
            },
        )
