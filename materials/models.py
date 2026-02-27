from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Max
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse

from bibliography.models import Source
from distributions.models import TemporalDistribution, Timestep
from utils.object_management.models import (
    NamedUserCreatedObject,
    UserCreatedObject,
    UserCreatedObjectManager,
    get_default_owner,
)
from utils.properties.models import PropertyBase, Unit, get_default_unit_pk


class MaterialComponentKind(models.TextChoices):
    SINGLE = "single", "Single component"
    AGGREGATE = "aggregate", "Aggregate component"


class MaterialPropertyAggregationKind(models.TextChoices):
    MASS_RELATED = "mass_related", "Mass-related"
    NON_MASS_RELATED = "non_mass_related", "Non mass-related"


def get_sample_substrate_category_name():
    """Return the configured substrate category name used for sample filtering."""
    return getattr(settings, "SAMPLE_SUBSTRATE_CATEGORY_NAME", "Bioresource")


class MaterialCategory(NamedUserCreatedObject):
    pass


def get_or_create_sample_substrate_category():
    """Return the configured substrate category, creating it when missing."""
    return MaterialCategory.objects.get_or_create(
        name=get_sample_substrate_category_name(),
        defaults={
            "description": "Category for substrate materials used in sample filtering.",
            "publication_status": "published",
        },
    )


class BaseMaterial(NamedUserCreatedObject):
    """
    Base for all specialized models of material
    """

    type = models.CharField(max_length=127, default="material")
    abbreviation = models.CharField(
        max_length=50,
        blank=True,
        help_text="Short abbreviation or acronym for this material/component.",
    )
    categories = models.ManyToManyField(MaterialCategory, blank=True)
    component_kind = models.CharField(
        max_length=20,
        choices=MaterialComponentKind.choices,
        default=MaterialComponentKind.SINGLE,
        blank=True,
        help_text="Only used for material components: single components versus aggregate groups.",
    )
    basis_component = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="derived_components",
        null=True,
        blank=True,
        limit_choices_to={"type": "component"},
        help_text=(
            "Basis component for this component (e.g. Dry Matter). Only used for components."
        ),
    )

    class Meta:
        verbose_name = "Material"
        unique_together = [["name", "owner"]]


class MaterialManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(type="material")


class Material(BaseMaterial):
    """
    Generic material class for many purposes. E.g. this is used as top level definition to link semantic definition of
    materials with analysis data.
    """

    class Meta:
        proxy = True


class MaterialComponentManager(UserCreatedObjectManager):
    def default(self):
        name = getattr(settings, "DEFAULT_MATERIAL_NAME", "Fresh Matter (FM)")
        return self.get_queryset().get(name=name, owner=get_default_owner())

    def other(self):
        name = getattr(settings, "DEFAULT_OTHER_MATERIAL_NAME", "Other")
        return self.get_queryset().get_or_create(name=name, owner=get_default_owner())[
            0
        ]


class MaterialComponent(BaseMaterial):
    """
    Component class of a material for which a weight fraction can be assigned but which cannot itself be defined as a
    material (e.g. total solids, volatile solids, etc.)
    """

    objects = MaterialComponentManager()

    class Meta:
        proxy = True
        verbose_name = "component"
        ordering = ["name"]


@receiver(post_save, sender=MaterialComponent)
def add_type_component(sender, instance, created, **kwargs):
    if created:
        instance.type = "component"
        instance.save()


class MaterialComponentGroupManager(UserCreatedObjectManager):
    def default(self):
        name = getattr(
            settings, "DEFAULT_MATERIALCOMPONENTGROUP_NAME", "Total Material"
        )
        return self.get_queryset().get_or_create(name=name)[0]


class MaterialComponentGroup(NamedUserCreatedObject):
    """
    Definition of a group of components that belong together to form a composition which can be described with
    weight fractions. E.g. Macro component, chemical elements, etc. The actual composition is described in its own
    model: Composition. This is a container that allows to identify comparable compositions.
    """

    objects = MaterialComponentGroupManager()

    class Meta:
        unique_together = [["name", "owner"]]


