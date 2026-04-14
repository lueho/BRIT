from sources.contracts import (
    SourceDomainExplorerCard,
    SourceDomainMapMount,
    SourceDomainPlugin,
    SourceDomainPublicMount,
)

plugin = SourceDomainPlugin(
    slug="greenhouses",
    verbose_name="Greenhouses",
    app_config="sources.greenhouses.apps.GreenhousesConfig",
    urlconf="sources.greenhouses.urls",
    capabilities=("api", "exports", "forms", "html_views", "tasks", "templates"),
    published_count_getter="sources.greenhouses.selectors.published_greenhouse_count",
    map_mount=SourceDomainMapMount(
        mount_path="nantes/",
        urlconf="sources.greenhouses.urls",
    ),
    public_mount=SourceDomainPublicMount(
        mount_path="case_studies/nantes/",
        urlconf="sources.greenhouses.urls",
    ),
    sitemap_items=(
        "/maps/nantes/cultures/",
        "/maps/nantes/cultures/create/",
        "/maps/nantes/greenhouses/data/",
        "/maps/nantes/greenhouses/map/",
        "/maps/nantes/greenhouses/export/",
        "/maps/nantes/greenhouses/catchment_autocomplete/",
        "/maps/nantes/greenhouses/",
        "/maps/nantes/greenhouses/create/",
        "/maps/nantes/growthcycles/create_inline/",
        "/case_studies/nantes/cultures/",
        "/case_studies/nantes/cultures/create/",
        "/case_studies/nantes/greenhouses/data/",
        "/case_studies/nantes/greenhouses/map/",
        "/case_studies/nantes/greenhouses/export/",
        "/case_studies/nantes/greenhouses/catchment_autocomplete/",
        "/case_studies/nantes/greenhouses/",
        "/case_studies/nantes/greenhouses/create/",
        "/case_studies/nantes/growthcycles/create_inline/",
    ),
    explorer_card=SourceDomainExplorerCard(
        title="Greenhouses",
        description=(
            "Greenhouse facilities near Nantes, France, with growth cycles, cultures, "
            "and residue generation data from the FLEXIBI project."
        ),
        url_name="greenhouse-list",
        image_path="img/greenhouses_cover_card.png",
        image_alt="Greenhouses cover image",
        icon_class="fas fa-fw fa-seedling",
        order=20,
    ),
)
