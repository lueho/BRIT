from sources.contracts import (
    SourceDomainLegacyRedirects,
    SourceDomainMapMount,
    SourceDomainPlugin,
)

plugin = SourceDomainPlugin(
    slug="urban_green_spaces",
    verbose_name="Urban Green Spaces",
    app_config="sources.urban_green_spaces.apps.UrbanGreenSpacesConfig",
    urlconf="sources.urban_green_spaces.urls",
    capabilities=("legacy_redirects",),
    map_mount=SourceDomainMapMount(
        mount_path="hamburg/",
        urlconf="sources.urban_green_spaces.urls",
    ),
    legacy_redirects=SourceDomainLegacyRedirects(
        mount_path="case_studies/hamburg/",
        urlconf="sources.urban_green_spaces.legacy_urls",
    ),
)