class AnalyticalMethod(NamedUserCreatedObject):
    """
    Represents an analytical method or laboratory procedure.

    - ontology_uri: if provided, points to an external ontology (e.g. CHMO/OBI) where method details are maintained.
    - technique, standard, instrument_type, and lower_detection_limit are available as local overrides.

    In a more elaborate workflow, you can add helper functions to dynamically fetch
    and cache external metadata based on the provided ontology URI.
    """

    ontology_uri = models.URLField(
        blank=True,
        null=True,
        help_text="External ontology URI (e.g., CHMO term) for this analytical method.",
    )
    technique = models.CharField(
        max_length=100,
        blank=True,
        help_text="Analytical technique (e.g., ICP-OES, Gravimetry).",
    )
    standard = models.CharField(
        max_length=100,
        blank=True,
        help_text="Standard or protocol (e.g., DIN EN 15936).",
    )
    instrument_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Type of instrument used (local override if not fetched externally).",
    )
    lower_detection_limit = models.CharField(
        max_length=50,
        blank=True,
        help_text="Lower detection limit (e.g., '0.5 mg/kg').",
    )
    sources = models.ManyToManyField(
        Source,
        blank=True,
        help_text="Sources or references for this analytical method.",
    )

    class Meta:
        verbose_name = "Analytical Method"
        verbose_name_plural = "Analytical Methods"

    def __str__(self):
        if self.ontology_uri:
            return f"{self.name} (Ont: {self.ontology_uri})"
        return self.name

    @property
    def external_metadata(self):
        """
        Placeholder for a method to retrieve external metadata from the linked ontology.
        In a later workflow, implement an API call (e.g., via OLS or BioPortal) to fetch
        metadata based on self.ontology_uri. You might cache the results locally.
        """
        return {}  # TODO: Implement external metadata retrieval

    def cascade_review_action(self, action_name, actor=None, previous_status=None):
        """Cascade review actions to linked sources.

        Analytical method review actions are propagated to all linked sources so
        reviewers can access collaborator references in the review UI.
        """
        action_map = {
            "submit_for_review": {
                "from": [
                    UserCreatedObject.STATUS_PRIVATE,
                    UserCreatedObject.STATUS_DECLINED,
                ],
                "handler": "submit_for_review",
            },
            "withdraw_from_review": {
                "from": [UserCreatedObject.STATUS_REVIEW],
                "handler": "withdraw_from_review",
            },
            "approve": {
                "from": [UserCreatedObject.STATUS_REVIEW],
                "handler": "approve",
            },
            "reject": {
                "from": [UserCreatedObject.STATUS_REVIEW],
                "handler": "reject",
            },
        }
        config = action_map.get(action_name)
        if not config:
            return

        sources_qs = self.sources.filter(
            publication_status__in=config["from"],
        )
        for source in sources_qs:
            action = getattr(source, config["handler"], None)
            if not callable(action):
                continue
            try:
                if action_name == "approve" and actor is not None:
                    action(user=actor)
                else:
                    action()
            except Exception:
                continue


