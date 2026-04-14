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
