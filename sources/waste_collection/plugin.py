from sources.contracts import SourceDomainPlugin

plugin = SourceDomainPlugin(
    slug="waste_collection",
    verbose_name="Waste Collection",
    app_config="sources.waste_collection.apps.WasteCollectionConfig",
    urlconf="sources.waste_collection.urls",
    capabilities=(
        "api",
        "exports",
        "forms",
        "html_views",
        "signals",
        "tasks",
        "templates",
    ),
    explorer_context_var="collection_count",
    published_count_getter="sources.waste_collection.selectors.published_collection_count",
)
