from dataclasses import dataclass

from django.apps import apps

KIND_REVIEWABLE = "reviewable"
KIND_OWNED = "owned"
KIND_PUBLIC_CATALOGUE = "public_catalogue"
KIND_GENERATED = "generated"


@dataclass(frozen=True)
class ModelPolicy:
    kind: str
    parent_path: str | None = None
    contributor: bool = False
    published_attachment: str | None = None


REVIEWABLE_MODELS = frozenset(
    {
        "bibliography.author",
        "bibliography.licence",
        "bibliography.source",
        "closecycle.showcase",
        "distributions.period",
        "distributions.temporaldistribution",
        "distributions.timestep",
        "greenhouses.culture",
        "greenhouses.greenhouse",
        "greenhouses.greenhousegrowthcycle",
        "greenhouses.growthshare",
        "inventories.scenario",
        "maps.catchment",
        "maps.catchmentrevision",
        "maps.categoricalattribute",
        "maps.geodataset",
        "maps.lauregion",
        "maps.location",
        "maps.mapconfiguration",
        "maps.maplayerconfiguration",
        "maps.maplayerstyle",
        "maps.nutsregion",
        "maps.region",
        "maps.regionattributetextvalue",
        "maps.regionattributevalue",
        "maps.regionproperty",
        "materials.analyticalmethod",
        "materials.basematerial",
        "materials.componentmeasurement",
        "materials.composition",
        "materials.material",
        "materials.materialcategory",
        "materials.materialcomponent",
        "materials.materialcomponentgroup",
        "materials.materialproperty",
        "materials.materialpropertygroup",
        "materials.materialpropertyvalue",
        "materials.sample",
        "materials.samplegroup",
        "materials.sampleseries",
        "processes.process",
        "processes.processcategory",
        "properties.property",
        "properties.unit",
        "simucf.inputmaterial",
        "waste_collection.aggregatedcollectionpropertyvalue",
        "waste_collection.binconfiguration",
        "waste_collection.collection",
        "waste_collection.collectioncatchment",
        "waste_collection.collectioncountoptions",
        "waste_collection.collectionfrequency",
        "waste_collection.collectionpropertyvalue",
        "waste_collection.collectionseason",
        "waste_collection.collectionsystem",
        "waste_collection.collector",
        "waste_collection.feesystem",
        "waste_collection.wastecategory",
        "waste_collection.wastecomponent",
        "waste_collection.wasteflyer",
    }
)

CURATED_MODELS = frozenset(
    {
        "maps.catchmentrevision",
        "maps.lauregion",
        "maps.mapconfiguration",
        "maps.maplayerconfiguration",
        "maps.maplayerstyle",
        "maps.nutsregion",
    }
)

# Owned children whose runtime relation/column configuration additionally
# requires explicit application administration on every mutation — including
# create, edit, delete, reassignment, and editable-scope listing. Ordinary
# owned children not listed here remain governed solely by parent authority.
ADMINISTRATOR_MANAGED_CHILDREN = frozenset(
    {
        "maps.geodatasetcolumnpolicy",
        "maps.geodatasetruntimeconfiguration",
    }
)

OWNED_CHILDREN = {
    "bibliography.sourceauthor": "source",
    "closecycle.showcasematerial": "showcase",
    "closecycle.showcaseprocess": "showcase",
    "distributions.timestep": "distribution",
    "greenhouses.greenhousegrowthcycle": "greenhouse",
    "greenhouses.growthshare": "timestepset__growth_cycle__greenhouse",
    "greenhouses.growthtimestepset": "growth_cycle__greenhouse",
    "inventories.scenarioinventoryconfiguration": "scenario",
    "maps.geodatasetcolumnpolicy": "dataset",
    "maps.geodatasetruntimeconfiguration": "dataset",
    "maps.georeferencedcatchment": "catchment_ptr",
    "maps.georeferencednutsregion": "nutsregion_ptr",
    "maps.georeferencedregion": "region_ptr",
    "materials.composition": "sample",
    "materials.sampleauthor": "sample",
    "materials.sampleexternalrecord": "sample",
    "processes.processauthor": "process",
    "processes.processinforesource": "process",
    "processes.processlink": "process",
    "processes.processmaterial": "process",
    "processes.processoperatingparameter": "process",
    "processes.processsource": "process",
}

PUBLIC_CATALOGUE_MODELS = frozenset(
    {
        "closecycle.biogasplantssweden",
        "greenhouses.nantesgreenhouses",
        "roadside_trees.hamburgroadsidetrees",
        "urban_green_spaces.hamburggreenareas",
    }
)

INDEPENDENT_EVIDENCE = {
    "maps.regionattributetextvalue": "region",
    "maps.regionattributevalue": "region",
    "materials.componentmeasurement": "sample",
    "materials.materialpropertyvalue": "sample",
    "waste_collection.aggregatedcollectionpropertyvalue": "collections",
    "waste_collection.collectionpropertyvalue": "collection",
}

PUBLISHED_ATTACHMENT_SCOPES = {
    "maps.regionattributetextvalue": "read",
    "maps.regionattributevalue": "read",
    "materials.materialpropertyvalue": "collaborator",
    "waste_collection.aggregatedcollectionpropertyvalue": "read",
    "waste_collection.collectionpropertyvalue": "read",
}

# Declarative per-record generated-projection profiles:
# model label -> (marker field, source pointer field). Rows whose marker is
# true are read-only projections governed by their linked raw source
# evidence; the class-level policy keeps describing raw records.
GENERATED_PROJECTIONS = {}


