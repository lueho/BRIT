import logging
from datetime import date
from functools import cached_property

import celery
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models, transaction
from django.db.models import Case, Count, IntegerField, Q, Sum, Value, When
from django.db.models.signals import m2m_changed, post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone

from bibliography.models import Source
from distributions.models import Period
from maps.models import Catchment
from materials.models import Material, MaterialCategory, MaterialManager, Sample
from utils.object_management.models import (
    NamedUserCreatedObject,
    UserCreatedObject,
    UserCreatedObjectManager,
    UserCreatedObjectQuerySet,
    get_default_owner,
)
from utils.object_management.permissions import filter_queryset_for_user
from utils.properties.models import PropertyValue

logger = logging.getLogger(__name__)


class CollectionCatchment(Catchment):
    class Meta:
        proxy = True

    @property
    def inside_collections(self):
        return Collection.objects.filter(
            catchment__region__borders__geom__within=self.region.borders.geom
        )

    @property
    def downstream_collections(self):
        qs = Collection.objects.filter(
            catchment__in=self.descendants(include_self=True)
        )
        qs = qs.select_related(
            "catchment", "collector", "waste_category", "collection_system"
        )
        return qs

    @property
    def upstream_collections(self):
        qs = Collection.objects.filter(catchment__in=self.ancestors())
        qs = qs.select_related(
            "catchment", "collector", "waste_category", "collection_system"
        )
        return qs


class Collector(NamedUserCreatedObject):
    website = models.URLField(max_length=511, blank=True, null=True)
    catchment = models.ForeignKey(
        CollectionCatchment, blank=True, null=True, on_delete=models.CASCADE
    )

    class Meta(NamedUserCreatedObject.Meta):
        verbose_name = "waste collector"

    @property
    def geom(self):
        """Return the geometry from the associated catchment."""
        if self.catchment:
            return self.catchment.geom
        return None


class CollectionSystem(NamedUserCreatedObject):
    class Meta(NamedUserCreatedObject.Meta):
        verbose_name = "waste collection system"

    def __str__(self):
        return self.name


class BinConfiguration(NamedUserCreatedObject):
    """How waste fractions are separated at the household level (e.g. separate bins, optical sorting)."""

    class Meta(NamedUserCreatedObject.Meta):
        verbose_name = "bin configuration"

    def __str__(self):
        return self.name


class WasteCategory(NamedUserCreatedObject):
    class Meta(NamedUserCreatedObject.Meta):
        verbose_name_plural = "waste categories"


class WasteComponentManager(MaterialManager):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(categories__name="Biowaste component")
            .distinct()
        )


class WasteComponent(Material):
    objects = WasteComponentManager()

    class Meta:
        proxy = True


@receiver(post_save, sender=WasteComponent)
def add_material_category(sender, instance, created, **kwargs):
    if created:
        category = MaterialCategory.objects.get(
            name="Biowaste component", owner=get_default_owner()
        )
        instance.categories.add(category)
        instance.save()


class WasteFlyerManager(UserCreatedObjectManager):
    def get_queryset(self):
        return super().get_queryset().filter(type="waste_flyer")

    def get_or_create_by_url(self, url: str, defaults: dict | None = None):
        flyer = self.filter(url=url).order_by("id").first()
        if flyer is not None:
            return flyer, False
        return self.get_or_create(url=url, defaults=defaults or {})


class WasteFlyer(Source):
    objects = WasteFlyerManager()

    class Meta:
        proxy = True
        verbose_name = "Waste Flyer"

    def __str__(self):
        if self.url:
            return self.url
        else:
            return ""


@receiver(pre_save, sender=WasteFlyer)
def set_source_type_and_check_url(sender, instance, **kwargs):
    instance.type = "waste_flyer"


@receiver(post_save, sender=WasteFlyer)
def check_url_valid(sender, instance, created, **kwargs):
    if created and instance.url and settings.AUTO_ENQUEUE_URL_CHECKS:
        transaction.on_commit(
            lambda: celery.current_app.send_task("check_wasteflyer_url", (instance.pk,))
        )


