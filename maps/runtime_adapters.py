from dataclasses import dataclass

from django.core.exceptions import ImproperlyConfigured

from maps.filters import NutsRegionFilterSet
from maps.models import NutsRegion
from sources.registry import get_source_domain_dataset_runtime_compatibility

LEGACY_DATASET_RUNTIME_COMPATIBILITY = {
    "NutsRegion": {
        "model": NutsRegion,
        "filterset_class": NutsRegionFilterSet,
        "template_name": "nuts_region_map.html",
        "features_api_basename": "api-nuts-region",
        "apply_user_visibility_filter": True,
    }
}


@dataclass(frozen=True)
class DatasetRuntimeAdapter:
    dataset: object
    runtime_model_name: str
    model: type
    filterset_class: type
    template_name: str
    features_api_basename: str
    apply_user_visibility_filter: bool = True

    def configure_view(self, view, *, template_name=None):
        view.model = self.model
        view.filterset_class = self.filterset_class
        view.template_name = template_name or self.template_name
        view.apply_user_visibility_filter = self.apply_user_visibility_filter
        view.model_name = self.runtime_model_name
        view.features_layer_api_basename = self.features_api_basename

    def get_visible_column_policies(self):
        return list(
            self.dataset.column_policies.filter(is_visible=True).order_by("column_name")
        )

    @staticmethod
    def get_policy_label(policy):
        return policy.display_label or policy.column_name.replace("_", " ").title()

    @staticmethod
    def get_column_value(obj, column_name):
        value = obj
        for attr in column_name.split("__"):
            value = getattr(value, attr, None)
            if value is None:
                return ""
        return value


def get_dataset_runtime_compatibility(runtime_model_name):
    compatibility = LEGACY_DATASET_RUNTIME_COMPATIBILITY.get(runtime_model_name)
    if compatibility is not None:
        return compatibility
    return get_source_domain_dataset_runtime_compatibility(runtime_model_name)


def get_dataset_runtime_adapter(dataset):
    runtime_model_name = dataset.get_runtime_model_name()
    compatibility = get_dataset_runtime_compatibility(runtime_model_name)
    if compatibility is None:
        raise ImproperlyConfigured(
            f"No dataset runtime compatibility registered for {runtime_model_name}."
        )
    if isinstance(compatibility, dict):
        model = compatibility["model"]
        filterset_class = compatibility["filterset_class"]
        template_name = compatibility["template_name"]
        apply_user_visibility_filter = compatibility["apply_user_visibility_filter"]
        features_api_basename = compatibility["features_api_basename"]
    else:
        model = compatibility.resolve_model()
        filterset_class = compatibility.resolve_filterset_class()
        template_name = compatibility.template_name
        apply_user_visibility_filter = compatibility.apply_user_visibility_filter
        features_api_basename = compatibility.features_api_basename
    return DatasetRuntimeAdapter(
        dataset=dataset,
        runtime_model_name=runtime_model_name,
        model=model,
        filterset_class=filterset_class,
        template_name=template_name,
        features_api_basename=(
            dataset.get_features_api_basename() or features_api_basename
        ),
        apply_user_visibility_filter=apply_user_visibility_filter,
    )