class SampleSeries(NamedUserCreatedObject):
    """
    Sample series are used to add concrete experimental data to the abstract semantic definition of materials. A sample
    series consists of several samples that are taken from a comparable source at different times. That way a temporal
    distribution of material properties and compositions over time can be described.
    """

    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name="sample_series",
    )
    image = models.ImageField(
        upload_to="materials_sampleseries/", blank=True, null=True
    )
    publish = models.BooleanField(default=False)
    standard = models.BooleanField(default=True)
    temporal_distributions = models.ManyToManyField(TemporalDistribution)

    def add_component_group(self, group, fractions_of=None):
        """Adds compositions of a component group to all samples of this sample series."""
        if not fractions_of:
            fractions_of = MaterialComponent.objects.default()
        for sample in self.samples.all():
            Composition.objects.create(
                owner=self.owner, group=group, sample=sample, fractions_of=fractions_of
            )

    def remove_component_group(self, group):
        """Removes all compositions of a component group from all samples of this sample series."""
        for sample in self.samples.all():
            Composition.objects.filter(sample=sample, group=group).delete()

    def add_component(self, component, group):
        """Creates WeightShare objects for a new component for all samples of a SampleSeries at once."""
        for sample in self.samples.all():
            for composition in sample.compositions.filter(group=group):
                composition.add_component(component)

    def remove_component(self, component, group):
        """Removes all WeightShare objects of a given component and component group"""
        for sample in self.samples.all():
            for composition in sample.compositions.filter(group=group):
                composition.remove_component(component)

    def add_temporal_distribution(self, distribution):
        """
        Adds the temporal distribution to the m2m field and also creates shares for all timesteps of the distribution
        for all components of this group.
        """
        # In case this method is called manually and not by m2m_changed
        if distribution not in self.temporal_distributions.all():
            self.temporal_distributions.add(distribution)

        # Use average and standard deviation of component averages as default values for all timesteps
        for timestep in distribution.timestep_set.all():
            Sample.objects.create(
                owner=self.owner, material=self.material, series=self, timestep=timestep
            )

    def remove_temporal_distribution(self, distribution):
        """
        Removes the temporal distribution from the m2m field and also cleans up all related composition sets and shares.
        """
        if distribution in self.temporal_distributions.all():
            for timestep in distribution.timestep_set.all():
                self.samples.filter(timestep=timestep).delete()
            self.temporal_distributions.remove(distribution)

    @property
    def components(self):
        """
        Queryset of all components that have been assigned to this group.
        """
        return MaterialComponent.objects.filter(
            id__in=[
                share["component"]
                for share in WeightShare.objects.filter(
                    composition__sample__series=self
                )
                .values("component")
                .distinct()
            ]
        )

    @property
    def component_groups(self):
        return MaterialComponentGroup.objects.filter(
            id__in=[
                composition["group"]
                for composition in Composition.objects.filter(sample__series=self)
                .exclude(id=MaterialComponentGroup.objects.default().id)
                .values("group")
                .distinct()
            ]
        )

    @property
    def group_ids(self):
        """
        Ids of component groups that have been assigned to this material.
        """
        return [
            setting["group"]
            for setting in Composition.objects.filter(sample__series=self)
            .values("group")
            .distinct()
        ]

    @property
    def blocked_ids(self):
        """
        Returns a list of group ids that cannot be added to the material because they are already assigned.
        """
        return self.group_ids

    @property
    def shares(self):
        return WeightShare.objects.filter(composition__sample__series=self)

    def duplicate(self, creator, **kwargs):
        post_save.disconnect(add_default_temporal_distribution, sender=SampleSeries)

        duplicate = SampleSeries.objects.create(
            owner=creator,
            name=kwargs.get("name", self.name),
            material=kwargs.get("material", self.material),
        )

        for sample in self.samples.all():
            sample_duplicate = sample.duplicate(creator)
            sample_duplicate.series = duplicate
            sample_duplicate.save()

        duplicate.temporal_distributions.set(self.temporal_distributions.all())

        post_save.connect(add_default_temporal_distribution, sender=SampleSeries)

        return duplicate

    @property
    def full_name(self):
        return f"{self.material.name} {self.name}"

    @property
    def group_settings(self):
        return Composition.objects.filter(sample__series=self).exclude(
            group=MaterialComponentGroup.objects.default()
        )


@receiver(post_save, sender=SampleSeries)
def add_default_temporal_distribution(sender, instance, created, **kwargs):
    if created:
        instance.add_temporal_distribution(TemporalDistribution.objects.default())


class MaterialProperty(PropertyBase):
    """Materials-specific property definition."""

    abbreviation = models.CharField(max_length=50, blank=True)
    group = models.ForeignKey(
        "MaterialPropertyGroup",
        on_delete=models.PROTECT,
        related_name="properties",
        null=True,
        blank=True,
        help_text=(
            "Aggregation domain used to avoid double-counting overlapping measurements."
        ),
    )
    aggregation_kind = models.CharField(
        max_length=30,
        choices=MaterialPropertyAggregationKind.choices,
        default=MaterialPropertyAggregationKind.NON_MASS_RELATED,
    )
    default_basis_component = models.ForeignKey(
        MaterialComponent,
        on_delete=models.PROTECT,
        related_name="default_basis_properties",
        null=True,
        blank=True,
        help_text=(
            "Mass basis component used to normalize this property (e.g. Dry Matter)."
        ),
    )
    allowed_units = models.ManyToManyField(
        Unit,
        blank=True,
        help_text="Units that are acceptable for this property.",
    )

    def __str__(self):
        return f"{self.name} [{self.unit}]"


class MaterialPropertyGroup(NamedUserCreatedObject):
    """Aggregation domain for material properties to prevent double-counting."""

    class Meta:
        unique_together = [["name", "owner"]]


