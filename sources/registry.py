from importlib import import_module

from django.apps import apps

from sources.contracts import SourceDomainPlugin


def _discover_source_domain_plugins() -> tuple[SourceDomainPlugin, ...]:
    plugins: list[SourceDomainPlugin] = []

    for app_config in apps.get_app_configs():
        if app_config.name == "sources":
            continue

        try:
            plugin_module = import_module(f"{app_config.name}.plugin")
        except ModuleNotFoundError as exc:
            if exc.name == f"{app_config.name}.plugin":
                continue
            raise

        plugin = getattr(plugin_module, "plugin", None)
        if plugin is None:
            continue
        if not isinstance(plugin, SourceDomainPlugin):
            raise TypeError(
                f"{app_config.name}.plugin.plugin must be a SourceDomainPlugin instance"
            )
        plugins.append(plugin)

    return tuple(sorted(plugins, key=lambda plugin: plugin.slug))


_SOURCE_DOMAIN_PLUGINS: tuple[SourceDomainPlugin, ...] = (
    _discover_source_domain_plugins()
)


def get_source_domain_plugins() -> tuple[SourceDomainPlugin, ...]:
    return _SOURCE_DOMAIN_PLUGINS


def get_source_domain_plugin(slug: str) -> SourceDomainPlugin:
    for plugin in _SOURCE_DOMAIN_PLUGINS:
        if plugin.slug == slug:
            return plugin

    raise LookupError(f"Unknown source-domain plugin: {slug}")


def get_hub_source_domain_plugins() -> tuple[SourceDomainPlugin, ...]:
    return tuple(plugin for plugin in _SOURCE_DOMAIN_PLUGINS if plugin.mount_in_hub)


def get_explorer_context() -> dict[str, int | None]:
    context: dict[str, int | None] = {}

    for plugin in _SOURCE_DOMAIN_PLUGINS:
        if not plugin.explorer_context_var:
            continue
        context[plugin.explorer_context_var] = plugin.get_published_count()

    return context
