"""Traceable population observations and derived estimates.

Population values are stored per dataset, region, and reference year.
Datasets keep provider, methodology, and classification metadata so that
values from different statistical series (e.g. Eurostat regional accounts
vs. national LAU statistics) are never conflated. Custom regions get
materialized estimates that preserve every contributing observation.
"""

from django.db import models

from bibliography.models import Source
from maps.models import Region


class TemporalBasis(models.TextChoices):
    CALENDAR_YEAR_AVERAGE = "calendar_year_average", "Calendar year average"
    POINT_IN_TIME = "point_in_time", "Point in time"


class GeographicScope(models.TextChoices):
    NUTS = "nuts", "NUTS"
    LAU = "lau", "LAU"


class SourceStatus(models.TextChoices):
    FINAL = "final", "Final"
    PROVISIONAL = "provisional", "Provisional"
    ESTIMATED = "estimated", "Estimated"


class PopulationDataset(models.Model):
    """A coherent statistical population series with a single methodology."""

    slug = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    provider = models.CharField(max_length=255)
    source_code = models.CharField(
        max_length=255,
        blank=True,
        help_text="Upstream dataset code, e.g. 'nama_10r_3popgdp'.",
    )
    geographic_scope = models.CharField(max_length=10, choices=GeographicScope.choices)
    temporal_basis = models.CharField(max_length=30, choices=TemporalBasis.choices)
    source_unit = models.CharField(
        max_length=30,
        blank=True,
        help_text="Unit of the upstream values before conversion to persons, e.g. 'THS'.",
    )
    classification_version = models.CharField(
        max_length=30,
        blank=True,
        help_text="NUTS/LAU classification version, e.g. 'NUTS2021'.",
    )
    is_canonical = models.BooleanField(
        default=False,
        help_text="Preferred dataset when multiple datasets cover the same region and year.",
    )
    bibliography_source = models.ForeignKey(
        Source,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="population_datasets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["slug"]

    def __str__(self):
        return self.slug


class PopulationImportRun(models.Model):
    """A single ingestion of upstream data into a dataset."""

    dataset = models.ForeignKey(
        PopulationDataset, on_delete=models.CASCADE, related_name="import_runs"
    )
    extracted_at = models.DateTimeField()
    upstream_updated_at = models.DateTimeField(null=True, blank=True)
    checksum = models.CharField(max_length=64, blank=True)
    structure_version = models.CharField(max_length=100, blank=True)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    unchanged_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-extracted_at"]

    def __str__(self):
        return f"{self.dataset.slug} @ {self.extracted_at:%Y-%m-%d %H:%M}"


class PopulationObservation(models.Model):
    """A direct population value for one region and one reference year, in persons."""

    dataset = models.ForeignKey(
        PopulationDataset, on_delete=models.PROTECT, related_name="observations"
    )
    import_run = models.ForeignKey(
        PopulationImportRun,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="observations",
    )
    region = models.ForeignKey(
        Region, on_delete=models.PROTECT, related_name="population_observations"
    )
    year = models.IntegerField()
    value = models.DecimalField(max_digits=15, decimal_places=3)
    source_status = models.CharField(
        max_length=20, choices=SourceStatus.choices, default=SourceStatus.FINAL
    )
    flags = models.CharField(
        max_length=20,
        blank=True,
        help_text="Raw upstream status/revision flags, e.g. Eurostat 'p'.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["dataset", "region", "year"],
                name="population_observation_dataset_region_year_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["region", "year"], name="population_obs_region_year_idx"
            )
        ]
        ordering = ["region_id", "year"]

    def __str__(self):
        return f"{self.dataset.slug}: {self.region} {self.year} = {self.value}"


class PopulationEstimateQuerySet(models.QuerySet):
    def stale(self):
        """Estimates whose component observations were revised after calculation."""
        return self.filter(
            components__updated_at__gt=models.F("calculated_at")
        ).distinct()


class PopulationEstimate(models.Model):
    """A materialized population estimate for a custom region.

    The value is the exact-year sum over the region's complete,
    non-overlapping NUTS/LAU components. Every contributing observation is
    preserved through :class:`PopulationEstimateComponent`.
    """

    region = models.ForeignKey(
        Region, on_delete=models.PROTECT, related_name="population_estimates"
    )
    year = models.IntegerField()
    value = models.DecimalField(max_digits=15, decimal_places=3)
    is_mixed_provenance = models.BooleanField(
        default=False,
        help_text="True when components come from methodologically different datasets.",
    )
    is_provisional = models.BooleanField(default=False)
    calculated_at = models.DateTimeField()
    components = models.ManyToManyField(
        PopulationObservation,
        through="PopulationEstimateComponent",
        related_name="dependent_estimates",
    )

    objects = PopulationEstimateQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["region", "year"],
                name="population_estimate_region_year_unique",
            )
        ]
        ordering = ["region_id", "year"]

    def __str__(self):
        return f"Estimate: {self.region} {self.year} = {self.value}"


class PopulationEstimateComponent(models.Model):
    estimate = models.ForeignKey(
        PopulationEstimate, on_delete=models.CASCADE, related_name="component_links"
    )
    observation = models.ForeignKey(
        PopulationObservation, on_delete=models.PROTECT, related_name="component_links"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["estimate", "observation"],
                name="population_estimate_component_unique",
            )
        ]
