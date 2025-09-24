"""Publication dependency utilities for user created objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator, Optional, Sequence

from django.apps import apps
from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True)
class RelationRule:
    """Descriptor for a related set of objects accessed via attribute name."""

    accessor: str
    label: Optional[str] = None
    optional: bool = False

    def get_label(self) -> str:
        return self.label or self.accessor.replace("_", " ")


@dataclass(frozen=True)
class DependencyConfig:
    """Configuration declaring dependent relations for a model."""

    requires_published: Sequence[RelationRule] = ()
    follows_parent: Sequence[RelationRule] = ()


@dataclass
class DependencyIssue:
    """Represents a dependency that violates publication expectations."""

    rule: RelationRule
    related_object: Optional[object]
    reason: str
    missing: bool = False

    def describe(self) -> str:
        label = self.rule.get_label().capitalize()
        if self.missing or self.related_object is None:
            obj_label = str(_("missing value"))
        else:
            obj_label = getattr(self.related_object, "name", None) or str(self.related_object)
        return f"{label}: {obj_label} ({self.reason})"


@dataclass
class PrepublishReport:
    """Result of a prepublish dependency check."""

    blocking: list[DependencyIssue] = field(default_factory=list)
    needs_sync: list[DependencyIssue] = field(default_factory=list)

    def has_blocking(self) -> bool:
        return bool(self.blocking)

    def format_blocking_message(self, obj: object, action: str) -> str:
        header = _("Cannot {action} {object}." ).format(
            action=action, object=getattr(obj, "_meta", None) and obj._meta.verbose_name or obj
        )
        if not self.blocking:
            return header
        details = "\n".join(f" - {issue.describe()}" for issue in self.blocking)
        return f"{header}\n{_('Unresolved dependencies:')}\n{details}"


def _registry_key_from_obj(obj: object) -> tuple[str, str]:
    meta = getattr(obj, "_meta", None)
    if meta is None:
        raise TypeError("Object does not have Django model metadata")
    return meta.app_label, meta.model_name


REGISTRY: dict[tuple[str, str], DependencyConfig] = {
    ("materials", "sample"): DependencyConfig(
        requires_published=(
            RelationRule("material", label="material"),
            RelationRule("series", label="sample series", optional=True),
            RelationRule("timestep", label="timestep", optional=True),
            RelationRule("sources", label="source"),
        ),
        follows_parent=(
            RelationRule("properties", label="material property value"),
            RelationRule("compositions", label="composition"),
        ),
    ),
    ("materials", "composition"): DependencyConfig(
        requires_published=(
            RelationRule("group", label="component group"),
            RelationRule("fractions_of", label="reference component", optional=True),
        ),
        follows_parent=(RelationRule("shares", label="weight share"),),
    ),
    ("materials", "weightshare"): DependencyConfig(
        requires_published=(RelationRule("component", label="component"),),
    ),
    ("materials", "materialpropertyvalue"): DependencyConfig(
        requires_published=(RelationRule("property", label="material property"),),
    ),
    ("materials", "sampleseries"): DependencyConfig(
        requires_published=(
            RelationRule("material", label="material"),
            RelationRule("temporal_distributions", label="temporal distribution"),
        ),
    ),
    ("materials", "materialcomponentgroup"): DependencyConfig(),
    ("materials", "materialcomponent"): DependencyConfig(),
    ("distributions", "timestep"): DependencyConfig(
        requires_published=(RelationRule("distribution", label="temporal distribution"),),
    ),
    ("bibliography", "source"): DependencyConfig(
        requires_published=(RelationRule("licence", label="licence", optional=True),),
    ),
}


def get_config_for_object(obj: object) -> Optional[DependencyConfig]:
    key = _registry_key_from_obj(obj)
    return REGISTRY.get(key)


def _resolve_related(obj: object, rule: RelationRule) -> Iterator[object]:
    value = getattr(obj, rule.accessor, None)
    if value is None:
        return iter(())
    if hasattr(value, "all"):
        return (item for item in value.all())
    if callable(value):  # support properties returning callables
        value = value()
    if value is None:
        return iter(())
    if isinstance(value, (list, tuple, set)):
        return (item for item in value)
    return iter((value,))


def _is_published(candidate: object) -> bool:
    status = getattr(candidate, "publication_status", None)
    return status == getattr(candidate, "STATUS_PUBLISHED", "published")


def prepublish_check(obj: object, target_status: Optional[str] = None) -> PrepublishReport:
    config = get_config_for_object(obj)
    report = PrepublishReport()
    if not config:
        return report

    for rule in config.requires_published:
        related_iter = list(_resolve_related(obj, rule))
        if not related_iter:
            if rule.optional:
                continue
            report.blocking.append(
                DependencyIssue(
                    rule=rule,
                    related_object=None,
                    reason=str(_("missing reference")),
                    missing=True,
                )
            )
            continue
        for related in related_iter:
            if related is None:
                report.blocking.append(
                    DependencyIssue(
                        rule=rule,
                        related_object=None,
                        reason=str(_("missing reference")),
                        missing=True,
                    )
                )
                continue
            status = getattr(related, "publication_status", None)
            if status is None:
                continue
            if not _is_published(related):
                status_label = getattr(related, "get_publication_status_display", None)
                if callable(status_label):
                    reason = status_label()
                else:
                    reason = status
                report.blocking.append(
                    DependencyIssue(rule=rule, related_object=related, reason=reason)
                )

    if target_status:
        for rule in config.follows_parent:
            for related in _resolve_related(obj, rule):
                if related is None:
                    continue
                status = getattr(related, "publication_status", None)
                if status is None:
                    continue
                if status != target_status:
                    report.needs_sync.append(
                        DependencyIssue(rule=rule, related_object=related, reason=status)
                    )
    return report


def cascade_publication_status(
    obj: object,
    target_status: str,
    acting_user: Optional[object] = None,
    visited: Optional[set[tuple[str, str, int]]] = None,
) -> None:
    config = get_config_for_object(obj)
    if not config:
        return
    if visited is None:
        visited = set()
    meta = getattr(obj, "_meta", None)
    if meta and getattr(obj, "pk", None) is not None:
        node = (meta.app_label, meta.model_name, obj.pk)
        if node in visited:
            return
        visited.add(node)

    for rule in config.follows_parent:
        for related in _resolve_related(obj, rule):
            if related is None or getattr(related, "pk", None) is None:
                continue
            status = getattr(related, "publication_status", None)
            if status is None or status == target_status:
                cascade_publication_status(related, target_status, acting_user, visited)
                continue
            _apply_status_change(related, target_status, acting_user)
            cascade_publication_status(related, target_status, acting_user, visited)


def _apply_status_change(child: object, target_status: str, acting_user: Optional[object]) -> None:
    # Import lazily to avoid circular dependencies
    from django.utils import timezone

    setattr(child, "publication_status", target_status)
    if hasattr(child, "submitted_at"):
        if target_status == getattr(child, "STATUS_REVIEW", "review"):
            child.submitted_at = timezone.now()
        elif target_status in {
            getattr(child, "STATUS_PRIVATE", "private"),
            getattr(child, "STATUS_DECLINED", "declined"),
        }:
            child.submitted_at = None
    if hasattr(child, "approved_at"):
        if target_status == getattr(child, "STATUS_PUBLISHED", "published"):
            child.approved_at = timezone.now()
            if hasattr(child, "approved_by") and acting_user is not None:
                child.approved_by = acting_user
        else:
            child.approved_at = None
            if hasattr(child, "approved_by"):
                child.approved_by = None
    child.save()


def get_model_config(app_label: str, model_name: str) -> Optional[DependencyConfig]:
    model = apps.get_model(app_label, model_name)
    if model is None:
        return None
    key = (app_label, model_name.lower())
    return REGISTRY.get(key)
