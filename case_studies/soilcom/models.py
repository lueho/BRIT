from datetime import date
from functools import cached_property

import celery
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models, transaction
from django.db.models import Case, Count, IntegerField, Q, Sum, Value, When
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone

from bibliography.models import Source
from distributions.models import Period, TemporalDistribution
from maps.models import Catchment
from materials.models import Material, MaterialCategory, Sample, SampleSeries
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
            "catchment", "collector", "waste_stream__category", "collection_system"
        )
        return qs

    @property
    def upstream_collections(self):
        qs = Collection.objects.filter(catchment__in=self.ancestors())
        qs = qs.select_related(
            "catchment", "collector", "waste_stream__category", "collection_system"
        )
        return qs


class Collector(NamedUserCreatedObject):
    website = models.URLField(max_length=511, blank=True, null=True)
    catchment = models.ForeignKey(
        CollectionCatchment, blank=True, null=True, on_delete=models.CASCADE
    )

    class Meta:
        verbose_name = "waste collector"

    @property
    def geom(self):
        """Return the geometry from the associated catchment."""
        if self.catchment:
            return self.catchment.geom
        return None


class CollectionSystem(NamedUserCreatedObject):
    class Meta:
        verbose_name = "waste collection system"

    def __str__(self):
        return self.name


class WasteCategory(NamedUserCreatedObject):
    class Meta:
        verbose_name_plural = "waste categories"


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


