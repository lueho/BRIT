from django.apps import apps
from django.core.checks import Error, register
from django.db.models import BooleanField

from .models import UserCreatedObject
from .registry import (
    CURATED_MODELS,
    GENERATED_PROJECTIONS,
    INDEPENDENT_EVIDENCE,
    KIND_OWNED,
    KIND_PUBLIC_CATALOGUE,
    KIND_REVIEWABLE,
    MODEL_POLICIES,
    root_model,
)


def _check_parent_path(errors, label, model, policy):
    if not policy.parent_path:
        errors.append(
            Error(
                f"Registry model {label} is {policy.kind} but has no parent_path.",
                id="object_management.E004",
            )
        )
        return
    resolved = root_model(model, policy.parent_path)
    if resolved is None:
        errors.append(
            Error(
                f"Registry parent_path {policy.parent_path!r} of {label} does not resolve.",
                id="object_management.E005",
            )
        )
        return
    if policy.kind == KIND_OWNED:
        root_policy = MODEL_POLICIES.get(resolved._meta.label_lower)
        if root_policy is None or root_policy.kind != KIND_REVIEWABLE:
            errors.append(
                Error(
                    f"Owned child {label} resolves to {resolved._meta.label_lower} "
                    "which is not a registered reviewable model.",
                    id="object_management.E006",
                )
            )


@register("object_management")
def registry_classification_check(app_configs, **kwargs):
    errors = []
    get_models = (
        apps.get_models
        if app_configs is None
        else (lambda: (m for c in app_configs for m in c.get_models()))
    )
    for model in get_models():
        if not (isinstance(model, type) and issubclass(model, UserCreatedObject)):
            continue
        if model._meta.abstract:
            continue
        label = model._meta.label_lower
        if label not in MODEL_POLICIES:
            errors.append(
                Error(
                    f"UserCreatedObject model {label} has no registry classification.",
                    hint="Add an explicit ModelPolicy in utils/object_management/registry.py.",
                    id="object_management.E001",
                )
            )
    for app_models in apps.all_models.values():
        for model in app_models.values():
            if not (
                isinstance(model, type)
                and issubclass(model, UserCreatedObject)
                and model._meta.proxy
            ):
                continue
            if model._meta.label_lower not in MODEL_POLICIES:
                errors.append(
                    Error(
                        f"UserCreatedObject proxy {model._meta.label_lower} has no "
                        "registry classification.",
                        hint="Add an explicit ModelPolicy in utils/object_management/registry.py.",
                        id="object_management.E010",
                    )
                )
    for label, policy in MODEL_POLICIES.items():
        try:
            model = apps.get_model(label)
        except LookupError:
            errors.append(
                Error(
                    f"Registry model {label} is not installed.",
                    id="object_management.E002",
                )
            )
            continue
        if policy.kind not in {
            KIND_REVIEWABLE,
            KIND_OWNED,
            KIND_PUBLIC_CATALOGUE,
        }:
            errors.append(
                Error(
                    f"Registry model {label} has unknown kind {policy.kind!r}.",
                    id="object_management.E003",
                )
            )
            continue
        if policy.kind == KIND_OWNED:
            _check_parent_path(errors, label, model, policy)
        elif policy.kind == KIND_REVIEWABLE and label in INDEPENDENT_EVIDENCE:
            _check_parent_path(errors, label, model, policy)
        if policy.kind == KIND_REVIEWABLE and label in CURATED_MODELS:
            if policy.contributor:
                errors.append(
                    Error(
                        f"Curated model {label} is flagged as contributor.",
                        id="object_management.E007",
                    )
                )
    for label in CURATED_MODELS - frozenset(MODEL_POLICIES):
        errors.append(
            Error(
                f"Curated model {label} is missing from the registry.",
                id="object_management.E008",
            )
        )
    for label in frozenset(INDEPENDENT_EVIDENCE) - frozenset(MODEL_POLICIES):
        errors.append(
            Error(
                f"Independent evidence model {label} is missing from the registry.",
                id="object_management.E009",
            )
        )
    for label, (marker_field, source_path) in GENERATED_PROJECTIONS.items():
        policy = MODEL_POLICIES.get(label)
        try:
            model = apps.get_model(label)
        except LookupError:
            model = None
        if model is None:
            errors.append(
                Error(
                    f"Generated-projection model {label} is not installed.",
                    id="object_management.E011",
                )
            )
            continue
        if policy is None or policy.kind != KIND_REVIEWABLE:
            errors.append(
                Error(
                    f"Generated-projection model {label} must keep a registered "
                    "reviewable class policy for its raw records.",
                    id="object_management.E012",
                )
            )
        try:
            marker = model._meta.get_field(marker_field)
        except Exception:
            marker = None
        if not isinstance(marker, BooleanField):
            errors.append(
                Error(
                    f"Generated-projection marker {label}.{marker_field} must be "
                    "a BooleanField.",
                    id="object_management.E013",
                )
            )
        source_root = root_model(model, source_path)
        if source_root is None:
            errors.append(
                Error(
                    f"Generated-projection source path {label}.{source_path} "
                    "does not resolve.",
                    id="object_management.E014",
                )
            )
            continue
        source_policy = MODEL_POLICIES.get(source_root._meta.label_lower)
        if source_policy is None or source_policy.kind != KIND_REVIEWABLE:
            errors.append(
                Error(
                    f"Generated-projection source {label}.{source_path} resolves "
                    f"to {source_root._meta.label_lower} which is not a "
                    "registered reviewable model.",
                    id="object_management.E015",
                )
            )
    return errors
