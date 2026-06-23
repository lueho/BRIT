from collections.abc import Callable

from maps.contracts import (
    SourceDomainDatasetRuntimeCompatibility,
    SourceDomainMapMount,
)

DatasetRuntimeCompatibilities = tuple[SourceDomainDatasetRuntimeCompatibility, ...]
SourceDomainMapMountListener = Callable[[SourceDomainMapMount], None]

_MAP_MOUNTS: list[SourceDomainMapMount] = []
_MAP_MOUNT_LISTENERS: list[SourceDomainMapMountListener] = []
_GEOJSON_CACHE_WARMERS: dict[str, object] = {}
_DATASET_RUNTIME_COMPATIBILITIES: dict[
    str, SourceDomainDatasetRuntimeCompatibility
] = {}


def _register_unique(registry, key, value, *, label):
    existing = registry.get(key)
    if existing is not None and existing != value:
        raise ValueError(f"Duplicate {label} registration for {key}.")
    registry[key] = value


def register_source_domain_map_contracts(
    *,
    slug: str,
    map_mount: SourceDomainMapMount | None = None,
    geojson_cache_warmer=None,
    dataset_runtime_compatibilities: DatasetRuntimeCompatibilities = (),
) -> None:
    new_map_mount = None
    if map_mount is not None:
        if map_mount not in _MAP_MOUNTS:
            _MAP_MOUNTS.append(map_mount)
            new_map_mount = map_mount
    if geojson_cache_warmer is not None:
        _register_unique(
            _GEOJSON_CACHE_WARMERS,
            slug,
            geojson_cache_warmer,
            label="GeoJSON cache warmer",
        )
    for compatibility in dataset_runtime_compatibilities:
        _register_unique(
            _DATASET_RUNTIME_COMPATIBILITIES,
            compatibility.runtime_model_name,
            compatibility,
            label="dataset runtime compatibility",
        )
    if new_map_mount is not None:
        for listener in _MAP_MOUNT_LISTENERS:
            listener(new_map_mount)


def register_source_domain_map_mount_listener(
    listener: SourceDomainMapMountListener,
) -> None:
    if listener not in _MAP_MOUNT_LISTENERS:
        _MAP_MOUNT_LISTENERS.append(listener)
    for map_mount in get_source_domain_map_mounts():
        listener(map_mount)


def get_source_domain_map_mounts() -> tuple[SourceDomainMapMount, ...]:
    return tuple(
        sorted(
            _MAP_MOUNTS,
            key=lambda map_mount: (map_mount.mount_path, map_mount.urlconf),
        )
    )


def get_source_domain_geojson_cache_warmers() -> tuple[tuple[str, object], ...]:
    return tuple(sorted(_GEOJSON_CACHE_WARMERS.items()))


def get_source_domain_dataset_runtime_compatibilities() -> (
    DatasetRuntimeCompatibilities
):
    return tuple(
        sorted(
            _DATASET_RUNTIME_COMPATIBILITIES.values(),
            key=lambda compatibility: compatibility.runtime_model_name,
        )
    )


def get_source_domain_dataset_runtime_compatibility(
    runtime_model_name: str,
) -> SourceDomainDatasetRuntimeCompatibility | None:
    return _DATASET_RUNTIME_COMPATIBILITIES.get(runtime_model_name)