class MaterialPropertyValue(UserCreatedObject):
    property = models.ForeignKey(MaterialProperty, on_delete=models.PROTECT)
    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        default=get_default_unit_pk,
        help_text="Unit for the measured value.",
    )
    analytical_method = models.ForeignKey(
        AnalyticalMethod,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Analytical method used for this measurement.",
    )
    sources = models.ManyToManyField(
        Source,
        blank=True,
        help_text="Sources or references for this measurement.",
    )
    average = models.DecimalField(max_digits=20, decimal_places=10)
    standard_deviation = models.DecimalField(max_digits=20, decimal_places=10)

    def duplicate(self, creator):
        duplicate = MaterialPropertyValue.objects.create(
            owner=creator,
            property=self.property,
            unit=self.unit,
            analytical_method=self.analytical_method,
            average=self.average,
            standard_deviation=self.standard_deviation,
        )
        duplicate.sources.set(self.sources.all())

        return duplicate


class Sample(NamedUserCreatedObject):
    """
    Representation of a single sample that was taken at a specific location and time. Equivalent samples are associated
    with a SampleSeries to temporal distribution of properties and composition.
    """

    image = models.ImageField(upload_to="materials_sample/", blank=True, null=True)
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name="samples",
        help_text='If no option fits, please choose "Other" and specify the material in the description.',
    )
    datetime = models.DateTimeField(
        blank=True, null=True, help_text="Choose 00:00 if time is unknown."
    )
    location = models.CharField(
        max_length=511,
        blank=True,
        null=True,
        help_text="Name of town, address or coordinates",
    )
    analysis_date = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Date when the analysis was performed.",
    )
    analysis_laboratory = models.CharField(
        max_length=255,
        blank=True,
        help_text="Laboratory where the analysis was performed.",
    )
    lab_accreditation = models.CharField(
        max_length=255,
        blank=True,
        help_text="Laboratory accreditation information.",
    )
    analysis_objective = models.TextField(
        blank=True,
        help_text="Objective or purpose of the analysis.",
    )
    series = models.ForeignKey(
        SampleSeries,
        related_name="samples",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text="If this sample belongs to a sample series or campaign, select it here.",
    )
    standalone = models.BooleanField(
        default=False,
        help_text="True if this sample is not part of a sample series.",
    )
    timestep = models.ForeignKey(
        Timestep,
        related_name="samples",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        help_text="If the sample represents a specific time step in a series, select it here.",
    )
    sources = models.ManyToManyField(Source)
    properties = models.ManyToManyField(MaterialPropertyValue)

    @property
    def group_ids(self):
        """
        Ids of component groups that have been assigned to this sample.
        """
        return [
            setting["group"]
            for setting in Composition.objects.filter(sample=self)
            .values("group")
            .distinct()
        ]

    @property
    def components(self):
        """
        Queryset of all components that have been assigned to this group.
        """
        return MaterialComponent.objects.filter(
            id__in=[
                share["component"]
                for share in WeightShare.objects.filter(composition__sample=self)
                .values("component")
                .distinct()
            ]
        )

    def duplicate(self, creator, **kwargs):
        post_save.disconnect(add_default_composition, sender=Sample)
        duplicate = Sample.objects.create(
            owner=creator,
            name=kwargs.get("name", f"{self.name} (copy)"),
            description=kwargs.get("description", self.description),
            material=kwargs.get("material", self.material),
            series=kwargs.get("series", self.series),
            timestep=kwargs.get("timestep", self.timestep),
            datetime=kwargs.get("datetime", self.datetime),
            location=kwargs.get("location", self.location),
            analysis_date=kwargs.get("analysis_date", self.analysis_date),
            analysis_laboratory=kwargs.get(
                "analysis_laboratory", self.analysis_laboratory
            ),
            lab_accreditation=kwargs.get("lab_accreditation", self.lab_accreditation),
            analysis_objective=kwargs.get(
                "analysis_objective", self.analysis_objective
            ),
            standalone=kwargs.get("standalone", self.standalone),
        )
        post_save.connect(add_default_composition, sender=Sample)
        for composition in self.compositions.all():
            duplicate_composition = composition.duplicate(creator)
            duplicate_composition.sample = duplicate
            duplicate_composition.save()

        for prop in self.properties.all():
            duplicate.properties.add(prop.duplicate(creator))

        for measurement in self.component_measurements.all():
            measurement.duplicate(creator, sample=duplicate)

        return duplicate


