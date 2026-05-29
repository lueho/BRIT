"""Template tags for the Waste Atlas generic map template."""

from django import template

from ..map_configs import MAP_CONFIGS

register = template.Library()


@register.simple_tag(takes_context=True)
def atlas_js_config(context, map_route_key):
    """Return the merged choropleth config dict for ``map_route_key``.

    Registry values from ``MAP_CONFIGS`` are merged with runtime context
    (country, year, nutsPrefix, nutsLevel) and hard-coded DOM ids.
    The result is intended to be passed through Django's ``json_script``
    filter in the template for safe JSON injection.
    """
    config = dict(MAP_CONFIGS.get(map_route_key, {}))

    # DOM ids shared by every map
    config.setdefault("svgId", "atlas-svg")
    config.setdefault("containerId", "map-container")
    config.setdefault("loadingId", "loading-overlay")

    # Runtime context from the view
    config["country"] = context.get("country", "DE")
    config["year"] = int(context.get("year", 2024))

    nuts_prefix = context.get("nuts_prefix")
    if nuts_prefix:
        config["nutsPrefix"] = nuts_prefix

    nuts_level = context.get("nuts_level")
    if nuts_level:
        config["nutsLevel"] = int(nuts_level)

    return config
