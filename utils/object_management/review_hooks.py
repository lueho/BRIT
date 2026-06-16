from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

ReviewContextEnricher = Callable[[object], Mapping[str, object]]
ReviewUpdateContextBuilder = Callable[[object, object], Mapping[str, object] | None]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BreadcrumbModule:
    label: str
    url_name: str | None
    parent_label: str | None = None
    parent_url_name: str | None = None


_review_context_enrichers: dict[str, list[ReviewContextEnricher]] = {}
_review_search_fields: dict[str, tuple[str, ...]] = {}
_review_update_context_builders: dict[str, ReviewUpdateContextBuilder] = {}
_breadcrumb_modules: dict[str, BreadcrumbModule] = {}


def register_review_context_enricher(
    model_label: str,
    fn: ReviewContextEnricher,
) -> None:
    label = _normalize_model_label(model_label)
    enrichers = _review_context_enrichers.setdefault(label, [])
    if fn not in enrichers:
        enrichers.append(fn)


def get_review_context_enrichments(obj: object) -> dict[str, object]:
    context: dict[str, object] = {}
    for enricher in _review_context_enrichers.get(_model_label_for(obj), []):
        try:
            context.update(enricher(obj))
        except Exception:
            logger.exception(
                "Failed to build review context enrichment for %s.",
                _model_label_for(obj),
            )
    return context


def register_review_search_fields(
    model_label: str,
    fields: Iterable[str],
) -> None:
    _review_search_fields[_normalize_model_label(model_label)] = tuple(fields)


def get_review_search_fields(model_class: object) -> tuple[str, ...]:
    return _review_search_fields.get(_model_label_for(model_class), ())


def register_review_update_context(
    model_label: str,
    fn: ReviewUpdateContextBuilder,
) -> None:
    _review_update_context_builders[_normalize_model_label(model_label)] = fn


def get_review_update_context(user: object, obj: object) -> Mapping[str, object] | None:
    builder = _review_update_context_builders.get(_model_label_for(obj))
    if builder is None:
        return None
    return builder(user, obj)


def register_breadcrumb_module(
    app_label: str,
    *,
    label: str,
    url_name: str | None,
    parent_label: str | None = None,
    parent_url_name: str | None = None,
) -> None:
    _breadcrumb_modules[app_label] = BreadcrumbModule(
        label=label,
        url_name=url_name,
        parent_label=parent_label,
        parent_url_name=parent_url_name,
    )


def get_breadcrumb_module(app_label: str) -> BreadcrumbModule | None:
    return _breadcrumb_modules.get(app_label)


def snapshot_review_hooks_for_tests() -> tuple[
    dict[str, list[ReviewContextEnricher]],
    dict[str, tuple[str, ...]],
    dict[str, ReviewUpdateContextBuilder],
    dict[str, BreadcrumbModule],
]:
    return (
        {key: list(value) for key, value in _review_context_enrichers.items()},
        dict(_review_search_fields),
        dict(_review_update_context_builders),
        dict(_breadcrumb_modules),
    )


def restore_review_hooks_for_tests(
    snapshot: tuple[
        dict[str, list[ReviewContextEnricher]],
        dict[str, tuple[str, ...]],
        dict[str, ReviewUpdateContextBuilder],
        dict[str, BreadcrumbModule],
    ],
) -> None:
    (
        context_enrichers,
        search_fields,
        update_context_builders,
        breadcrumb_modules,
    ) = snapshot
    _review_context_enrichers.clear()
    _review_context_enrichers.update(context_enrichers)
    _review_search_fields.clear()
    _review_search_fields.update(search_fields)
    _review_update_context_builders.clear()
    _review_update_context_builders.update(update_context_builders)
    _breadcrumb_modules.clear()
    _breadcrumb_modules.update(breadcrumb_modules)


def _model_label_for(model_or_obj: object) -> str:
    return _normalize_model_label(
        f"{model_or_obj._meta.app_label}.{model_or_obj._meta.model_name}"
    )


def _normalize_model_label(model_label: str) -> str:
    return model_label.lower()