class CollectionSeasonManager(UserCreatedObjectManager):
    def get_queryset(self):
        # Filter by join instead of fetching owner and distribution eagerly:
        # get_queryset runs on every CollectionSeason.objects access, so those
        # two lookups cost two queries each time.
        username = getattr(settings, "DEFAULT_OBJECT_OWNER_USERNAME", None)
        if not username:
            username = getattr(settings, "ADMIN_USERNAME", None)
        if not username:
            raise RuntimeError(
                "Neither DEFAULT_OBJECT_OWNER_USERNAME in settings "
                "nor ADMIN_USERNAME env var is set."
            )
        return (
            super()
            .get_queryset()
            .filter(
                distribution__name="Months of the year",
                distribution__owner__username=username,
            )
        )


class CollectionSeason(Period):
    objects = CollectionSeasonManager()

    class Meta:
        proxy = True

    def __str__(self):
        return f"{self.first_timestep.name} - {self.last_timestep.name}"


FREQUENCY_TYPES = (
    ("Fixed", "Fixed"),
    ("Fixed-Flexible", "Fixed-Flexible"),
    ("Fixed-Seasonal", "Fixed-Seasonal"),
    ("Seasonal", "Seasonal"),
)


class CollectionFrequency(NamedUserCreatedObject):
    type = models.CharField(max_length=16, choices=FREQUENCY_TYPES, default="Fixed")
    seasons = models.ManyToManyField(CollectionSeason, through="CollectionCountOptions")

    class Meta(NamedUserCreatedObject.Meta):
        verbose_name_plural = "collection frequencies"

    @property
    def has_options(self):
        frequencies_with_options = CollectionCountOptions.objects.filter(
            Q(option_1__isnull=False)
            | Q(option_2__isnull=False)
            | Q(option_3__isnull=False)
        ).values_list("frequency")
        return self.id in [f[0] for f in frequencies_with_options]

    @property
    def seasonal(self):
        qs = CollectionFrequency.objects.annotate(season_count=Count("seasons")).filter(
            season_count__gt=1
        )
        return self in qs

    @property
    def collections_per_year(self):
        return self.collectioncountoptions_set.aggregate(Sum("standard"))[
            "standard__sum"
        ]


class CollectionCountOptions(UserCreatedObject):
    """
    The available options of how many collections  will be provided within a given season. Is used as 'through' model
    for the many-to-many relation of CollectionFrequency and CollectionSeason.
    """

    frequency = models.ForeignKey(
        CollectionFrequency, on_delete=models.CASCADE, null=False
    )
    season = models.ForeignKey(CollectionSeason, on_delete=models.CASCADE, null=False)
    standard = models.PositiveSmallIntegerField(blank=True, null=True)
    option_1 = models.PositiveSmallIntegerField(blank=True, null=True)
    option_2 = models.PositiveSmallIntegerField(blank=True, null=True)
    option_3 = models.PositiveSmallIntegerField(blank=True, null=True)

    class Meta(UserCreatedObject.Meta):
        verbose_name = "collection count options"
        verbose_name_plural = "collection count options"

    @property
    def non_standard_options(self):
        return [
            option for option in (self.option_1, self.option_2, self.option_3) if option
        ]


class FeeSystem(NamedUserCreatedObject):
    pass


YEAR_VALIDATOR = RegexValidator(
    r"^([0-9]{4})$", message="Year needs to be in YYYY format.", code="invalid year"
)


