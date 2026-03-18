from dataclasses import dataclass
from importlib import import_module


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

    def get_published_count(self) -> int | None:
        if not self.published_count_getter:
            return None

        module_path, attr_name = self.published_count_getter.rsplit(".", 1)
        getter = getattr(import_module(module_path), attr_name)
        return getter()

    def get_urlpatterns(self):
        return import_module(self.urlconf).urlpatterns
