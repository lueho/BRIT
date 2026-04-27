from dataclasses import dataclass
from importlib import import_module


@dataclass(frozen=True)
class SourceDomainExport:
    model_label: str
    filterset: object
    serializer: object
    renderers: dict[str, object]


@dataclass(frozen=True)
class SourceDomainExplorerCard:
    title: str
    description: str
    url_name: str
    image_path: str
    image_alt: str
    icon_class: str = ""
    cta_label: str = "Open list"
    order: int = 0


@dataclass(frozen=True)
class SourceDomainLegacyRedirects:
    mount_path: str
    urlconf: str


@dataclass(frozen=True)
class SourceDomainMapMount:
    mount_path: str
    urlconf: str


@dataclass(frozen=True)
class SourceDomainPublicMount:
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
        module_path, attr_name = self.model.rsplit(".", 1)
        return getattr(import_module(module_path), attr_name)

    def resolve_filterset_class(self):
        module_path, attr_name = self.filterset_class.rsplit(".", 1)
        return getattr(import_module(module_path), attr_name)


@dataclass(frozen=True)
class SourceDomainPlugin:
    slug: str
    verbose_name: str
    app_config: str
    urlconf: str
    capabilities: tuple[str, ...] = ()
    mount_in_hub: bool = False
    mount_path: str = ""
    published_count_getter: str | None = None
    explorer_card: SourceDomainExplorerCard | None = None
    legacy_redirects: SourceDomainLegacyRedirects | None = None
    map_mount: SourceDomainMapMount | None = None
    public_mount: SourceDomainPublicMount | None = None
    sitemap_items: tuple[str, ...] = ()
    geojson_cache_warmer: str | None = None
    dataset_runtime_compatibilities: tuple[
        SourceDomainDatasetRuntimeCompatibility, ...
    ] = ()

    def get_published_count(self) -> int | None:
        if not self.published_count_getter:
            return None

        module_path, attr_name = self.published_count_getter.rsplit(".", 1)
        getter = getattr(import_module(module_path), attr_name)
        return getter()

    def get_app_module(self) -> str:
        return self.app_config.rsplit(".", 2)[0]

    def get_urlpatterns(self):
        return import_module(self.urlconf).urlpatterns

    def get_geojson_cache_warmer(self):
        if not self.geojson_cache_warmer:
            return None

        module_path, attr_name = self.geojson_cache_warmer.rsplit(".", 1)
        warmer = getattr(import_module(module_path), attr_name)
        return warmer
