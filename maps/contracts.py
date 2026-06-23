from dataclasses import dataclass

from django.utils.module_loading import import_string


@dataclass(frozen=True)
class SourceDomainMapMount:
    mount_path: str
    urlconf: str


@dataclass(frozen=True)
class SourceDomainDatasetRuntimeCompatibility:
    runtime_model_name: str
    model: str
    filterset_class: str
    template_name: str
    features_api_basename: str
    apply_user_visibility_filter: bool = True

    def resolve_model(self):
        return import_string(self.model)

    def resolve_filterset_class(self):
        return import_string(self.filterset_class)
