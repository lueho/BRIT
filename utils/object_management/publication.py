"""Publication dependency utilities for user created objects."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field

from django.apps import apps
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True)
class RelationRule:
    """Descriptor for a related set of objects accessed via attribute name."""

    accessor: str
    label: str | None = None
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
    related_object: object | None
    reason: str
    missing: bool = False
    status: str | None = None

    def describe(self) -> str:
        label = self.rule.get_label().capitalize()
        if self.missing or self.related_object is None:
            obj_label = str(_("missing value"))
        else:
            obj_label = getattr(self.related_object, "name", None) or str(
                self.related_object
            )
        return f"{label}: {obj_label} ({self.reason})"


@dataclass
class PromotionResult:
    promoted: list[object] = field(default_factory=list)
    skipped: list[object] = field(default_factory=list)

    def extend(self, other: PromotionResult) -> None:
        self.promoted.extend(other.promoted)
        self.skipped.extend(other.skipped)


@dataclass
class PrepublishReport:
    """Result of a prepublish dependency check."""

    blocking: list[DependencyIssue] = field(default_factory=list)
    needs_sync: list[DependencyIssue] = field(default_factory=list)

    def has_blocking(self) -> bool:
        return bool(self.blocking)

    def format_blocking_message(self, obj: object, action: str) -> str:
        header = _("Cannot {action} {object}.").format(
            action=action,
            object=getattr(obj, "_meta", None) and obj._meta.verbose_name or obj,
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
        requires_published=(
            RelationRule("distribution", label="temporal distribution"),
        ),
    ),
    ("bibliography", "source"): DependencyConfig(
        requires_published=(RelationRule("licence", label="licence", optional=True),),
    ),
    # soilcom (case studies) --------------------------------------------------
    ("soilcom", "collection"): DependencyConfig(
        requires_published=(
            RelationRule("collector", label="collector", optional=True),
            RelationRule("catchment", label="catchment", optional=True),
            RelationRule("collection_system", label="collection system", optional=True),
            RelationRule("waste_stream", label="waste stream", optional=True),
            RelationRule("frequency", label="collection frequency", optional=True),
            RelationRule("fee_system", label="fee system", optional=True),
            RelationRule("sources", label="source", optional=True),
        ),
        follows_parent=(
            RelationRule(
                "collectionpropertyvalue_set", label="collection property value"
            ),
        ),
    ),
    ("soilcom", "wastestream"): DependencyConfig(
        requires_published=(
            RelationRule("category", label="waste category"),
            RelationRule("allowed_materials", label="allowed material", optional=True),
            RelationRule(
                "forbidden_materials", label="forbidden material", optional=True
            ),
            RelationRule("composition", label="composition series", optional=True),
        ),
    ),
    ("soilcom", "collector"): DependencyConfig(
        requires_published=(RelationRule("catchment", label="catchment"),),
    ),
    ("soilcom", "collectionsystem"): DependencyConfig(),
    ("soilcom", "feesystem"): DependencyConfig(),
}


def get_config_for_object(obj: object) -> DependencyConfig | None:
    key = _registry_key_from_obj(obj)
    return REGISTRY.get(key)


def _resolve_related(obj: object, rule: RelationRule) -> Iterator[object]:
    value = getattr(obj, rule.accessor, None)
    if value is None:
        return iter(())
    if hasattr(value, "all"):
        return value.all()
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


def prepublish_check(obj: object, target_status: str | None = None) -> PrepublishReport:
    config = get_config_for_object(obj)
    report = PrepublishReport()
    if not config:
        return report

    for rule in config.requires_published:
        related_iterable = _resolve_related(obj, rule)
        if isinstance(related_iterable, QuerySet):
            if not related_iterable.exists():
                if not rule.optional:
                    report.blocking.append(
                        DependencyIssue(
                            rule=rule,
                            related_object=None,
                            reason=str(_("missing reference")),
                            missing=True,
                            status=None,
                        )
                    )
                continue
            iterator = related_iterable.iterator()
        else:
            related_list = list(related_iterable)
            if not related_list:
                if not rule.optional:
                    report.blocking.append(
                        DependencyIssue(
                            rule=rule,
                            related_object=None,
                            reason=str(_("missing reference")),
                            missing=True,
                            status=None,
                        )
                    )
                continue
            iterator = iter(related_list)

        for related in iterator:
            if related is None:
                report.blocking.append(
                    DependencyIssue(
                        rule=rule,
                        related_object=None,
                        reason=str(_("missing reference")),
                        missing=True,
                        status=None,
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
                    DependencyIssue(
                        rule=rule,
                        related_object=related,
                        reason=reason,
                        status=status,
                    )
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
                        DependencyIssue(
                            rule=rule,
                            related_object=related,
                            reason=status,
                            status=status,
                        )
                    )
    return report


def cascade_publication_status(
    obj: object,
    target_status: str,
    acting_user: object | None = None,
    visited: set[tuple[str, str, int]] | None = None,
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


def promote_dependencies_to_review(
    obj: object,
    acting_user: object | None = None,
    visited: set[tuple[str, str, int]] | None = None,
    should_promote: Callable[[object], bool] | None = None,
) -> PromotionResult:
    """Set private/declined required dependencies to review status recursively."""

    config = get_config_for_object(obj)
    if not config:
        return PromotionResult()

    if visited is None:
        visited = set()

    result = PromotionResult()

    for rule in config.requires_published:
        for related in _resolve_related(obj, rule):
            if related is None:
                continue

            meta = getattr(related, "_meta", None)
            pk = getattr(related, "pk", None)
            if meta and pk is not None:
                node = (meta.app_label, meta.model_name, pk)
                if node in visited:
                    continue
                visited.add(node)

            status = getattr(related, "publication_status", None)
            if status is None:
                continue

            if should_promote and not should_promote(related):
                result.skipped.append(related)
                continue

            review_status = getattr(related, "STATUS_REVIEW", "review")
            private_status = getattr(related, "STATUS_PRIVATE", "private")
            declined_status = getattr(related, "STATUS_DECLINED", "declined")

            if status in {private_status, declined_status} and review_status is not None:
                _apply_status_change(related, review_status, acting_user)
                result.promoted.append(related)

            child_result = promote_dependencies_to_review(
                related,
                acting_user,
                visited,
                should_promote=should_promote,
            )
            result.extend(child_result)

    return result


def _apply_status_change(
    child: object, target_status: str, acting_user: object | None
) -> None:
    # Import lazily to avoid circular dependencies
    from django.utils import timezone

    update_fields: list[str] = []

    if getattr(child, "publication_status", None) != target_status:
        child.publication_status = target_status
        update_fields.append("publication_status")

    if hasattr(child, "submitted_at"):
        if target_status == getattr(child, "STATUS_REVIEW", "review"):
            child.submitted_at = timezone.now()
            update_fields.append("submitted_at")
        elif target_status in {
            getattr(child, "STATUS_PRIVATE", "private"),
            getattr(child, "STATUS_DECLINED", "declined"),
        }:
            if getattr(child, "submitted_at", None) is not None:
                child.submitted_at = None
                update_fields.append("submitted_at")
    if hasattr(child, "approved_at"):
        if target_status == getattr(child, "STATUS_PUBLISHED", "published"):
            child.approved_at = timezone.now()
            if "approved_at" not in update_fields:
                update_fields.append("approved_at")
            if hasattr(child, "approved_by") and acting_user is not None:
                if getattr(child, "approved_by", None) != acting_user:
                    child.approved_by = acting_user
                    update_fields.append("approved_by")
        else:
            if getattr(child, "approved_at", None) is not None:
                child.approved_at = None
                update_fields.append("approved_at")
            if (
                hasattr(child, "approved_by")
                and getattr(child, "approved_by", None) is not None
            ):
                child.approved_by = None
                update_fields.append("approved_by")

    if update_fields:
        child.save(update_fields=list(dict.fromkeys(update_fields)))


def get_model_config(app_label: str, model_name: str) -> DependencyConfig | None:
    model = apps.get_model(app_label, model_name)
    if model is None:
        return None
    key = (app_label, model_name.lower())
    return REGISTRY.get(key)