class CollectionQuerySet(UserCreatedObjectQuerySet):
    def valid_on(self, date):
        return self.filter(
            Q(valid_from__lte=date), Q(valid_until__gte=date) | Q(valid_until=None)
        )

    def currently_valid(self):
        return self.valid_on(timezone.now().date())

    def archived(self):
        return self.filter(valid_until__lt=timezone.now().date())

    @staticmethod
    def _normalize_material_ids(materials):
        if materials is None:
            return set()

        if hasattr(materials, "values_list"):
            return {
                int(material_id)
                for material_id in materials.values_list("id", flat=True)
                if material_id is not None
            }

        material_ids = set()
        for material in materials:
            material_id = getattr(material, "pk", material)
            if material_id is None:
                continue
            material_ids.add(int(material_id))
        return material_ids

    def match_allowed_materials(self, materials):
        """Return collections whose allowed_materials set exactly matches *materials*."""
        material_ids = self._normalize_material_ids(materials)

        if not material_ids:
            matching_ids = (
                self.annotate(_allowed_total=Count("allowed_materials", distinct=True))
                .filter(_allowed_total=0)
                .values("pk")
            )
            return self.filter(pk__in=matching_ids)

        matching_ids = (
            self.annotate(
                _allowed_total=Count("allowed_materials", distinct=True),
                _allowed_matched=Count(
                    "allowed_materials",
                    filter=Q(allowed_materials__in=material_ids),
                    distinct=True,
                ),
            )
            .filter(
                _allowed_total=len(material_ids),
                _allowed_matched=len(material_ids),
            )
            .values("pk")
        )
        return self.filter(pk__in=matching_ids)

    def match_forbidden_materials(self, materials):
        """Return collections whose forbidden_materials set exactly matches *materials*."""
        material_ids = self._normalize_material_ids(materials)

        if not material_ids:
            matching_ids = (
                self.annotate(
                    _forbidden_total=Count("forbidden_materials", distinct=True)
                )
                .filter(_forbidden_total=0)
                .values("pk")
            )
            return self.filter(pk__in=matching_ids)

        matching_ids = (
            self.annotate(
                _forbidden_total=Count("forbidden_materials", distinct=True),
                _forbidden_matched=Count(
                    "forbidden_materials",
                    filter=Q(forbidden_materials__in=material_ids),
                    distinct=True,
                ),
            )
            .filter(
                _forbidden_total=len(material_ids),
                _forbidden_matched=len(material_ids),
            )
            .values("pk")
        )
        return self.filter(pk__in=matching_ids)

    def match_materials(self, *, allowed_materials=None, forbidden_materials=None):
        """Return collections matching exact allowed/forbidden material combinations."""
        queryset = self
        if allowed_materials is not None:
            queryset = queryset.match_allowed_materials(allowed_materials)
        if forbidden_materials is not None:
            queryset = queryset.match_forbidden_materials(forbidden_materials)
        return queryset


PARTICIPATION_POLICY_CHOICES = [
    ("MANDATORY", "mandatory"),
    (
        "MANDATORY_WITH_HOME_COMPOSTER_EXCEPTION",
        "mandatory with exception for home composters",
    ),
    ("VOLUNTARY", "voluntary"),
    ("not_specified", "not specified"),
]

REQUIRED_BIN_CAPACITY_REFERENCE_CHOICES = [
    ("person", "per person"),
    ("person_week", "per person & week"),
    ("household", "per household"),
    ("property", "per property"),
    ("not_specified", "not specified"),
]