def _build_policies():
    policies = {}
    owned_labels = frozenset(OWNED_CHILDREN)
    for label in REVIEWABLE_MODELS - owned_labels:
        policies[label] = ModelPolicy(
            kind=KIND_REVIEWABLE,
            parent_path=INDEPENDENT_EVIDENCE.get(label),
            contributor=label not in CURATED_MODELS,
            published_attachment=PUBLISHED_ATTACHMENT_SCOPES.get(label),
        )
    for label, parent_path in OWNED_CHILDREN.items():
        policies[label] = ModelPolicy(kind=KIND_OWNED, parent_path=parent_path)
    for label in PUBLIC_CATALOGUE_MODELS:
        policies[label] = ModelPolicy(kind=KIND_PUBLIC_CATALOGUE)
    return policies


MODEL_POLICIES = _build_policies()


def model_policy(model):
    meta = getattr(model, "_meta", None)
    if meta is None:
        return None
    label = getattr(meta, "label_lower", None)
    if not isinstance(label, str):
        return None
    return MODEL_POLICIES.get(label)


def administrator_managed(model):
    """Whether writes to ``model`` additionally require ``actor.admin``.

    Parent authority, lifecycle state, and capability checks still apply; the
    administrator requirement is strictly additive.
    """
    meta = getattr(model, "_meta", None)
    label = getattr(meta, "label_lower", None) if meta is not None else None
    return label in ADMINISTRATOR_MANAGED_CHILDREN


def generated_profile(model):
    """Return the declared ``(marker, pointer)`` generated profile or None."""
    meta = getattr(model, "_meta", None)
    label = getattr(meta, "label_lower", None) if meta is not None else None
    return GENERATED_PROJECTIONS.get(label)


def record_policy(obj):
    """Return the effective policy for one persisted or in-memory record.

    Rows whose configured generated-projection marker is true resolve to a
    ``KIND_GENERATED`` record policy pointing at their declared source
    relation; every other object keeps its class-level classification.
    """
    policy = model_policy(type(obj))
    if policy is None:
        return None
    profile = generated_profile(type(obj))
    if profile is not None and getattr(obj, profile[0], None) is True:
        return ModelPolicy(kind=KIND_GENERATED, parent_path=profile[1])
    return policy


def generated_source(obj):
    """Resolve the declared raw source of a generated row, or None.

    A valid source is persisted, distinct from the projection, and keeps a
    ``KIND_REVIEWABLE`` record policy — never another generated row, an
    owned child, or a missing link.
    """
    policy = record_policy(obj)
    if policy is None or policy.kind != KIND_GENERATED:
        return None
    source = resolve_parent(obj, policy.parent_path)
    if source is None or source.pk is None or source.pk == obj.pk:
        return None
    source_policy = record_policy(source)
    if source_policy is None or source_policy.kind != KIND_REVIEWABLE:
        return None
    return source


def review_target(obj):
    """Return the record whose review lifecycle governs ``obj``.

    A generated projection resolves to its validated raw source; every
    other record is its own review target. ``None`` marks a generated
    row whose source is missing or invalid — it has no review surface.
    """
    policy = record_policy(obj)
    if policy is not None and policy.kind == KIND_GENERATED:
        return generated_source(obj)
    return obj


def root_model(model, parent_path):
    current = model
    for part in parent_path.split("__"):
        try:
            field = current._meta.get_field(part)
        except Exception:
            return None
        current = getattr(field, "related_model", None)
        if current is None:
            return None
    return current


def resolve_parent(instance, parent_path):
    current = instance
    for part in parent_path.split("__"):
        current = getattr(current, part, None)
        if current is None or getattr(current, "pk", None) is None:
            return None
    return current


def declared_parent_changed(instance, parent_path, new_parent):
    """Whether ``new_parent`` re-targets ``instance`` away from its stored parent.

    The stored row is re-read because form validation already copies the
    posted parent onto the in-memory instance.
    """
    if instance.pk is not None:
        stored = type(instance)._base_manager.filter(pk=instance.pk).first()
        if stored is not None:
            instance = stored
    if isinstance(new_parent, (list, tuple)):
        new_keys = sorted(getattr(p, "pk", None) for p in new_parent)
        old_keys = sorted(p.pk for p in resolve_parents(instance, parent_path))
        return new_keys != old_keys
    old_parent = resolve_parent(instance, parent_path)
    if old_parent is None:
        return True
    return getattr(new_parent, "pk", None) != old_parent.pk


def resolve_parents(instance, parent_path):
    """Resolve every persisted parent row for a declared ``parent_path``.

    Single-valued paths return a one-element list; many-valued paths return
    all related rows. Empty result means the stored parent cannot be
    resolved.
    """
    from django.db.models.manager import BaseManager

    first = getattr(instance, parent_path.split("__")[0], None)
    if first is None:
        return []
    if isinstance(first, BaseManager):
        return list(first.all())
    parent = resolve_parent(instance, parent_path)
    return [parent] if parent is not None else []


def resolve_create_parent(policy, instance=None, validated_data=None):
    """Resolve the declared parent for a create decision.

    Reads the configured ``parent_path`` from the (possibly unsaved) instance
    first, then from validated form/serializer data. Returns a parent
    instance, a list/tuple of parents, or ``None`` when the context cannot be
    resolved.
    """
    if policy is None or policy.parent_path is None:
        return None
    if instance is not None:
        try:
            parent = resolve_parent(instance, policy.parent_path)
        except (AttributeError, ValueError):
            parent = None
        if parent is not None:
            return parent
    if validated_data:
        parts = policy.parent_path.split("__")
        related = validated_data.get(parts[0])
        if isinstance(related, (list, tuple)):
            return related
        for part in parts[1:]:
            related = getattr(related, part, None) if related is not None else None
        return related
    return None


def registered_models(kind=None):
    for label, policy in MODEL_POLICIES.items():
        if kind is None or policy.kind == kind:
            yield apps.get_model(label)
