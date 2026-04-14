from sources.contracts import (
    SourceDomainLegacyRedirects,
    SourceDomainMapMount,
    SourceDomainPlugin,
)

plugin = SourceDomainPlugin(
    slug="roadside_trees",
    verbose_name="Roadside Trees",
    app_config="sources.roadside_trees.apps.RoadsideTreesConfig",
    urlconf="sources.roadside_trees.urls",
    capabilities=(
        "api",
        "exports",
        "html_views",
        "legacy_redirects",
        "static_assets",
        "templates",
    ),
    mount_in_hub=True,
    mount_path="",
    map_mount=SourceDomainMapMount(
        mount_path="hamburg/",
        urlconf="sources.roadside_trees.urls",
    ),
    legacy_redirects=SourceDomainLegacyRedirects(
        mount_path="case_studies/hamburg/",
        urlconf="sources.roadside_trees.legacy_urls",
    ),
)
