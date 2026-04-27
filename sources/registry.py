from importlib import import_module

from django.apps import apps

from sources.contracts import (
    SourceDomainDatasetRuntimeCompatibility,
    SourceDomainExplorerCard,
    SourceDomainLegacyRedirects,
    SourceDomainMapMount,
    SourceDomainPlugin,
    SourceDomainPublicMount,
)


def _optional_module_exists(module_name: str) -> bool:
    try:
        import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            return False
        raise
    return True


def _validate_source_domain_plugin(
    plugin: SourceDomainPlugin, *, discovered_app_name: str
) -> None:
    if not plugin.slug:
        raise ValueError(
            f"{discovered_app_name}.plugin.plugin must define a non-empty slug"
        )

    if plugin.get_app_module() != discovered_app_name:
        raise ValueError(
            f"{discovered_app_name}.plugin.plugin app_config must point back to "
            f"the discovered app"
        )

    if plugin.mount_path and not plugin.mount_in_hub:
        raise ValueError(
            f"{discovered_app_name}.plugin.plugin mount_path requires mount_in_hub=True"
        )

    if plugin.explorer_card is not None and not plugin.published_count_getter:
        raise ValueError(
            f"{discovered_app_name}.plugin.plugin explorer_card requires a "
            f"published_count_getter"
        )

    if plugin.explorer_card is not None and not isinstance(
        plugin.explorer_card, SourceDomainExplorerCard
    ):
        raise TypeError(
            f"{discovered_app_name}.plugin.plugin explorer_card must be a "
            f"SourceDomainExplorerCard instance"
        )

    if plugin.legacy_redirects is not None and not isinstance(
        plugin.legacy_redirects, SourceDomainLegacyRedirects
    ):
        raise TypeError(
            f"{discovered_app_name}.plugin.plugin legacy_redirects must be a "
            f"SourceDomainLegacyRedirects instance"
        )

    if plugin.map_mount is not None and not isinstance(
        plugin.map_mount, SourceDomainMapMount
    ):
        raise TypeError(
            f"{discovered_app_name}.plugin.plugin map_mount must be a "
            f"SourceDomainMapMount instance"
        )

    if plugin.public_mount is not None and not isinstance(
        plugin.public_mount, SourceDomainPublicMount
    ):
        raise TypeError(
            f"{discovered_app_name}.plugin.plugin public_mount must be a "
            f"SourceDomainPublicMount instance"
        )

    if not isinstance(plugin.sitemap_items, tuple) or not all(
        isinstance(item, str) for item in plugin.sitemap_items
    ):
        raise TypeError(
            f"{discovered_app_name}.plugin.plugin sitemap_items must be a "
            f"tuple of strings"
        )

    if plugin.geojson_cache_warmer is not None and not isinstance(
        plugin.geojson_cache_warmer, str
    ):
        raise TypeError(
            f"{discovered_app_name}.plugin.plugin geojson_cache_warmer must be a "
            f"dotted task path string"
        )

    if not isinstance(plugin.dataset_runtime_compatibilities, tuple) or not all(
        isinstance(item, SourceDomainDatasetRuntimeCompatibility)
        for item in plugin.dataset_runtime_compatibilities
    ):
        raise TypeError(
            f"{discovered_app_name}.plugin.plugin "
            f"dataset_runtime_compatibilities must be a tuple of "
            f"SourceDomainDatasetRuntimeCompatibility instances"
        )

    if "exports" in plugin.capabilities:
        module_name = f"{plugin.get_app_module()}.exports"
        if not _optional_module_exists(module_name):
            raise ValueError(
                f"{discovered_app_name}.plugin.plugin declares 'exports' "
                f"capability but {module_name} is missing"
            )


def _validate_source_domain_plugins(plugins: tuple[SourceDomainPlugin, ...]) -> None:
    seen_slugs: dict[str, str] = {}
    seen_mount_paths: dict[str, str] = {}
    seen_public_mount_paths: dict[str, str] = {}
    seen_runtime_model_names: dict[str, str] = {}

    for plugin in plugins:
        existing_slug_owner = seen_slugs.get(plugin.slug)
        if existing_slug_owner is not None:
            raise ValueError(
                f"Duplicate source-domain plugin slug '{plugin.slug}' declared by "
                f"{existing_slug_owner} and {plugin.get_app_module()}"
            )
        seen_slugs[plugin.slug] = plugin.get_app_module()

        for compatibility in plugin.dataset_runtime_compatibilities:
            existing_runtime_owner = seen_runtime_model_names.get(
                compatibility.runtime_model_name
            )
            if existing_runtime_owner is not None:
                raise ValueError(
                    f"Duplicate source-domain dataset runtime compatibility "
                    f"'{compatibility.runtime_model_name}' declared by "
                    f"{existing_runtime_owner} and {plugin.get_app_module()}"
                )
            seen_runtime_model_names[compatibility.runtime_model_name] = (
                plugin.get_app_module()
            )

        if plugin.public_mount is not None:
            existing_public_mount_owner = seen_public_mount_paths.get(
                plugin.public_mount.mount_path
            )
            if existing_public_mount_owner is not None:
                raise ValueError(
                    f"Duplicate source-domain public mount_path "
                    f"'{plugin.public_mount.mount_path}' declared by "
                    f"{existing_public_mount_owner} and {plugin.get_app_module()}"
                )
            seen_public_mount_paths[plugin.public_mount.mount_path] = (
                plugin.get_app_module()
            )

        if not plugin.mount_in_hub:
            continue

        existing_mount_owner = seen_mount_paths.get(plugin.mount_path)
        if existing_mount_owner is not None:
            raise ValueError(
                f"Duplicate source-domain hub mount_path '{plugin.mount_path}' "
                f"declared by {existing_mount_owner} and {plugin.get_app_module()}"
            )
        seen_mount_paths[plugin.mount_path] = plugin.get_app_module()


