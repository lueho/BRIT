from sources.contracts import SourceDomainPlugin

plugin = SourceDomainPlugin(
    slug="greenhouses",
    verbose_name="Greenhouses",
    app_config="sources.greenhouses.apps.GreenhousesConfig",
    urlconf="sources.greenhouses.urls",
    capabilities=("api", "exports", "forms", "html_views", "tasks", "templates"),
    explorer_context_var="greenhouse_count",
    published_count_getter="sources.greenhouses.selectors.published_greenhouse_count",
)
