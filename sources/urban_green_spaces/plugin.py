from sources.contracts import SourceDomainPlugin

plugin = SourceDomainPlugin(
    slug="urban_green_spaces",
    verbose_name="Urban Green Spaces",
    app_config="sources.urban_green_spaces.apps.UrbanGreenSpacesConfig",
    urlconf="sources.urban_green_spaces.urls",
    capabilities=("legacy_redirects",),
)
