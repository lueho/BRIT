from django.core.exceptions import ImproperlyConfigured

from .object_management.models import UserCreatedObject
from .object_management.permissions import UserCreatedObjectPermission
from .object_management.registry import model_policy


class HasModelPermission(UserCreatedObjectPermission):
    """
    A custom permission class that extends the base permission class provided by Django REST Framework.

    This class is used to check if a request should be granted or denied access based on the user's permissions and the
    required permissions for the view's action. It supports checking multiple permissions for a single action.

    For models registered in the object-management policy registry, the
    explicit ``permission_required`` entries remain enforced as additional
    narrowing, while authorization itself delegates to
    ``utils.object_management.policy.decide`` so model-permission-only checks
    cannot bypass object-level or lifecycle rules.
    """

    _STANDARD_PERM_VERBS = {
        "create": "add",
        "list": "view",
        "retrieve": "view",
        "update": "change",
        "partial_update": "change",
        "destroy": "delete",
    }

    def _dict_permissions_allow(self, request, view, registered_model=None):
        """Enforce the view's explicit ``permission_required`` mapping.

        On registered models, a required permission identical to the model's
        standard action permission is covered by the policy decision itself and
        is skipped; any additional or different requirement still applies as
        explicit narrowing.
        """
        if not hasattr(view, "permission_required"):
            raise ImproperlyConfigured(
                "View does not have a 'permission_required' attribute."
            )

        if type(view.permission_required) is not dict:
            raise ImproperlyConfigured(
                "View's 'permission_required' attribute must be a dictionary."
            )

        if view.action not in view.permission_required:
            raise ImproperlyConfigured(
                f"Action '{view.action}' does not have a permission_required attribute."
            )

        required_permissions = view.permission_required.get(view.action)

        if required_permissions is None:
            return True

        if isinstance(required_permissions, str):
            required_permissions = [required_permissions]

        if registered_model is not None:
            verb = self._STANDARD_PERM_VERBS.get(getattr(view, "action", None))
            if verb is not None:
                meta = registered_model._meta
                standard = {f"{meta.app_label}.{verb}_{meta.model_name}"}
                required_permissions = [
                    perm for perm in required_permissions if perm not in standard
                ]

        for perm in required_permissions:
            if not request.user.has_perm(perm):
                return False

        return True

    def has_permission(self, request, view):
        # The OPTIONS method is not associated with any action and should always be allowed
        if request.method in ("OPTIONS", "HEAD"):
            return True

        model = self._get_view_model(view)
        registered = model is not None and model_policy(model) is not None

        if not self._dict_permissions_allow(
            request, view, registered_model=model if registered else None
        ):
            return False

        if not registered:
            if model is not None and issubclass(model, UserCreatedObject):
                return False
            return True

        return super().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        if model_policy(type(obj)) is None:
            return not isinstance(obj, UserCreatedObject)
        return super().has_object_permission(request, view, obj)