@receiver(post_save, sender=Sample)
def add_default_composition(sender, instance, created, **kwargs):
    if created:
        composition = Composition.objects.create(
            owner=instance.owner,
            group=MaterialComponentGroup.objects.default(),
            sample=instance,
            fractions_of=MaterialComponent.objects.default(),
        )
        composition.add_component(MaterialComponent.objects.default(), average=1.0)


class Composition(NamedUserCreatedObject):
    """
    Utility model to store the settings for component groups for each material in each customization. This model is not
    supposed to be edited directly by a user. It depends on user objects and must be deleted, when any of the user
    objects it depends on is deleted.
    """

    sample = models.ForeignKey(
        Sample,
        related_name="compositions",
        on_delete=models.CASCADE,
        help_text="The sample that this composition is part of.",
    )
    group = models.ForeignKey(
        MaterialComponentGroup,
        related_name="compositions",
        on_delete=models.PROTECT,
        help_text="The group of components that this composition is part of. Typically determined by type of analysis.",
    )
    fractions_of = models.ForeignKey(
        MaterialComponent,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="The component that the weight fractions of this composition are fractions of. Must be a component that is already defined.",
    )
    order = models.IntegerField(default=90)

    class Meta:
        ordering = ["order"]

    @property
    def material(self):
        return self.sample.material

    @property
    def timestep(self):
        return self.sample.timestep

    @property
    def component_ids(self):
        """
        Ids of all material components that have been assigned to this group.
        """
        return [
            share["component"] for share in self.shares.values("component").distinct()
        ]

    @property
    def components(self):
        """
        Queryset of all components that have been assigned to this group.
        """
        return MaterialComponent.objects.filter(id__in=self.component_ids)

    @property
    def blocked_component_ids(self):
        """
        Returns a list of ids that cannot be added to the group because they are either already assigned to the group
        or would create a circular reference.
        """
        ids = self.component_ids
        ids.append(self.fractions_of.id)
        ids.append(self.material.id)
        return ids

    @property
    def blocked_distribution_ids(self):
        return [dist.id for dist in self.sample.series.temporal_distributions.all()]

    def add_component(self, component, **kwargs):
        """
        Convenience method to create a correct WeightShare object with correct for this model.
        """
        return WeightShare.objects.create(
            owner=self.owner,
            component=component,
            composition=self,
            average=kwargs.setdefault("average", 0.0),
            standard_deviation=kwargs.setdefault("standard_deviation", 0.0),
        )

    def remove_component(self, component):
        """
        Removes the component from all compositions in which it appears.
        """
        self.shares.filter(component=component).delete()

    def add_temporal_distribution(self, distribution):
        """
        Adds the temporal distribution to the m2m field and also creates shares for all timesteps of the distribution
        for all components of this group.
        """
        self.sample.series.add_temporal_distribution(distribution)

    def remove_temporal_distribution(self, distribution):
        """
        Removes the temporal distribution from the m2m field and also cleans up all related composition sets and shares.
        """
        self.sample.series.remove_temporal_distribution(distribution)

    def order_up(self):
        current_order = self.order
        next_composition = (
            self.sample.compositions.filter(order__gt=self.order)
            .order_by("order")
            .first()
        )
        if next_composition:
            self.order = next_composition.order
            next_composition.order = current_order
            next_composition.save()
            self.save()

    def order_down(self):
        current_order = self.order
        previous_composition = (
            self.sample.compositions.filter(order__lt=self.order)
            .order_by("-order")
            .first()
        )
        if previous_composition:
            self.order = previous_composition.order
            previous_composition.order = current_order
            previous_composition.save()
            self.save()

    def duplicate(self, creator):
        post_save.disconnect(add_next_order_value, sender=Composition)
        duplicate = Composition.objects.create(
            owner=creator,
            group=self.group,
            sample=self.sample,
            fractions_of=self.fractions_of,
            order=self.order,
        )
        post_save.connect(add_next_order_value, sender=Composition)
        for share in self.shares.all():
            duplicate_share = share.duplicate(creator)
            duplicate_share.composition = duplicate
            duplicate_share.save()

        return duplicate

    def get_absolute_url(self):
        return self.sample.get_absolute_url()

    def __str__(self):
        return f"Composition of {self.group.name} of sample {self.sample.name}"


