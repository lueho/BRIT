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
class SourceDomainPlugin:
    slug: str
    verbose_name: str
    app_config: str
    urlconf: str
    capabilities: tuple[str, ...] = ()
    mount_in_hub: bool = False
    mount_path: str = ""
    explorer_context_var: str | None = None
    published_count_getter: str | None = None
    explorer_card: SourceDomainExplorerCard | None = None
    legacy_redirects: SourceDomainLegacyRedirects | None = None

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
