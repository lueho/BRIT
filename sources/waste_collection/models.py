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
from distributions.models import Period, TemporalDistribution
from maps.models import Catchment
from materials.models import Material, MaterialCategory, Sample
from utils.object_management.models import (
    NamedUserCreatedObject,
    UserCreatedObject,
    UserCreatedObjectManager,
    UserCreatedObjectQuerySet,
    get_default_owner,
)
from utils.object_management.permissions import filter_queryset_for_user
from utils.properties.models import PropertyValue


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
        db_table = "soilcom_collector"

    @property
    def geom(self):
        """Return the geometry from the associated catchment."""
        if self.catchment:
            return self.catchment.geom
        return None


class CollectionSystem(NamedUserCreatedObject):
    class Meta(NamedUserCreatedObject.Meta):
        verbose_name = "waste collection system"
        db_table = "soilcom_collectionsystem"

    def __str__(self):
        return self.name


class SortingMethod(NamedUserCreatedObject):
    """How waste fractions are separated at the household level (e.g. separate bins, optical sorting)."""

    class Meta(NamedUserCreatedObject.Meta):
        verbose_name = "sorting method"
        db_table = "soilcom_sortingmethod"

    def __str__(self):
        return self.name


class WasteCategory(NamedUserCreatedObject):
    class Meta(NamedUserCreatedObject.Meta):
        verbose_name_plural = "waste categories"
        db_table = "soilcom_wastecategory"


class WasteComponentManager(UserCreatedObjectManager):
    def get_queryset(self):
        return super().get_queryset().filter(categories__name="Biowaste component")


class WasteComponent(Material):
    objects = WasteComponentManager()

    class Meta:
        proxy = True


@receiver(post_save, sender=WasteComponent)
def add_material_category(sender, instance, created, **kwargs):
    if created:
        category = MaterialCategory.objects.get(name="Biowaste component")
        instance.categories.add(category)
        instance.save()


class WasteFlyerManager(UserCreatedObjectManager):
    def get_queryset(self):
        return super().get_queryset().filter(type="waste_flyer")


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
        distribution = TemporalDistribution.objects.get(
            owner=get_default_owner(), name="Months of the year"
        )
        return super().get_queryset().filter(distribution=distribution)


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
        db_table = "soilcom_collectionfrequency"

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
        db_table = "soilcom_collectioncountoptions"

    @property
    def non_standard_options(self):
        return [
            option for option in (self.option_1, self.option_2, self.option_3) if option
        ]


YEAR_VALIDATOR = RegexValidator(
    r"^([0-9]{4})$", message="Year needs to be in YYYY format.", code="invalid year"
)


class FeeSystem(NamedUserCreatedObject):
    class Meta(NamedUserCreatedObject.Meta):
        db_table = "soilcom_feesystem"


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


