from django.db import models

from bibliography.models import Source
from materials.models import Material
from utils.object_management.models import NamedUserCreatedObject


class ProcessGroup(NamedUserCreatedObject):
    """
    Functional grouping of related process types (e.g. Pulping, Composting).
    """

    class Meta:
        verbose_name = "Process Group"
        verbose_name_plural = "Process Groups"
        unique_together = [["name", "owner"]]


class MechanismCategory(NamedUserCreatedObject):
    """
    Scientific classification of how a process works
    (e.g. Biochemical, Thermochemical, Physical).
    """

    class Meta:
        verbose_name = "Mechanism Category"
        verbose_name_plural = "Mechanism Categories"
        unique_together = [["name", "owner"]]


class ProcessType(NamedUserCreatedObject):
    """
    A type of material-conversion process (e.g. Pyrolysis, Composting).

    Captures the general scientific / engineering description together with
    key operating parameters.  Concrete runs of a process are **not** modelled
    here – this is the *type* level only.
    """

    group = models.ForeignKey(
        ProcessGroup,
        on_delete=models.PROTECT,
        related_name="process_types",
        null=True,
        blank=True,
        help_text="Functional process group (e.g. Pulping).",
    )
    mechanism_categories = models.ManyToManyField(
        MechanismCategory,
        blank=True,
        related_name="process_types",
        help_text="Scientific mechanism classifications (e.g. Physical, Biochemical).",
    )
    short_description = models.TextField(
        blank=True,
        help_text="One-line summary shown in cards and lists.",
    )
    mechanism = models.CharField(
        max_length=255,
        blank=True,
        help_text="Dominant reaction mechanism (e.g. Partial Oxidation).",
    )
    temperature_min = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Minimum operating temperature in °C.",
    )
    temperature_max = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum operating temperature in °C.",
    )
    yield_min = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Minimum yield in percent.",
    )
    yield_max = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum yield in percent.",
    )
    image = models.ImageField(
        upload_to="processes/",
        blank=True,
        null=True,
    )
    input_materials = models.ManyToManyField(
        Material,
        blank=True,
        related_name="as_process_input",
        help_text="Materials that can serve as feedstock for this process.",
    )
    output_materials = models.ManyToManyField(
        Material,
        blank=True,
        related_name="as_process_output",
        help_text="Materials produced by this process.",
    )
    sources = models.ManyToManyField(
        Source,
        blank=True,
        help_text="Literature references for this process type.",
    )

    class Meta:
        verbose_name = "Process Type"
        verbose_name_plural = "Process Types"
        unique_together = [["name", "owner"]]

    @property
    def temperature_range(self):
        if self.temperature_min is not None and self.temperature_max is not None:
            return f"{self.temperature_min} – {self.temperature_max} °C"
        return ""

    @property
    def yield_range(self):
        if self.yield_min is not None and self.yield_max is not None:
            return f"{self.yield_min} – {self.yield_max} %"
        return ""