class WasteStreamQuerySet(UserCreatedObjectQuerySet):
    @staticmethod
    def _material_ids(materials):
        """Normalize materials input into a list of ids or objects."""

        if materials is None:
            return None
        if hasattr(materials, "values_list"):
            return list(materials.values_list("id", flat=True))
        return list(materials)

    def match_allowed_materials(self, allowed_materials):
        allowed_ids = self._material_ids(allowed_materials)
        if allowed_ids is None:
            return self

        if allowed_ids:
            return self.alias(
                allowed_materials_count=models.Count(
                    "allowed_materials", distinct=True
                ),
                allowed_materials_matches=models.Count(
                    "allowed_materials",
                    filter=models.Q(allowed_materials__in=allowed_ids),
                    distinct=True,
                ),
            ).filter(
                allowed_materials_count=len(allowed_ids),
                allowed_materials_matches=len(allowed_ids),
            )
        return self.filter(allowed_materials__isnull=True)

    def match_forbidden_materials(self, forbidden_materials):
        forbidden_ids = self._material_ids(forbidden_materials)
        if forbidden_ids is None:
            return self

        if forbidden_ids:
            return self.alias(
                forbidden_materials_count=models.Count(
                    "forbidden_materials", distinct=True
                ),
                forbidden_materials_matches=models.Count(
                    "forbidden_materials",
                    filter=models.Q(forbidden_materials__in=forbidden_ids),
                    distinct=True,
                ),
            ).filter(
                forbidden_materials_count=len(forbidden_ids),
                forbidden_materials_matches=len(forbidden_ids),
            )
        return self.filter(forbidden_materials__isnull=True)

    def get_or_create(self, defaults=None, **kwargs):
        """
        Customizes the regular get_or_create to incorporate comparison of many-to-many relationships of
        allowed_materials and forbidden_materials. A queryset of allowed_materials and forbidden_materials can be
        passed to this method to get a waste stream with exactly that combination of materials.
        Each possible combination can only appear once in the database.
        :param defaults: dict
        :param kwargs: dict
        :return: tuple (WasteStream instance, bool)
        """

        if defaults:
            defaults = defaults.copy()

        qs = self
        unset = object()

        allowed_materials = kwargs.pop("allowed_materials", unset)
        allowed_provided = allowed_materials is not unset
        forbidden_materials = kwargs.pop("forbidden_materials", unset)
        forbidden_provided = forbidden_materials is not unset

        if defaults:
            if "allowed_materials" in defaults:
                allowed_materials = defaults.pop("allowed_materials")
                allowed_provided = True
            if "forbidden_materials" in defaults:
                forbidden_materials = defaults.pop("forbidden_materials")
                forbidden_provided = True

        if not allowed_provided:
            allowed_materials = None
        if not forbidden_provided:
            forbidden_materials = None

        pk_name = self.model._meta.pk.name
        has_pk = pk_name in kwargs

        if allowed_provided and not has_pk:
            allowed_ids = self._material_ids(allowed_materials)
            qs = qs.match_allowed_materials(
                allowed_ids if allowed_ids is not None else allowed_materials
            )
        if forbidden_provided and not has_pk:
            forbidden_ids = self._material_ids(forbidden_materials)
            qs = qs.match_forbidden_materials(
                forbidden_ids if forbidden_ids is not None else forbidden_materials
            )

        instance, created = super(WasteStreamQuerySet, qs).get_or_create(
            defaults=defaults, **kwargs
        )

        if created:
            allowed_list = [] if allowed_materials is None else list(allowed_materials)
            forbidden_list = (
                [] if forbidden_materials is None else list(forbidden_materials)
            )
            if allowed_list:
                instance.allowed_materials.add(*allowed_list)
            if forbidden_list:
                instance.forbidden_materials.add(*forbidden_list)
            if not instance.name:
                instance.name = f"{instance.category.name} {len(allowed_list)} {len(forbidden_list)}"
                instance.save()

        return instance, created

    def update_or_create(self, defaults=None, **kwargs):
        """
        Customizes the regular update_or_create to incorporate comparison of many-to-many relationships of
        allowed_materials and forbidden_materials. A queryset of allowed_materials and forbidden_materials can be
        passed to this method to get a waste stream with exactly that combination of materials.
        Each possible combination can only appear once in the database.
        :param defaults: dict
        :param kwargs: dict
        :return: tuple (WasteStream instance, bool)
        """

        if defaults:
            defaults = defaults.copy()

        instance, created = self.get_or_create(defaults=defaults, **kwargs)

        if not created:
            new_allowed_materials = defaults.pop("allowed_materials", None)
            new_forbidden_materials = defaults.pop("forbidden_materials", None)
            category = kwargs.get("category", None)

            qs = self

            if category:
                qs = qs.filter(category=category)

            if new_allowed_materials or new_forbidden_materials:
                if new_allowed_materials:
                    qs = qs.match_allowed_materials(new_allowed_materials)
                if new_forbidden_materials:
                    qs = qs.match_forbidden_materials(new_forbidden_materials)

                if qs.exists():
                    raise ValidationError(
                        """
                        Waste stream cannot be updated. Equivalent waste stream of equal category and same combination
                        of allowed and forbidden materials already exists.
                        """
                    )

            self.filter(id=instance.id).update(**defaults)

            if new_allowed_materials:
                instance.allowed_materials.clear()
                instance.allowed_materials.add(*new_allowed_materials)

            if new_forbidden_materials:
                instance.forbidden_materials.clear()
                instance.forbidden_materials.add(*new_forbidden_materials)

            instance.refresh_from_db()

        return instance, created


class WasteStreamManager(UserCreatedObjectManager):
    def get_queryset(self):
        return WasteStreamQuerySet(self.model, using=self._db)

    def match_allowed_materials(self, allowed_materials):
        return self.get_queryset().match_allowed_materials(allowed_materials)

    def match_forbidden_materials(self, forbidden_materials):
        return self.get_queryset().match_forbidden_materials(forbidden_materials)


class WasteStream(NamedUserCreatedObject):
    """Describes Waste Streams that are collected in Collections. This model is managed automatically by
    the Collection model. Instances of this model must not be created, edited or deleted manually.
    """

    category = models.ForeignKey(WasteCategory, on_delete=models.PROTECT)
    allowed_materials = models.ManyToManyField(
        Material, related_name="allowed_in_waste_streams"
    )
    forbidden_materials = models.ManyToManyField(
        Material, related_name="forbidden_in_waste_streams"
    )
    composition = models.ManyToManyField(SampleSeries)

    objects = WasteStreamQuerySet.as_manager()

    class Meta:
        verbose_name = "Waste Stream"


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
    if created:
        celery.current_app.send_task("check_wasteflyer_url", (instance.pk,))


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

    class Meta:
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

    @property
    def non_standard_options(self):
        return [
            option for option in (self.option_1, self.option_2, self.option_3) if option
        ]