class Collection(NamedUserCreatedObject):
    """
    Represents a waste collection system, including collection parameters,
    inline waste category/materials, and container requirements.
    """

    collector = models.ForeignKey(
        Collector, on_delete=models.CASCADE, blank=True, null=True
    )
    catchment = models.ForeignKey(
        CollectionCatchment,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="collections",
    )
    collection_system = models.ForeignKey(
        CollectionSystem,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="collections",
    )
    waste_category = models.ForeignKey(
        WasteCategory,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="collections",
    )
    allowed_materials = models.ManyToManyField(
        Material,
        related_name="allowed_in_collections",
        blank=True,
    )
    forbidden_materials = models.ManyToManyField(
        Material,
        related_name="forbidden_in_collections",
        blank=True,
    )
    frequency = models.ForeignKey(
        CollectionFrequency,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="collections",
    )
    fee_system = models.ForeignKey(
        FeeSystem, on_delete=models.PROTECT, blank=True, null=True
    )
    samples = models.ManyToManyField(Sample, related_name="collections")
    flyers = models.ManyToManyField(
        WasteFlyer,
        related_name="collections",
    )
    sources = models.ManyToManyField(Source)

    valid_from = models.DateField(default=date.today)
    valid_until = models.DateField(blank=True, null=True)
    predecessors = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=False,
        related_name="successors",
    )
    bin_configuration = models.ForeignKey(
        BinConfiguration,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="collections",
        verbose_name="Bin configuration",
        help_text="How waste fractions are separated at the household level.",
    )
    established = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        verbose_name="Year established",
        help_text="Year when this collection scheme was first introduced.",
    )
    participation_policy = models.CharField(
        max_length=40,
        blank=True,
        null=True,
        choices=PARTICIPATION_POLICY_CHOICES,
        default=None,
        verbose_name="Participation policy",
        help_text="Indicates whether connection to the collection system is mandatory, voluntary, or not specified. Leave blank for never set; select 'not specified' for explicit user choice.",
    )
    access_control_bp = models.BooleanField(
        blank=True,
        null=True,
        default=None,
        verbose_name="Access control (BP)",
        help_text=(
            "Whether access to the bring-point (BP) collection infrastructure is "
            "controlled (e.g. by chip, key card, or lock). "
            "True = access-controlled; False = no access control; blank = not specified."
        ),
    )
    access_control_pap = models.BooleanField(
        blank=True,
        null=True,
        default=None,
        verbose_name="Access control (PAP)",
        help_text=(
            "Whether access to the door-to-door (PAP) container is controlled "
            "(e.g. by chip, key card, or lock). "
            "True = access-controlled; False = no access control; blank = not specified."
        ),
    )

    min_bin_size = models.DecimalField(
        blank=True,
        null=True,
        verbose_name="Smallest available bin size (L)",
        help_text="Smallest physical bin size that the collector provides for this collection. Exceprions may apply (e.g. for home composters)",
        max_digits=8,
        decimal_places=1,
        validators=[MinValueValidator(0)],
    )
    required_bin_capacity = models.DecimalField(
        blank=True,
        null=True,
        verbose_name="Minimum required specific bin capacity (L/reference unit)",
        help_text="Minimum total bin capacity that must be supplied per reference unit (see field below).",
        max_digits=8,
        decimal_places=1,
        validators=[MinValueValidator(0)],
    )
    required_bin_capacity_reference = models.CharField(
        max_length=16,
        blank=True,
        null=True,
        choices=REQUIRED_BIN_CAPACITY_REFERENCE_CHOICES,
        default=None,
        verbose_name="Reference unit for minimum required specific bin capacity",
        help_text="Defines the unit (person, household, property) for which the required bin capacity applies. Leave blank if not specified.",
    )

    objects = CollectionQuerySet.as_manager()

    class Meta(NamedUserCreatedObject.Meta):
        indexes = [
            models.Index(fields=["name", "id"], name="collection_name_id_idx"),
            # Meta.indexes replaces the abstract base's list, so the shared
            # publication_status index must be re-declared explicitly.
            models.Index(
                fields=["publication_status"], name="collection_pub_status_idx"
            ),
            # valid_until stays out: valid_on() ORs it with IS NULL, so it can
            # never become an index condition.
            models.Index(fields=["valid_from"], name="collection_valid_from_idx"),
        ]

    VERSION_REVIEW_FIELD_NAMES = (
        "catchment",
        "collector",
        "collection_system",
        "waste_category",
        "frequency",
        "fee_system",
        "bin_configuration",
        "allowed_materials",
        "forbidden_materials",
        "sources",
        "flyer_urls",
        "established",
        "participation_policy",
        "access_control_bp",
        "access_control_pap",
        "min_bin_size",
        "required_bin_capacity",
        "required_bin_capacity_reference",
        "description",
    )

    @property
    def geom(self):
        return self.catchment.geom

    @property
    def effective_waste_category(self):
        return self.waste_category

    @property
    def effective_allowed_materials(self):
        return self.allowed_materials.all()

    @property
    def effective_forbidden_materials(self):
        return self.forbidden_materials.all()

    @cached_property
    def version_chain_ids(self):
        """Return the set of primary keys connected through predecessors/successors."""

        visited = set()
        stack = [self]

        while stack:
            current = stack.pop()
            if not current.pk or current.pk in visited:
                continue

            visited.add(current.pk)

            stack.extend(current.predecessors.all())
            stack.extend(current.successors.all())

        return visited

    def all_versions(self):
        """Return a queryset with every version connected to this collection."""

        model = self.__class__

        if not self.version_chain_ids:
            return model.objects.none()

        return model.objects.filter(pk__in=self.version_chain_ids)

    @cached_property
    def version_anchor(self):
        """Return the canonical version used as anchor for shared statistics."""

        candidate_qs = self.all_versions().order_by("valid_from", "pk")

        for candidate in candidate_qs:
            if not candidate.predecessors.exists():
                return candidate

        return candidate_qs.first()

    @staticmethod
    def _deduplicate_property_values(values):
        """Return values without duplicates for the same property/unit/year key."""

        seen = set()
        ordered = []

        for value in values:
            key = (value.property_id, value.unit_id, value.year)
            if key in seen:
                continue

            seen.add(key)
            ordered.append(value)

        return ordered

    @classmethod
    def version_chains_for(cls, collection_ids):
        """Map each requested pk to the set of pks connected through versions.

        Walks the predecessor/successor graph breadth-first in batched queries
        instead of one traversal per collection.
        """

        through = cls.predecessors.through
        parent = {pk: pk for pk in collection_ids}

        def find(pk):
            while parent[pk] != pk:
                parent[pk] = parent[parent[pk]]
                pk = parent[pk]
            return pk

        frontier = set(parent)
        while frontier:
            edges = through.objects.filter(
                Q(from_collection_id__in=frontier) | Q(to_collection_id__in=frontier)
            ).values_list("from_collection_id", "to_collection_id")
            frontier = set()
            for left, right in edges:
                for pk in (left, right):
                    if pk not in parent:
                        parent[pk] = pk
                        frontier.add(pk)
                parent[find(left)] = find(right)

        chains = {}
        for pk in parent:
            chains.setdefault(find(pk), set()).add(pk)
        return {pk: chains[find(pk)] for pk in collection_ids}

    @staticmethod
    def visible_collectionpropertyvalues(collection_ids, user=None):
        """Return an ordered queryset of values on ``collection_ids`` visible to ``user``."""

        qs = (
            CollectionPropertyValue.objects.filter(collection_id__in=collection_ids)
            .select_related("property", "unit", "collection", "owner", "approved_by")
            .prefetch_related("sources")
        )

        qs = filter_queryset_for_user(qs, user)

        published_status = getattr(
            CollectionPropertyValue, "STATUS_PUBLISHED", "published"
        )
        user_id = getattr(user, "id", None)

        return qs.annotate(
            owner_order=Case(
                When(owner_id=user_id, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
            if user_id
            else Value(1),
            publication_order=Case(
                When(publication_status=published_status, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
        ).order_by(
            "property__name",
            "unit__name",
            "year",
            "owner_order",
            "publication_order",
            "-collection__valid_from",
            "-collection__pk",
            "pk",
        )

    def collectionpropertyvalues_for_display(self, user=None):
        """Return collection-specific property values visible to ``user`` across the chain."""

        return self._deduplicate_property_values(
            self.visible_collectionpropertyvalues(self.version_chain_ids, user)
        )

    @staticmethod
    def visible_aggregatedcollectionpropertyvalues(collection_ids, user=None):
        """Return an ordered queryset of aggregated values touching ``collection_ids``."""

        qs = (
            AggregatedCollectionPropertyValue.objects.filter(
                collections__in=collection_ids
            )
            .select_related("property", "unit", "owner", "approved_by")
            .prefetch_related("collections", "sources")
            .distinct()
        )

        qs = filter_queryset_for_user(qs, user)

        published_status = getattr(
            AggregatedCollectionPropertyValue, "STATUS_PUBLISHED", "published"
        )
        user_id = getattr(user, "id", None)

        return qs.annotate(
            owner_order=Case(
                When(owner_id=user_id, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
            if user_id
            else Value(1),
            publication_order=Case(
                When(publication_status=published_status, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
        ).order_by(
            "property__name",
            "unit__name",
            "year",
            "owner_order",
            "publication_order",
            "-created_at",
            "-pk",
        )

    def aggregatedcollectionpropertyvalues_for_display(self, user=None):
        """Return aggregated property values visible to ``user`` across the chain."""

        return list(
            self.visible_aggregatedcollectionpropertyvalues(
                self.version_chain_ids, user
            )
        )

    def construct_name(self):
        """
        Construct a descriptive name for the collection using catchment, waste category, system, and year.
        """
        catchment = self.catchment.name if self.catchment else "Unknown catchment"
        system = (
            self.collection_system.name
            if self.collection_system
            else "Unknown collection system"
        )
        category = "Unknown waste category"
        effective_waste_category = self.effective_waste_category
        if effective_waste_category:
            category = effective_waste_category.name
        return f"{catchment} {category} {system} {self.valid_from.year}"

    def clean(self):
        if self.valid_from and self.valid_until:
            if self.valid_from >= self.valid_until:
                raise ValidationError(
                    {
                        "valid_from": "Valid from date must be before the valid until date.",
                        "valid_until": "Valid until date must be after the valid from date.",
                    }
                )
        super().clean()

    def review_readiness_errors(self):
        return {}

    def validate_review_readiness(self):
        errors = self.review_readiness_errors()
        if errors:
            raise ValidationError(errors)

    def carried_over_version_review_fields(self):
        fields = []

        field_values = {
            "catchment": self.catchment_id,
            "collector": self.collector_id,
            "collection_system": self.collection_system_id,
            "waste_category": self.waste_category_id,
            "frequency": self.frequency_id,
            "fee_system": self.fee_system_id,
            "bin_configuration": self.bin_configuration_id,
            "established": self.established,
            "participation_policy": self.participation_policy,
            "access_control_bp": self.access_control_bp,
            "access_control_pap": self.access_control_pap,
            "min_bin_size": self.min_bin_size,
            "required_bin_capacity": self.required_bin_capacity,
            "required_bin_capacity_reference": self.required_bin_capacity_reference,
            "description": (self.description or "").strip(),
        }
        for field_name, value in field_values.items():
            if value not in (None, ""):
                fields.append(field_name)

        if self.allowed_materials.exists():
            fields.append("allowed_materials")
        if self.forbidden_materials.exists():
            fields.append("forbidden_materials")
        if self.sources.exists():
            fields.append("sources")
        if self.flyers.exclude(url__isnull=True).exclude(url="").exists():
            fields.append("flyer_urls")

        return fields

    def add_predecessor(self, predecessor):
        """
        Link *predecessor* to the current collection.

        The predecessor remains valid until this collection is published.
        Updating of ``valid_until`` is deferred to :meth:`approve`.
        """
        if not self.predecessors.filter(id=predecessor.id).exists():
            self.predecessors.add(predecessor)

    def submit_for_review(self):
        self.validate_review_readiness()
        return super().submit_for_review()

    def approve(self, user=None):
        """
        Publish the collection and archive predecessors, with concurrency check.

        Implements review-stage concurrency control:
        - For each predecessor, checks:
            - If predecessor.version_etag != self.branched_from_predecessor_etag, raises ValidationError.
            - If any other published successor exists, raises ValidationError.
        - Only after all checks, proceeds to publish self and archive predecessors.
        """

        with transaction.atomic():
            # Acquire row-level locks on predecessors deterministically to avoid races
            locked_predecessors_qs = self.predecessors.order_by(
                "pk"
            ).select_for_update()
            predecessors = list(locked_predecessors_qs)

            # Re-check after acquiring locks: ensure no other published successor exists
            for predecessor in predecessors:
                published_successors = predecessor.successors.filter(
                    publication_status="published"
                ).exclude(pk=self.pk)
                if published_successors.exists():
                    raise ValidationError(
                        "Another version based on this predecessor has already been published."
                    )

            super().approve(user=user)

            # Archive published predecessors after publishing self. Only
            # published rows may enter the public archive: archiving a
            # private, review or declined predecessor would expose an
            # unpublished draft. Governed approval goes through the shared
            # transition service so the archival is separately authorized
            # and audited under the lock already held above.
            for predecessor in predecessors:
                if predecessor.publication_status != self.STATUS_PUBLISHED:
                    continue
                if user is not None:
                    from utils.object_management.services import (
                        perform_transition,
                    )

                    perform_transition(
                        user,
                        predecessor,
                        "archive",
                        expected_revision=predecessor.content_revision,
                    )
                else:
                    predecessor.archive()

    @classmethod
    def public_map_url(cls):
        return reverse("WasteCollection")

    @classmethod
    def private_map_url(cls):
        return reverse("WasteCollection-owned")

    @classmethod
    def review_map_url(cls):
        return reverse("WasteCollection-review")

    def __str__(self):
        return self.name


@receiver(pre_save, sender=Collection)
def name_collection(sender, instance, **kwargs):
    instance.name = instance.construct_name()


@receiver(post_save, sender=WasteCategory)
@receiver(post_save, sender=CollectionSystem)
@receiver(post_save, sender=Catchment)
@receiver(post_save, sender=CollectionCatchment)
def update_collection_names(sender, instance, created, **kwargs):
    if not created:
        if sender == WasteCategory:
            collections = Collection.objects.filter(waste_category=instance)
        else:
            collections = instance.collections.all()
        with transaction.atomic():
            for collection in collections:
                collection.name = collection.construct_name()
                collection.save(update_fields=["name", "lastmodified_at"])


class CollectionPropertyValue(PropertyValue):
    sources = models.ManyToManyField(
        Source,
        blank=True,
        help_text="Sources or references for this property value.",
    )
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    year = models.PositiveSmallIntegerField(null=True, validators=[YEAR_VALIDATOR])
    is_derived = models.BooleanField(
        default=False,
        help_text="True when this value was computed from another property (e.g. total ↔ specific via population).",
    )
    derived_from = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="generated_values",
        null=True,
        blank=True,
        editable=False,
        help_text=(
            "The raw source value this generated projection is derived from. "
            "Server-controlled; set only by the derivation pipeline."
        ),
    )

    def get_breadcrumb_object_label(self):
        label = f"{self.property}: {self.display_average}"
        if self.standard_deviation:
            label += f" ± {self.display_standard_deviation}"
        return label

    @property
    def year_outside_collection_period(self):
        """True when ``year`` falls outside the collection's valid period.

        Statistics can describe a year the collection did not (or does not
        yet) cover; the UI flags those so readers do not misattribute the
        value's timeframe.
        """
        if self.year is None or self.collection_id is None:
            return False
        collection = self.collection
        if self.year < collection.valid_from.year:
            return True
        return bool(collection.valid_until and self.year > collection.valid_until.year)

    class Meta(PropertyValue.Meta):
        constraints = [
            # A source has exactly one generated output, bound by the
            # explicit derived_from link rather than the data key. Legacy
            # unlinked generated rows keep a NULL pointer.
            models.UniqueConstraint(
                fields=["derived_from"],
                condition=Q(is_derived=True, derived_from__isnull=False),
                name="wc_unique_generated_cpv_source",
            ),
            # A raw record can never carry a source pointer; generated rows
            # may keep a NULL pointer until provenance is audited (legacy).
            models.CheckConstraint(
                condition=Q(is_derived=True) | Q(derived_from__isnull=True),
                name="soilcom_cpv_raw_without_source_pointer",
            ),
        ]
        indexes = [
            models.Index(
                fields=["collection", "property", "year", "is_derived"],
                name="cpv_sync_lookup_idx",
            ),
        ]


class AggregatedCollectionPropertyValue(PropertyValue):
    collections = models.ManyToManyField(
        Collection,
    )
    sources = models.ManyToManyField(
        Source,
        blank=True,
        help_text="Sources or references for this property value.",
    )
    year = models.PositiveSmallIntegerField(null=True, validators=[YEAR_VALIDATOR])


def _schedule_wasteflyer_url_check(flyer_ids):
    """Schedule URL checks for the provided waste flyer ids after commit."""

    unique_flyer_ids = sorted({pk for pk in flyer_ids if pk})
    if not unique_flyer_ids:
        return

    def _enqueue_tasks():
        for flyer_id in unique_flyer_ids:
            celery.current_app.send_task("check_wasteflyer_url", (flyer_id,))

    transaction.on_commit(_enqueue_tasks)


def _waste_flyer_ids_for_pk_set(pk_set):
    """Return ids from ``pk_set`` that belong to WasteFlyers."""

    return list(WasteFlyer.objects.filter(pk__in=pk_set).values_list("pk", flat=True))


@receiver(m2m_changed, sender=Collection.flyers.through)
def check_collection_flyers_on_add(sender, action, pk_set, **kwargs):
    """Trigger URL checks whenever flyers are attached to a collection."""

    if action != "post_add" or not pk_set:
        return
    _schedule_wasteflyer_url_check(pk_set)


@receiver(m2m_changed, sender=CollectionPropertyValue.sources.through)
def check_collection_property_value_flyers_on_add(sender, action, pk_set, **kwargs):
    """Trigger URL checks for WasteFlyer sources attached to collection values."""

    if action != "post_add" or not pk_set:
        return
    flyer_ids = _waste_flyer_ids_for_pk_set(pk_set)
    _schedule_wasteflyer_url_check(flyer_ids)


@receiver(m2m_changed, sender=AggregatedCollectionPropertyValue.sources.through)
def check_aggregated_collection_property_value_flyers_on_add(
    sender, action, pk_set, **kwargs
):
    """Trigger URL checks for WasteFlyer sources attached to aggregated values."""

    if action != "post_add" or not pk_set:
        return
    flyer_ids = _waste_flyer_ids_for_pk_set(pk_set)
    _schedule_wasteflyer_url_check(flyer_ids)
