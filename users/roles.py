from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from utils.object_management.registry import (
    KIND_PUBLIC_CATALOGUE,
    KIND_REVIEWABLE,
    MODEL_POLICIES,
)

ROLE_REGISTERED = "registered"
ROLE_EDITORS = "editors"
ROLE_LIBRARIANS = "librarians"
ROLE_ADMINISTRATORS = "administrators"
ROLE_ANALYSIS_API = "analysis_api"

MODERATORS_GROUP_NAME = getattr(settings, "REVIEW_MODERATORS_GROUP_NAME", "moderators")

MANAGED_ROLES = (
    ROLE_REGISTERED,
    ROLE_EDITORS,
    ROLE_LIBRARIANS,
    MODERATORS_GROUP_NAME,
    ROLE_ADMINISTRATORS,
    ROLE_ANALYSIS_API,
)

ADMIN_PERMISSION_MODEL = "object_management.reviewaction"
ADMIN_PERMISSION_CODENAME = "administer_objects"

ANALYSIS_API_PERMISSION_MODEL = "waste_collection.collection"
ANALYSIS_API_PERMISSION_CODENAME = "access_analysis_api"

_CRUD_ACTIONS = ("add", "change", "delete", "view")

_LIBRARIAN_MODELS = frozenset(
    {
        "bibliography.author",
        "bibliography.licence",
        "bibliography.source",
    }
)


def _labels(kind, contributor=None):
    return frozenset(
        label
        for label, policy in MODEL_POLICIES.items()
        if policy.kind == kind
        and (contributor is None or policy.contributor == contributor)
    )


def _crud_permissions(labels):
    permissions = set()
    for label in labels:
        model_name = label.rsplit(".", 1)[1]
        for action in _CRUD_ACTIONS:
            permissions.add((label, f"{action}_{model_name}"))
    return permissions


def role_manifest():
    contributor = _labels(KIND_REVIEWABLE, contributor=True)
    curated = _labels(KIND_REVIEWABLE, contributor=False)
    reviewable = contributor | curated
    return {
        ROLE_REGISTERED: _crud_permissions(contributor),
        ROLE_EDITORS: _crud_permissions(reviewable),
        ROLE_LIBRARIANS: _crud_permissions(_LIBRARIAN_MODELS),
        MODERATORS_GROUP_NAME: {
            (label, f"can_moderate_{label.rsplit('.', 1)[1]}") for label in reviewable
        },
        ROLE_ADMINISTRATORS: {
            (ADMIN_PERMISSION_MODEL, ADMIN_PERMISSION_CODENAME),
        }
        | _crud_permissions(reviewable | _labels(KIND_PUBLIC_CATALOGUE)),
        ROLE_ANALYSIS_API: {
            (ANALYSIS_API_PERMISSION_MODEL, ANALYSIS_API_PERMISSION_CODENAME),
        },
    }


_PRIVILEGED_PERMISSIONS = frozenset(
    {
        (ADMIN_PERMISSION_MODEL, ADMIN_PERMISSION_CODENAME),
        (ANALYSIS_API_PERMISSION_MODEL, ANALYSIS_API_PERMISSION_CODENAME),
    }
)


def is_privileged_permission(permission):
    """Moderation, administration, and service grants that only their
    manifest roles may hold; reconciliation revokes them from every other
    managed role."""
    codename = permission.codename
    if codename.startswith("can_moderate_"):
        return True
    label = f"{permission.content_type.app_label}.{permission.content_type.model}"
    return (label, codename) in _PRIVILEGED_PERMISSIONS


def resolve_permission(model_label, codename):
    model = apps.get_model(model_label)
    content_type = ContentType.objects.get_for_model(model, for_concrete_model=False)
    return Permission.objects.get(content_type=content_type, codename=codename)


def role_state():
    state = {}
    missing_rows = []
    for role, required in role_manifest().items():
        required_permissions = set()
        for label, codename in sorted(required):
            try:
                required_permissions.add(resolve_permission(label, codename))
            except (Permission.DoesNotExist, LookupError):
                missing_rows.append((label, codename))
        group = Group.objects.filter(name=role).first()
        granted = set(group.permissions.all()) if group else set()
        state[role] = {
            "required": required_permissions,
            "missing": required_permissions - granted,
            "extraneous": granted - required_permissions,
        }
    return state, missing_rows
