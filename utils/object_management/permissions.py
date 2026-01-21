import logging
from types import SimpleNamespace

from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q
from rest_framework import exceptions as drf_exceptions
from rest_framework import permissions

logger = logging.getLogger(__name__)


class GlobalObjectPermission(permissions.BasePermission):
    """
    Custom permission to allow read-only access to anyone,
    and write access only to staff users.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user and request.user.is_authenticated and request.user.is_staff


class UserCreatedObjectPermission(permissions.BasePermission):
    """
    Generic permission class for user-created objects.
    Handles ownership, publication_status, and moderation permissions dynamically.

    Supports the review workflow with methods for checking if a user can:
    - submit_for_review: Only owners can submit their private objects for review
    - withdraw_from_review: Only owners can withdraw their objects from review
    - approve: Only moderators can approve objects in review
    - reject: Only moderators can reject objects in review
    """

    def has_permission(self, request, view):
        # Allow any user to list or retrieve published objects
        if getattr(view, "action", None) in ["list", "retrieve"]:
            return True

        # For create action, check proper model permissions
        if getattr(view, "action", None) == "create":
            # User must be authenticated
            if not (request.user and request.user.is_authenticated):
                return False

            # Staff users can always create objects
            if request.user.is_staff:
                return True

            # Get model from viewset's queryset without requiring a DRF Request
            model = None
            queryset = getattr(view, "queryset", None)
            if queryset is not None:
                model = getattr(queryset, "model", None)

            if model is None:
                try:
                    model = view.get_queryset().model
                except Exception:
                    model = None

            if model is None:
                # If we can't determine the model permission, default to False for security
                return False

            app_label = model._meta.app_label
            model_name = model._meta.model_name

            # Check if user has 'add' permission for this model
            return request.user.has_perm(f"{app_label}.add_{model_name}")

        # For other actions, ensure the user is authenticated
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Handle safe methods
        if request.method in permissions.SAFE_METHODS:
            return self._check_safe_permissions(request, obj)

        # Handle write methods
        user = request.user

        if obj.owner == user:
            from .models import UserCreatedObject

            # Owners cannot modify objects that are already published or archived
            if getattr(obj, "publication_status", None) in (
                UserCreatedObject.STATUS_PUBLISHED,
                getattr(UserCreatedObject, "STATUS_ARCHIVED", "archived"),
            ):
                return False

            # Safely access request data (can raise UnsupportedMediaType for empty multipart)
            try:
                payload = request.data
            except drf_exceptions.UnsupportedMediaType:
                payload = {}

            # Four eyes principle: moderators cannot publish their own objects
            if (
                "publication_status" in payload
                and payload["publication_status"] == UserCreatedObject.STATUS_PUBLISHED
                and self._is_moderator(user, obj)
            ):
                return False

            # If attempting to change publication_status, require moderator rights
            if "publication_status" in payload and not self._is_moderator(user, obj):
                return False

            return True  # Owners can modify other fields

        # Check if user is a moderator
        if self._is_moderator(user, obj):
            # Moderators cannot modify 'private' objects unless they are the owner
            if (
                getattr(obj, "publication_status", None) == "private"
                and obj.owner != user
            ):
                return False
            # Moderators may only change 'publication_status'—nothing else
            if request.method in ("PATCH", "PUT"):
                try:
                    payload = request.data
                except Exception:
                    payload = {}
                # Only allow if the only field being changed is 'publication_status'
                allowed_fields = {"publication_status"}
                changed_fields = set(payload.keys())
                if not changed_fields.issubset(allowed_fields):
                    return False
            return True

        return False

    def _check_safe_permissions(self, request, obj):
        """
        Helper method to handle safe method permissions based on publication_status.
        """
        if not hasattr(obj, "publication_status"):
            return False  # Deny access if publication_status is undefined

        from .models import UserCreatedObject

        status = obj.publication_status

        # Published objects are always readable
        if status == UserCreatedObject.STATUS_PUBLISHED:
            return True

        # Objects in review: owner or moderator/staff can view
        if status == UserCreatedObject.STATUS_REVIEW:
            return obj.owner == request.user or self._is_moderator(request.user, obj)

        # Private objects: owner or moderator/staff can view
        if status == UserCreatedObject.STATUS_PRIVATE:
            return obj.owner == request.user or self._is_moderator(request.user, obj)

        # Archived objects: NOT publicly readable; owner or moderator/staff only
        if status == getattr(UserCreatedObject, "STATUS_ARCHIVED", "archived"):
            return obj.owner == request.user or self._is_moderator(request.user, obj)

        return False

    def _is_moderator(self, user, obj):
        """
        Determines if the user has moderation permissions for the given object.
        Assumes that a permission named 'can_moderate_<modelname>' exists.
        """
        if not user or not user.is_authenticated:
            return False

        model_name = obj._meta.model_name
        perm_codename = f"can_moderate_{model_name}"
        app_label = obj._meta.app_label
        return user.is_staff or user.has_perm(f"{app_label}.{perm_codename}")

    # Public wrapper to avoid using private method in other modules/templates
    def is_moderator(self, user, obj):  # pragma: no cover - thin wrapper
        return self._is_moderator(user, obj)

    def has_submit_permission(self, request, obj):
        """
        Check if the user can submit an object for review.
        Owners or staff can submit when the object is private (first submission)
        or declined (re‑submission). Archived objects cannot be submitted.
        """
        from .models import UserCreatedObject

        if not request.user or not request.user.is_authenticated:
            return False

        status = getattr(obj, "publication_status", None)
        if status == getattr(UserCreatedObject, "STATUS_ARCHIVED", "archived"):
            return False

        allowed_statuses = {
            getattr(UserCreatedObject, "STATUS_PRIVATE", "private"),
            getattr(UserCreatedObject, "STATUS_DECLINED", "declined"),
        }
        return (
            obj.owner == request.user or getattr(request.user, "is_staff", False)
        ) and status in allowed_statuses

    def has_withdraw_permission(self, request, obj):
        """
        Check if the user can withdraw an object from review.
        Owners or staff can withdraw when the object is in review or declined.
        Archived objects cannot be withdrawn.
        """
        from .models import UserCreatedObject

        if not request.user or not request.user.is_authenticated:
            return False

        status = getattr(obj, "publication_status", None)
        if status == getattr(UserCreatedObject, "STATUS_ARCHIVED", "archived"):
            return False

        allowed_statuses = {
            getattr(UserCreatedObject, "STATUS_REVIEW", "review"),
            getattr(UserCreatedObject, "STATUS_DECLINED", "declined"),
        }
        return (
            obj.owner == request.user or getattr(request.user, "is_staff", False)
        ) and status in allowed_statuses

    def has_approve_permission(self, request, obj):
        """
        Check if the user can approve an object.
        Only moderators who are NOT the owner can approve objects in review (four eyes principle).
        """
        from .models import UserCreatedObject

        if not request.user or not request.user.is_authenticated:
            return False

        return (
            self._is_moderator(request.user, obj)
            and obj.publication_status == UserCreatedObject.STATUS_REVIEW
            and obj.owner
            != request.user  # Four eyes principle: can't approve own objects
        )

    def has_reject_permission(self, request, obj):
        """
        Check if the user can reject an object.
        Only moderators who are NOT the owner can reject objects in review (four eyes principle).
        """
        from .models import UserCreatedObject

        if not request.user or not request.user.is_authenticated:
            return False

        return (
            self._is_moderator(request.user, obj)
            and obj.publication_status == UserCreatedObject.STATUS_REVIEW
            and obj.owner
            != request.user  # Four eyes principle: can't reject own objects
        )

    def has_archive_permission(self, request, obj):
        """
        Check if the user can archive an object.

        Policy aligned with get_object_policy.can_archive:
        - Object must be published (not already archived)
        - User must be owner, staff, or moderator for the model
        """
        if not request.user or not request.user.is_authenticated:
            return False

        try:
            from .models import UserCreatedObject

            is_published = getattr(obj, "publication_status", None) == getattr(
                UserCreatedObject, "STATUS_PUBLISHED", "published"
            )
            is_archived = getattr(obj, "publication_status", None) == getattr(
                UserCreatedObject, "STATUS_ARCHIVED", "archived"
            )
        except Exception:
            # Fail-closed if model does not define statuses
            return False

        if not is_published or is_archived:
            return False

        # Owner, staff, or moderator
        is_owner = getattr(obj, "owner_id", None) == getattr(request.user, "id", None)
        return (
            is_owner
            or getattr(request.user, "is_staff", False)
            or self._is_moderator(request.user, obj)
        )


# Centralized object policy for templates and views
def get_object_policy(user, obj, request=None, review_mode=False):
    """
    Compute a unified policy dictionary for the given object and user.

    This is the single source of truth for button visibility in templates and
    should mirror backend permission checks. Review workflow permissions are
    delegated (when appropriate) to UserCreatedObjectPermission to ensure
    consistency with backend behavior.

    Returned dict keys (booleans unless noted):
      - is_authenticated, is_owner, is_staff, is_moderator
      - is_private, is_in_review, is_published, is_declined, is_archived
      - can_edit, can_manage_samples, can_add_property
      - can_duplicate, can_new_version
      - can_archive, can_delete
      - can_submit_review, can_withdraw_review, can_approve, can_reject
      - can_export, export_list_type ('published'|'private'|None)
      - can_view_review_feedback
    """
    perm = UserCreatedObjectPermission()

    # Basic identity flags
    is_authenticated = bool(user and getattr(user, "is_authenticated", False))
    is_staff = bool(getattr(user, "is_staff", False))
    is_owner = bool(
        is_authenticated and getattr(obj, "owner_id", None) == getattr(user, "id", None)
    )

    # Publication status helpers (use convenience properties if available)
    is_private = bool(getattr(obj, "is_private", False))
    is_in_review = bool(getattr(obj, "is_in_review", False))
    is_published = bool(getattr(obj, "is_published", False))
    is_declined = bool(getattr(obj, "is_declined", False))
    is_archived = bool(getattr(obj, "is_archived", False))
    # Fallbacks using raw publication_status if convenience properties are unavailable
    try:
        _status = getattr(obj, "publication_status", None)
        if _status is not None:
            if not is_private and _status == "private":
                is_private = True
            if not is_in_review and _status == "review":
                is_in_review = True
            if not is_published and _status == "published":
                is_published = True
            if not is_declined and _status == "declined":
                is_declined = True
            if not is_archived and _status == "archived":
                is_archived = True
    except Exception:
        pass

    # Moderator rights (per-model 'can_moderate_<modelname>' or staff)
    try:
        is_moderator = is_staff or perm.is_moderator(user, obj)
    except Exception:
        logger.exception(
            "Failed checking moderator permission in get_object_policy", exc_info=True
        )
        is_moderator = is_staff  # safer default

    # Ensure we have a request-like object for permission helpers
    if request is None:
        request = SimpleNamespace(user=user)

    # logger.debug(
    #     "Entering get_object_policy for obj=%s user=%s",
    #     getattr(obj, "pk", None),
    #     getattr(user, "id", None),
    # )

    # Review workflow permissions (delegate to centralized helpers)
    # logger.debug(
    #     "get_object_policy status: auth=%s archived=%s owner=%s staff=%s private=%s declined=%s in_review=%s obj=%s user=%s",
    #     is_authenticated,
    #     is_archived,
    #     is_owner,
    #     is_staff,
    #     is_private,
    #     is_declined,
    #     is_in_review,
    #     getattr(obj, "pk", None),
    #     getattr(user, "id", None),
    # )
    can_submit_review = (
        bool(perm.has_submit_permission(request, obj)) if is_authenticated else False
    )
    can_withdraw_review = (
        bool(perm.has_withdraw_permission(request, obj)) if is_authenticated else False
    )
    # Approve/Reject via permission helper (four eyes, moderator)
    can_approve = (
        bool(perm.has_approve_permission(request, obj)) if is_authenticated else False
    )
    can_reject = (
        bool(perm.has_reject_permission(request, obj)) if is_authenticated else False
    )

    # logger.debug(
    #     "get_object_policy actions: can_submit=%s can_withdraw=%s moderator=%s",
    #     can_submit_review,
    #     can_withdraw_review,
    #     is_moderator,
    # )
    # CRUD-like actions
    has_update_url = bool(getattr(obj, "update_url", None))
    # Support both modal and direct delete URLs across templates
    has_delete_url = bool(
        getattr(obj, "modal_delete_url", None) or getattr(obj, "delete_url", None)
    )

    # Edit: staff always; owners if not published; never when archived
    can_edit = (
        has_update_url
        and not is_archived
        and (is_staff or (is_owner and not is_published))
    )

    # Delete:
    # - Archived: staff-only special case (optional "Archive → Delete")
    # - Published: staff only
    # - Private/Review/Declined: owner or staff
    can_delete = has_delete_url and (
        (is_archived and is_staff)
        or (
            (not is_archived)
            and (
                (is_published and is_staff)
                or (not is_published and (is_owner or is_staff))
            )
        )
    )

    # Archive: only when published; not already archived; owner, staff, or moderator
    can_archive = (
        is_published and not is_archived and (is_owner or is_staff or is_moderator)
    )

    # Object-specific management helpers
    # If published objects shouldn't mutate, gate with not is_published
    can_manage_samples = (is_owner or is_staff) and not is_archived and not is_published
    can_add_property = (is_owner or is_staff) and not is_archived

    # Duplicate/New version: require model add permission
    can_duplicate = False
    try:
        model = obj.__class__
        app_label = model._meta.app_label
        model_name = model._meta.model_name
        add_perm = f"{app_label}.add_{model_name}"
        can_duplicate = is_authenticated and user.has_perm(add_perm)
    except Exception:
        logger.exception(
            "Failed checking add permission in get_object_policy", exc_info=True
        )
        can_duplicate = False
    # New version usually requires ownership/staff, published state, and not archived
    can_new_version = (
        can_duplicate and (is_owner or is_staff) and is_published and not is_archived
    )

    # Export: allow anonymous export of published/archived; private export requires auth and ownership/staff
    can_export = (is_published or is_archived) or (
        is_authenticated and (is_owner or is_staff)
    )
    export_list_type = (
        "published"
        if (is_published or is_archived)
        else ("private" if (is_owner or is_staff) else None)
    )

    # Review feedback visibility (declined and owner, outside explicit review mode UIs)
    can_view_review_feedback = is_owner and is_declined and (not bool(review_mode))

    return {
        "is_authenticated": is_authenticated,
        "is_owner": is_owner,
        "is_staff": is_staff,
        "is_moderator": is_moderator,
        "is_private": is_private,
        "is_in_review": is_in_review,
        "is_published": is_published,
        "is_declined": is_declined,
        "is_archived": is_archived,
        "can_edit": can_edit,
        "can_manage_samples": can_manage_samples,
        "can_add_property": can_add_property,
        "can_duplicate": can_duplicate,
        "can_new_version": can_new_version,
        "can_archive": can_archive,
        "can_delete": can_delete,
        "can_submit_review": can_submit_review,
        "can_withdraw_review": can_withdraw_review,
        "can_approve": can_approve,
        "can_reject": can_reject,
        "can_export": can_export,
        "export_list_type": export_list_type,
        "can_view_review_feedback": can_view_review_feedback,
    }


def user_is_moderator_for_model(user, model_class):
    """Return ``True`` when ``user`` has moderation rights for ``model_class``."""

    if not user or not getattr(user, "is_authenticated", False):
        return False

    perm_codename = f"can_moderate_{model_class._meta.model_name}"
    full_perm = f"{model_class._meta.app_label}.{perm_codename}"
    return getattr(user, "is_staff", False) or user.has_perm(full_perm)


def _resolve_status_value(model, status_name: str):
    """Return the concrete value for ``STATUS_<status_name>`` on the model hierarchy."""

    attr_name = f"STATUS_{status_name.upper()}"
    if hasattr(model, attr_name):
        return getattr(model, attr_name)

    # Fallback to the base implementation on UserCreatedObject
    from .models import UserCreatedObject

    if hasattr(UserCreatedObject, attr_name):
        return getattr(UserCreatedObject, attr_name)

    # As a last resort, use the provided string (lowercase) to keep behaviour predictable
    return status_name.lower()


def apply_scope_filter(queryset, scope: str | None, user=None):
    """Filter ``queryset`` according to the requested scope ('published', 'private', ...)."""

    if scope is None:
        return queryset

    model = queryset.model

    if not hasattr(model, "publication_status"):
        raise ImproperlyConfigured(
            f"{model.__name__} must define a 'publication_status' field to use scoped lists."
        )

    status_field = "publication_status"

    def _status_kwargs(name: str):
        return {status_field: _resolve_status_value(model, name)}

    def _ensure_owner_field(scope_name: str):
        if not hasattr(model, "owner"):
            raise ImproperlyConfigured(
                f"{model.__name__} must define an 'owner' field to use the '{scope_name}' scope."
            )

    staff_or_moderator = getattr(
        user, "is_staff", False
    ) or user_is_moderator_for_model(user, model)
    is_authenticated = bool(user) and getattr(user, "is_authenticated", False)

    if scope == "published":
        return queryset.filter(**_status_kwargs("published"))

    if scope == "private":
        if staff_or_moderator:
            return queryset
        if not is_authenticated:
            return queryset.none()
        _ensure_owner_field("private")
        return queryset.filter(owner=user)

    if scope in {"review", "declined", "archived"}:
        filtered = queryset.filter(**_status_kwargs(scope))
        if staff_or_moderator:
            return filtered
        if not is_authenticated:
            return queryset.none()
        _ensure_owner_field(scope)
        return filtered.filter(owner=user)

    return queryset


def filter_queryset_for_user(queryset, user):
    """Return the subset of ``queryset`` visible to ``user`` under the read policy."""

    model = queryset.model

    if getattr(user, "is_staff", False):
        return queryset

    if user_is_moderator_for_model(user, model):
        return queryset

    if not getattr(user, "is_authenticated", False):
        return queryset.filter(
            publication_status=_resolve_status_value(model, "published")
        )

    if not hasattr(model, "owner"):
        raise ImproperlyConfigured(
            f"{model.__name__} must define an 'owner' field to apply user visibility filtering."
        )

    return queryset.filter(
        Q(owner=user) | Q(publication_status=_resolve_status_value(model, "published"))
    )


def build_scope_filter_params(scope: str | None, user):
    """Return filter kwargs (as lists) that mirror ``apply_scope_filter`` for exports."""

    if scope == "private":
        if not user or not getattr(user, "is_authenticated", False):
            return {"owner": []}
        return {"owner": [getattr(user, "pk", None)]}

    if scope == "review":
        from .models import UserCreatedObject

        return {
            "publication_status": [_resolve_status_value(UserCreatedObject, "review")]
        }

    if scope == "declined":
        from .models import UserCreatedObject

        return {
            "publication_status": [_resolve_status_value(UserCreatedObject, "declined")]
        }

    if scope == "archived":
        from .models import UserCreatedObject

        return {
            "publication_status": [_resolve_status_value(UserCreatedObject, "archived")]
        }

    from .models import UserCreatedObject

    return {
        "publication_status": [_resolve_status_value(UserCreatedObject, "published")]
    }
