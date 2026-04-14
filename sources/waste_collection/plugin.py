from sources.contracts import SourceDomainExplorerCard, SourceDomainPlugin

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
    published_count_getter="sources.waste_collection.selectors.published_collection_count",
    explorer_card=SourceDomainExplorerCard(
        title="Household Waste Collection",
        description=(
            "Collection system parameters, waste streams, frequencies, and container "
            "types that determine biowaste volumes from households."
        ),
        url_name="collection-list",
        image_path="img/waste_collection_cover_card.png",
        image_alt="Household waste collection cover image",
        icon_class="fas fa-fw fa-recycle",
        order=10,
    ),
)