def _discover_source_domain_plugins() -> tuple[SourceDomainPlugin, ...]:
    plugins: list[SourceDomainPlugin] = []

    for app_config in apps.get_app_configs():
        if app_config.name == "sources":
            continue

        try:
            plugin_module = import_module(f"{app_config.name}.plugin")
        except ModuleNotFoundError as exc:
            if exc.name == f"{app_config.name}.plugin":
                continue
            raise

        plugin = getattr(plugin_module, "plugin", None)
        if plugin is None:
            continue
        if not isinstance(plugin, SourceDomainPlugin):
            raise TypeError(
                f"{app_config.name}.plugin.plugin must be a SourceDomainPlugin instance"
            )

        _validate_source_domain_plugin(plugin, discovered_app_name=app_config.name)
        plugins.append(plugin)

    discovered_plugins = tuple(sorted(plugins, key=lambda plugin: plugin.slug))
    _validate_source_domain_plugins(discovered_plugins)
    return discovered_plugins


_SOURCE_DOMAIN_PLUGINS: tuple[SourceDomainPlugin, ...] = (
    _discover_source_domain_plugins()
)


def get_source_domain_plugins() -> tuple[SourceDomainPlugin, ...]:
    return _SOURCE_DOMAIN_PLUGINS


def get_source_domain_plugin(slug: str) -> SourceDomainPlugin:
    for plugin in _SOURCE_DOMAIN_PLUGINS:
        if plugin.slug == slug:
            return plugin

    raise LookupError(f"Unknown source-domain plugin: {slug}")


def get_hub_source_domain_plugins() -> tuple[SourceDomainPlugin, ...]:
    return tuple(plugin for plugin in _SOURCE_DOMAIN_PLUGINS if plugin.mount_in_hub)


def get_source_domain_explorer_cards() -> tuple[dict[str, object], ...]:
    cards: list[dict[str, object]] = []

    for plugin in _SOURCE_DOMAIN_PLUGINS:
        if plugin.explorer_card is None:
            continue

        cards.append(
            {
                "slug": plugin.slug,
                "title": plugin.explorer_card.title,
                "description": plugin.explorer_card.description,
                "url_name": plugin.explorer_card.url_name,
                "image_path": plugin.explorer_card.image_path,
                "image_alt": plugin.explorer_card.image_alt,
                "icon_class": plugin.explorer_card.icon_class,
                "cta_label": plugin.explorer_card.cta_label,
                "order": plugin.explorer_card.order,
                "published_count": plugin.get_published_count(),
            }
        )

    return tuple(sorted(cards, key=lambda card: (card["order"], card["title"])))


def get_source_domain_legacy_redirects() -> tuple[SourceDomainLegacyRedirects, ...]:
    redirects: list[SourceDomainLegacyRedirects] = []

    for plugin in _SOURCE_DOMAIN_PLUGINS:
        if plugin.legacy_redirects is None:
            continue
        redirects.append(plugin.legacy_redirects)

    return tuple(sorted(redirects, key=lambda redirect: redirect.mount_path))


def get_source_domain_map_mounts() -> tuple[SourceDomainMapMount, ...]:
    map_mounts: list[SourceDomainMapMount] = []

    for plugin in _SOURCE_DOMAIN_PLUGINS:
        if plugin.map_mount is None:
            continue
        map_mounts.append(plugin.map_mount)

    return tuple(
        sorted(
            map_mounts, key=lambda map_mount: (map_mount.mount_path, map_mount.urlconf)
        )
    )


def get_source_domain_public_mounts() -> tuple[SourceDomainPublicMount, ...]:
    public_mounts: list[SourceDomainPublicMount] = []

    for plugin in _SOURCE_DOMAIN_PLUGINS:
        if plugin.public_mount is None:
            continue
        public_mounts.append(plugin.public_mount)

    return tuple(
        sorted(public_mounts, key=lambda public_mount: public_mount.mount_path)
    )


def get_source_domain_sitemap_items() -> tuple[str, ...]:
    sitemap_items: list[str] = []
    seen_items: set[str] = set()

    for plugin in _SOURCE_DOMAIN_PLUGINS:
        for item in plugin.sitemap_items:
            if item in seen_items:
                continue
            seen_items.add(item)
            sitemap_items.append(item)

    return tuple(sitemap_items)


def get_source_domain_geojson_cache_warmers() -> tuple[tuple[str, object], ...]:
    warmers: list[tuple[str, object]] = []

    for plugin in _SOURCE_DOMAIN_PLUGINS:
        warmer = plugin.get_geojson_cache_warmer()
        if warmer is None:
            continue
        warmers.append((plugin.slug, warmer))

    return tuple(warmers)


def get_source_domain_dataset_runtime_compatibilities() -> (
    tuple[SourceDomainDatasetRuntimeCompatibility, ...]
):
    compatibilities: list[SourceDomainDatasetRuntimeCompatibility] = []

    for plugin in _SOURCE_DOMAIN_PLUGINS:
        compatibilities.extend(plugin.dataset_runtime_compatibilities)

    return tuple(
        sorted(
            compatibilities,
            key=lambda compatibility: compatibility.runtime_model_name,
        )
    )


def get_source_domain_dataset_runtime_compatibility(
    runtime_model_name: str,
) -> SourceDomainDatasetRuntimeCompatibility | None:
    for compatibility in get_source_domain_dataset_runtime_compatibilities():
        if compatibility.runtime_model_name == runtime_model_name:
            return compatibility
    return None
