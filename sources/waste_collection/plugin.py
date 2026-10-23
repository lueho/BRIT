from sources.contracts import (
    SourceDomainDatasetRuntimeCompatibility,
    SourceDomainExplorerCard,
    SourceDomainLegacyRedirects,
    SourceDomainPlugin,
    SourceDomainPublicMount,
)

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
        "legacy_redirects",
        "signals",
        "tasks",
        "templates",
    ),
    published_count_getter="sources.waste_collection.selectors.published_collection_count",
    public_mount=SourceDomainPublicMount(
        mount_path="waste_collection/",
        urlconf="sources.waste_collection.urls",
    ),
    legacy_redirects=SourceDomainLegacyRedirects(
        mount_path="waste_collection/api/waste-atlas/",
        urlconf="sources.waste_collection.waste_atlas.legacy_urls",
    ),
    dataset_runtime_compatibilities=(
        SourceDomainDatasetRuntimeCompatibility(
            runtime_model_name="WasteCollection",
            model="sources.waste_collection.models.Collection",
            filterset_class="sources.waste_collection.filters.CollectionFilterSet",
            template_name="waste_collection_map.html",
            features_api_basename="api-waste-collection",
        ),
    ),
    sitemap_items=(
        "/waste_collection/collectors/",
        "/waste_collection/collectionsystems/",
        "/waste_collection/wastecategories/",
        "/waste_collection/wastecomponents/",
        "/waste_collection/frequencies/",
        "/waste_collection/flyers/",
        "/waste_collection/collections/",
        "/waste_collection/collections/map/",
        "/waste_collection/waste-atlas/map/",
    ),
    geojson_cache_warmer="sources.waste_collection.tasks.warm_collection_geojson_cache",
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