CONNECTION_TYPE_CHOICES = [
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
    ("per person & week"),
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
        db_table="soilcom_collection_allowed_materials",
    )
    forbidden_materials = models.ManyToManyField(
        Material,
        related_name="forbidden_in_collections",
        blank=True,
        db_table="soilcom_collection_forbidden_materials",
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
    samples = models.ManyToManyField(
        Sample, related_name="collections", db_table="soilcom_collection_samples"
    )
    flyers = models.ManyToManyField(
        WasteFlyer,
        related_name="collections",
        db_table="soilcom_collection_flyers",
    )
    sources = models.ManyToManyField(Source, db_table="soilcom_collection_sources")

    valid_from = models.DateField(default=date.today)
    valid_until = models.DateField(blank=True, null=True)
    predecessors = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=False,
        related_name="successors",
        db_table="soilcom_collection_predecessors",
    )
    sorting_method = models.ForeignKey(
        SortingMethod,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="collections",
        verbose_name="Sorting method",
        help_text="How waste fractions are separated at the household level.",
    )
    established = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        verbose_name="Year established",
        help_text="Year when this collection scheme was first introduced.",
    )
    connection_type = models.CharField(
        max_length=40,
        blank=True,
        null=True,
        choices=CONNECTION_TYPE_CHOICES,
        default=None,
        verbose_name="Connection type",
        help_text="Indicates whether connection to the collection system is mandatory, voluntary, or not specified. Leave blank for never set; select 'not specified' for explicit user choice.",
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
        db_table = "soilcom_collection"

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

    def collectionpropertyvalues_for_display(self, user=None):
        """Return collection-specific property values visible to ``user`` across the chain."""

        qs = (
            CollectionPropertyValue.objects.filter(collection__in=self.all_versions())
            .select_related("property", "unit", "collection", "owner", "approved_by")
            .prefetch_related("sources")
        )

        qs = filter_queryset_for_user(qs, user)

        published_status = getattr(
            CollectionPropertyValue, "STATUS_PUBLISHED", "published"
        )
        user_id = getattr(user, "id", None)

        qs = qs.annotate(
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

        return self._deduplicate_property_values(qs)

    def aggregatedcollectionpropertyvalues_for_display(self, user=None):
        """Return aggregated property values visible to ``user`` across the chain."""

        qs = (
            AggregatedCollectionPropertyValue.objects.filter(
                collections__in=self.all_versions()
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

        qs = qs.annotate(
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

        return list(qs)

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

    def add_predecessor(self, predecessor):
        """
        Link *predecessor* to the current collection.

        The predecessor remains valid until this collection is published.
        Updating of ``valid_until`` is deferred to :meth:`approve`.
        """
        if not self.predecessors.filter(id=predecessor.id).exists():
            self.predecessors.add(predecessor)

    def cascade_review_action(self, action_name, actor=None, previous_status=None):
        """Cascade review actions to property values across the collection chain."""
        versions = self.all_versions() if hasattr(self, "all_versions") else [self]
        actor_id = getattr(actor, "id", None)

        allowed_statuses = self._allowed_statuses_for_review_action(action_name)
        if not allowed_statuses:
            return

        cpv_qs = CollectionPropertyValue.objects.filter(collection__in=versions)
        cpv_qs = cpv_qs.filter(publication_status__in=allowed_statuses)

        if action_name in ("submit_for_review", "withdraw_from_review") and actor_id:
            cpv_qs = cpv_qs.filter(
                Q(owner_id=actor_id) | Q(collection__owner_id=actor_id)
            )

        cpv_list = list(cpv_qs.select_related("collection", "property", "unit"))

        agg_qs = AggregatedCollectionPropertyValue.objects.filter(
            collections__in=versions
        ).distinct()
        agg_qs = agg_qs.filter(publication_status__in=allowed_statuses)

        if action_name in ("submit_for_review", "withdraw_from_review") and actor_id:
            agg_qs = agg_qs.filter(owner_id=actor_id)

        agg_list = list(
            agg_qs.select_related("property", "unit").prefetch_related("collections")
        )

        self._apply_review_action_transition(
            cpv_list + agg_list, action_name, actor=actor
        )

    @staticmethod
    def _allowed_statuses_for_review_action(action_name):
        """Return which publication statuses should be affected by a review action."""
        if action_name == "submit_for_review":
            return ["private", "declined"]
        if action_name == "withdraw_from_review":
            return ["review"]
        if action_name in ("approve", "reject"):
            return ["review"]
        return []

    @staticmethod
    def _apply_review_action_transition(values, action_name, actor=None):
        """Apply the review action to each related value."""
        for value in values:
            action_method = getattr(value, action_name, None)
            if not callable(action_method):
                continue
            try:
                if action_name == "approve":
                    action_method(user=actor)
                else:
                    action_method()
            except Exception:
                continue

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

            # Archive all predecessors after publishing self
            for predecessor in predecessors:
                if predecessor.publication_status != "archived":
                    predecessor.publication_status = "archived"
                    predecessor.save(update_fields=["publication_status"])

    def reject(self):
        """Reject the collection and cascade to related property values in review."""

        from utils.object_management.models import UserCreatedObject

        review_status = UserCreatedObject.STATUS_REVIEW

        with transaction.atomic():
            pending_property_values = list(
                self.collectionpropertyvalue_set.filter(
                    publication_status=review_status
                )
            )
            pending_aggregated_values = list(
                self.aggregatedcollectionpropertyvalue_set.filter(
                    publication_status=review_status
                ).distinct()
            )

            super().reject()

            for value in pending_property_values:
                value.reject()

            for aggregated_value in pending_aggregated_values:
                aggregated_value.reject()

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
        for collection in collections:
            collection.name = collection.construct_name()
            collection.save(update_fields=["name", "lastmodified_at"])


class CollectionPropertyValue(PropertyValue):
    sources = models.ManyToManyField(
        Source,
        blank=True,
        help_text="Sources or references for this property value.",
        db_table="soilcom_collectionpropertyvalue_sources",
    )
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    year = models.PositiveSmallIntegerField(null=True, validators=[YEAR_VALIDATOR])
    is_derived = models.BooleanField(
        default=False,
        help_text="True when this value was computed from another property (e.g. total ↔ specific via population).",
    )

    class Meta(PropertyValue.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["collection", "property", "year"],
                condition=Q(is_derived=True),
                name="soilcom_unique_derived_cpv_per_key",
            ),
            models.UniqueConstraint(
                fields=["collection", "property"],
                condition=Q(is_derived=True, year__isnull=True),
                name="soilcom_unique_derived_cpv_per_key_null_year",
            ),
        ]
        db_table = "soilcom_collectionpropertyvalue"


class AggregatedCollectionPropertyValue(PropertyValue):
    collections = models.ManyToManyField(
        Collection,
        db_table="soilcom_aggregatedcollectionpropertyvalue_collections",
    )
    sources = models.ManyToManyField(
        Source,
        blank=True,
        help_text="Sources or references for this property value.",
        db_table="soilcom_aggregatedcollectionpropertyvalue_sources",
    )
    year = models.PositiveSmallIntegerField(null=True, validators=[YEAR_VALIDATOR])

    class Meta(PropertyValue.Meta):
        db_table = "soilcom_aggregatedcollectionpropertyvalue"


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
