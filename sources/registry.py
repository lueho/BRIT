from sources.contracts import SourceDomainPlugin
from sources.greenhouses.plugin import plugin as greenhouses_plugin
from sources.roadside_trees.plugin import plugin as roadside_trees_plugin
from sources.urban_green_spaces.plugin import plugin as urban_green_spaces_plugin
from sources.waste_collection.plugin import plugin as waste_collection_plugin

_SOURCE_DOMAIN_PLUGINS: tuple[SourceDomainPlugin, ...] = (
    roadside_trees_plugin,
    urban_green_spaces_plugin,
    greenhouses_plugin,
    waste_collection_plugin,
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