class ComponentMeasurement(UserCreatedObject):
    """Raw (unnormalized) component measurements for a sample."""

    sample = models.ForeignKey(
        Sample,
        related_name="component_measurements",
        on_delete=models.CASCADE,
        help_text="The sample these measurements belong to.",
    )
    group = models.ForeignKey(
        MaterialComponentGroup,
        related_name="component_measurements",
        on_delete=models.PROTECT,
        help_text="Grouping domain for the measurement (e.g. chemical elements).",
    )
    component = models.ForeignKey(
        MaterialComponent,
        related_name="component_measurements",
        on_delete=models.PROTECT,
    )
    basis_component = models.ForeignKey(
        MaterialComponent,
        related_name="basis_component_measurements",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Basis component for the measurement (e.g. Dry Matter).",
    )
    analytical_method = models.ForeignKey(
        AnalyticalMethod,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Analytical method used for this measurement.",
    )
    sources = models.ManyToManyField(
        Source,
        blank=True,
        help_text="Sources or references for this measurement.",
    )
    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        default=get_default_unit_pk,
        help_text="Unit for the measured value (e.g. %, g/kg).",
    )
    average = models.DecimalField(
        max_digits=20, decimal_places=10, default=Decimal("0.0"), null=False
    )
    standard_deviation = models.DecimalField(
        max_digits=20, decimal_places=10, default=Decimal("0.0"), null=False
    )
    sample_size = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of samples/replicates (n) used for the measurement.",
    )
    comment = models.TextField(
        blank=True,
        help_text="Additional comments about the measurement.",
    )

    class Meta:
        ordering = ["component__name", "id"]

    def duplicate(self, creator, sample=None):
        duplicate = ComponentMeasurement.objects.create(
            owner=creator,
            sample=sample or self.sample,
            group=self.group,
            component=self.component,
            basis_component=self.basis_component,
            analytical_method=self.analytical_method,
            unit=self.unit,
            average=self.average,
            standard_deviation=self.standard_deviation,
            sample_size=self.sample_size,
            comment=self.comment,
        )
        duplicate.sources.set(self.sources.all())
        return duplicate

    def __str__(self):
        return f"Raw measurement of {self.component.name} for sample {self.sample.name}"


@receiver(pre_save, sender=Composition)
def set_default_material(sender, instance, **kwargs):
    if instance.fractions_of is None:
        instance.fractions_of = MaterialComponent.objects.default()


@receiver(post_save, sender=Composition)
def add_next_order_value(sender, instance, created, **kwargs):
    if created:
        compositions = Composition.objects.filter(sample=instance.sample)
        instance.order = compositions.aggregate(Max("order"))["order__max"] + 10
        instance.save()


class WeightShare(NamedUserCreatedObject):
    """
    Holds the actual values of weight fractions that are part of any material composition. This model is not edited
    directly to maintain consistency within compositions. Use API of Composition instead.
    """

    component = models.ForeignKey(
        MaterialComponent, related_name="shares", on_delete=models.CASCADE
    )
    composition = models.ForeignKey(
        Composition, related_name="shares", on_delete=models.CASCADE
    )
    average = models.DecimalField(
        max_digits=11, decimal_places=10, default=Decimal("0.0"), null=False
    )
    standard_deviation = models.DecimalField(
        max_digits=11, decimal_places=10, default=Decimal("0.0"), null=False
    )

    class Meta:
        ordering = ["-average"]

    @property
    def as_percentage(self):
        return f"{round(self.average * 100, 1)} ± {round(self.standard_deviation * 100, 1)}%"

    @property
    def material(self):
        return self.composition.sample.material

    @property
    def material_settings(self):
        return self.composition.sample.series

    @property
    def group(self):
        return self.composition.group

    @property
    def group_settings(self):
        return self.composition

    @property
    def timestep(self):
        return self.composition.sample.timestep

    def get_absolute_url(self):
        return reverse(
            "sampleseries-detail", kwargs={"pk": self.composition.sample.series.id}
        )

    def duplicate(self, creator):
        duplicate = WeightShare.objects.create(
            owner=creator,
            component=self.component,
            composition=self.composition,
            average=self.average,
            standard_deviation=self.standard_deviation,
        )
        return duplicate

    def __str__(self):
        return f"Component share of material: {self.material.name}, component: {self.component.name}"
