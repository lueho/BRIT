"""Sitemap item registry.

Apps contribute their public, indexable routes by calling
``register_sitemap_items`` from ``AppConfig.ready()``; source-domain plugins
declare ``sitemap_items`` on their ``SourceDomainPlugin`` and are forwarded
here by ``sources.registry``. Keeping the registry in the composition root
lets ``brit`` compose the sitemap without importing higher layers.
"""

from collections.abc import Iterable

_registered_items: list[str] = []


def register_sitemap_items(items: Iterable[str]) -> None:
    for item in items:
        if not isinstance(item, str) or not item.startswith("/"):
            raise ValueError(
                f"Sitemap items must be absolute path strings, got {item!r}"
            )
        _registered_items.append(item)


def get_sitemap_items() -> tuple[str, ...]:
    return tuple(dict.fromkeys(_registered_items))
