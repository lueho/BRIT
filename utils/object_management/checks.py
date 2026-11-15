import inspect

from django.apps import apps
from django.core.checks import Error, register
from django.db.models import BooleanField
from django.urls import URLPattern, URLResolver, get_resolver
from django_filters import (
    FilterSet,
    ModelChoiceFilter,
    ModelMultipleChoiceFilter,
)
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from .models import UserCreatedObject
from .registry import (
    CURATED_MODELS,
    GENERATED_PROJECTIONS,
    INDEPENDENT_EVIDENCE,
    KIND_OWNED,
    KIND_PUBLIC_CATALOGUE,
    KIND_REVIEWABLE,
    MODEL_POLICIES,
    model_policy,
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


def _route_view_classes(patterns, prefix=""):
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            yield from _route_view_classes(pattern.url_patterns, route)
            continue
        if not isinstance(pattern, URLPattern):
            continue
        callback = pattern.callback
        view_class = getattr(callback, "view_class", None) or getattr(
            callback, "cls", None
        )
        if view_class is not None:
            yield route, view_class


def _governed_models(view_class):
    candidates = (
        getattr(view_class, "policy_model", None),
        getattr(view_class, "model", None),
        getattr(getattr(view_class, "queryset", None), "model", None),
        getattr(
            getattr(getattr(view_class, "serializer_class", None), "Meta", None),
            "model",
            None,
        ),
        getattr(
            getattr(getattr(view_class, "form_class", None), "_meta", None),
            "model",
            None,
        ),
        getattr(
            getattr(getattr(view_class, "filterset_class", None), "_meta", None),
            "model",
            None,
        ),
    )
    models = {}
    for model in candidates:
        if not inspect.isclass(model):
            continue
        policy = model_policy(model)
        if policy is not None and policy.kind != KIND_PUBLIC_CATALOGUE:
            models[model._meta.label_lower] = model
    return tuple(models[label] for label in sorted(models))


def _has_policy_coverage(view_class):
    return getattr(view_class, "policy_enforced", None) is True or (
        isinstance(getattr(view_class, "policy_exempt", None), str)
        and bool(view_class.policy_exempt.strip())
    )


def _view_path(view_class):
    return f"{view_class.__module__}.{view_class.__qualname__}"


def _project_filtersets():
    project_packages = tuple(config.name for config in apps.get_app_configs())
    pending = list(FilterSet.__subclasses__())
    seen = set()
    while pending:
        filterset = pending.pop()
        if filterset in seen:
            continue
        seen.add(filterset)
        pending.extend(filterset.__subclasses__())
        module = filterset.__module__
        if any(
            module == package or module.startswith(f"{package}.")
            for package in project_packages
        ):
            yield filterset


def _governed_choice_filters(filterset):
    for name, filter_ in filterset.base_filters.items():
        if not isinstance(filter_, (ModelChoiceFilter, ModelMultipleChoiceFilter)):
            continue
        queryset = filter_.queryset
        if callable(queryset):
            try:
                queryset = filter_.get_queryset(None)
            except (AttributeError, TypeError):
                continue
        model = getattr(queryset, "model", None)
        policy = model_policy(model)
        if policy is not None and policy.kind != KIND_PUBLIC_CATALOGUE:
            yield name, model


@register("object_management")
def policy_route_coverage_check(app_configs, **kwargs):
    from utils.filters import BaseCrispyFilterSet

    errors = []
    for route, view_class in _route_view_classes(get_resolver().url_patterns):
        view_path = _view_path(view_class)
        models = _governed_models(view_class)
        covered = _has_policy_coverage(view_class)
        if not covered:
            for model in models:
                errors.append(
                    Error(
                        f"Route {route!r} uses {view_path} for governed model "
                        f"{model._meta.label_lower} without policy coverage.",
                        hint=(
                            "Use a policy-enforcing adapter, set "
                            "policy_enforced = True after verifying enforcement, "
                            "or provide a reasoned policy_exempt string."
                        ),
                        id="object_management.E020",
                    )
                )
        if not models and not covered and inspect.isclass(view_class):
            try:
                is_api_view = issubclass(view_class, APIView)
            except TypeError:
                is_api_view = False
            if is_api_view:
                authentication_classes = getattr(
                    view_class, "authentication_classes", ()
                )
                permission_classes = getattr(view_class, "permission_classes", ())
                is_public = (
                    not authentication_classes
                    or not permission_classes
                    or AllowAny in permission_classes
                )
                if is_public:
                    errors.append(
                        Error(
                            f"Public DRF route {route!r} uses {view_path} without "
                            "a governed model or policy coverage.",
                            hint=(
                                "Use a policy-enforcing adapter or provide a "
                                "reasoned policy_exempt string."
                            ),
                            id="object_management.E021",
                        )
                    )

    for filterset in _project_filtersets():
        if issubclass(filterset, BaseCrispyFilterSet):
            continue
        exemption = getattr(filterset, "reference_choices_policy_exempt", None)
        if isinstance(exemption, str) and exemption.strip():
            continue
        for name, model in _governed_choice_filters(filterset):
            filterset_path = f"{filterset.__module__}.{filterset.__qualname__}"
            errors.append(
                Error(
                    f"FilterSet {filterset_path}.{name} has an unscoped choice for "
                    f"governed model {model._meta.label_lower}.",
                    hint=(
                        "Inherit BaseCrispyFilterSet or provide a reasoned "
                        "reference_choices_policy_exempt string."
                    ),
                    id="object_management.E022",
                )
            )
    return errors
