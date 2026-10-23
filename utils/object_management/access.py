"""Access-control mixins for user-created objects.

Single home for the ownership/publication-status permission mixins used by
object-management views and by app views that compose them directly.
"""

from django.contrib.auth.mixins import PermissionRequiredMixin, UserPassesTestMixin
from django.core.exceptions import (
    ImproperlyConfigured,
    ObjectDoesNotExist,
)
from django.http import Http404

from utils.views import NextOrSuccessUrlMixin

from .permissions import _resolve_status_value, get_object_policy


class UserOwnsObjectMixin(UserPassesTestMixin):
    """
    All models that have access restrictions specific to a user contain a field named 'owner'. This mixin prevents
    access to objects owned by other users.
    """

    def test_func(self):
        try:
            obj = self.get_object()
        except Http404:
            # Propagate 404 so DetailView handles nonexistent objects correctly
            raise
        except ObjectDoesNotExist as err:
            # Normalize model DoesNotExist to Http404
            raise Http404 from err
        except Exception:
            return False
        policy = get_object_policy(self.request.user, obj, request=self.request)
        return policy["is_owner"]


class UserCreatedObjectReadAccessMixin(UserPassesTestMixin):
    """
    A Mixin to control access to objects based on 'publication_status' and 'owner'.

    - Published objects ('publication_status' == 'published') are accessible to all users.
    - Unpublished objects are accessible to their owners, staff, or moderators
      (users with the per‑model permission `can_moderate_<model>`).
    """

    publication_status_field = "publication_status"
    owner_field = "owner"
    published_status = "published"
    permission_denied_message = "You do not have permission to access this object."

    def test_func(self):
        try:
            obj = self.get_object()
        except Http404:
            # Ensure missing objects yield 404 rather than permission redirect
            raise
        except ObjectDoesNotExist as err:
            # Normalize model-specific DoesNotExist to Http404
            raise Http404 from err
        except Exception:
            return False

        if not hasattr(obj, self.publication_status_field) or not hasattr(
            obj, self.owner_field
        ):
            raise ImproperlyConfigured(
                f"The model {obj.__class__.__name__} must have '{self.publication_status_field}' and '{self.owner_field}' fields."
            )

        # Directly honor model publication_status for public read access
        try:
            status = getattr(obj, self.publication_status_field, None)
            if status is not None:
                published_value = _resolve_status_value(obj.__class__, "published")
                if status == published_value:
                    return True
        except Exception:
            pass

        # Policy-based evaluation (covers private/review/declined/archived and role checks)
        policy = get_object_policy(self.request.user, obj, request=self.request)
        if policy["is_published"]:
            return True
        # Archived, private, review, and declined objects require authentication
        return (
            policy["is_owner"]
            or policy["is_editor"]
            or policy["is_staff"]
            or policy["is_moderator"]
        )


class UserCreatedObjectWriteAccessMixin(UserPassesTestMixin):
    """
    A Mixin to control write access to objects based on 'publication_status' and 'owner'.

    - Published objects ('publication_status' == 'published') are accessible to all users.
    - Unpublished objects are only accessible to their owners.
    """

    publication_status_field = "publication_status"
    owner_field = "owner"
    published_status = "published"
    permission_denied_message = "You do not have permission to access this object."
    object_policy_action = "edit"

    def test_func(self):
        user = self.request.user

        # Authentication is required for all write operations
        if not user.is_authenticated:
            return False

        try:
            obj = self.get_object()
        except Http404:
            # For write operations on nonexistent objects, propagate 404
            raise
        except ObjectDoesNotExist as err:
            raise Http404 from err
        except Exception:
            return False

        if not hasattr(obj, self.publication_status_field) or not hasattr(
            obj, self.owner_field
        ):
            raise ImproperlyConfigured(
                f"The model {obj.__class__.__name__} must have '{self.publication_status_field}' and '{self.owner_field}' fields."
            )

        policy = get_object_policy(user, obj, request=self.request)
        if self.object_policy_action == "delete":
            if policy["can_delete"]:
                return True
            # Fallback for models without delete URLs in the policy
            return not policy["is_archived"] and (
                policy["is_staff"]
                or (policy["is_owner"] and not policy["is_published"])
            )

        if self.object_policy_action == "duplicate" and policy["can_new_version"]:
            return True

        if policy["can_edit"]:
            return True

        # Fallback for models without update URLs in the policy
        return not policy["is_archived"] and (
            policy["is_staff"]
            or (
                policy["is_owner"]
                and not policy["is_published"]
                and policy["has_change_permission"]
            )
        )


class CreateUserObjectMixin(PermissionRequiredMixin, NextOrSuccessUrlMixin):
    def has_permission(self):
        # Staff users can always create objects
        if self.request.user.is_staff:
            return True
        # For non-staff users, use the default permission check
        return super().has_permission()

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)