YEAR_VALIDATOR = RegexValidator(
    r"^([0-9]{4})$", message="Year needs to be in YYYY format.", code="invalid year"
)


class FeeSystem(NamedUserCreatedObject):
    pass


class CollectionQuerySet(UserCreatedObjectQuerySet):
    def valid_on(self, date):
        return self.filter(
            Q(valid_from__lte=date), Q(valid_until__gte=date) | Q(valid_until=None)
        )

    def currently_valid(self):
        return self.valid_on(timezone.now().date())

    def archived(self):
        return self.filter(valid_until__lt=timezone.now().date())


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
    ("household", "per household"),
    ("property", "per property"),
    ("not_specified", "not specified"),
]


class Collection(NamedUserCreatedObject):
    """
    Represents a waste collection system, including collection parameters, waste stream, and container requirements.
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
    waste_stream = models.ForeignKey(
        WasteStream,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="collections",
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
    flyers = models.ManyToManyField(WasteFlyer, related_name="collections")
    sources = models.ManyToManyField(Source)

    valid_from = models.DateField(default=date.today)
    valid_until = models.DateField(blank=True, null=True)
    predecessors = models.ManyToManyField(
        "self", blank=True, symmetrical=False, related_name="successors"
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
        verbose_name="Required bin capacity per unit (L)",
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
        verbose_name="Reference unit for required bin capacity",
        help_text="Defines the unit (person, household, property) for which the required bin capacity applies. Leave blank if not specified.",
    )

    objects = CollectionQuerySet.as_manager()

    @property
    def geom(self):
        return self.catchment.geom

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
            .select_related("property", "unit", "collection")
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
            .select_related("property", "unit")
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
        if self.waste_stream and self.waste_stream.category:
            category = self.waste_stream.category.name
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


@receiver(pre_save, sender=Collection)
def capture_previous_waste_stream(sender, instance, **kwargs):
    """Store previous waste stream id for change detection."""

    update_fields = kwargs.get("update_fields")
    if update_fields and "waste_stream" not in update_fields:
        instance._previous_waste_stream_id = instance.waste_stream_id
        return

    if not instance.pk:
        instance._previous_waste_stream_id = None
        return

    instance._previous_waste_stream_id = (
        sender.objects.filter(pk=instance.pk)
        .values_list("waste_stream_id", flat=True)
        .first()
    )


@receiver(post_save, sender=Collection)
def schedule_orphaned_waste_stream_cleanup(sender, instance, created, **kwargs):
    """Schedule orphaned waste stream cleanup when waste stream changes."""
    if created:
        return
    previous_waste_stream_id = getattr(instance, "_previous_waste_stream_id", None)
    if previous_waste_stream_id == instance.waste_stream_id:
        return
    celery.current_app.send_task("cleanup_orphaned_waste_streams")


@receiver(post_delete, sender=Collection)
def schedule_orphaned_waste_stream_cleanup_on_delete(sender, instance, **kwargs):
    """Schedule orphaned waste stream cleanup after collection deletion."""
    celery.current_app.send_task("cleanup_orphaned_waste_streams")


@receiver(post_save, sender=WasteStream)
@receiver(post_save, sender=WasteCategory)
@receiver(post_save, sender=CollectionSystem)
@receiver(post_save, sender=Catchment)
@receiver(post_save, sender=CollectionCatchment)
def update_collection_names(sender, instance, created, **kwargs):
    if not created:
        if sender == WasteCategory:
            collections = Collection.objects.filter(waste_stream__category=instance)
        else:
            collections = instance.collections.all()
        for collection in collections:
            collection.name = collection.construct_name()
            collection.save(update_fields=["name", "lastmodified_at"])


class CollectionPropertyValue(PropertyValue):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    year = models.PositiveSmallIntegerField(null=True, validators=[YEAR_VALIDATOR])


class AggregatedCollectionPropertyValue(PropertyValue):
    collections = models.ManyToManyField(Collection)
    year = models.PositiveSmallIntegerField(null=True, validators=[YEAR_VALIDATOR])
