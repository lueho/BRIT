"""Database models for the processes module.

The first version of the :mod:`processes` app mirrored the mock templates with
just enough structure to display demo content.  The models in this module now
move beyond that baseline by introducing reusable entities that can capture
real-world process data:

* processes retain their hierarchical organisation and descriptive metadata
* structured operating parameters are stored in :class:`ProcessOperatingParameter`
  records so editors can capture ranges for temperature, pressure, residence
  time, yield and custom metrics – each with explicit units
* material flows expose richer annotations such as stage/stream labels and
  optional quantity data
* literature references are normalised through :class:`ProcessReference`
  entries to avoid duplicated Source relations, while call-to-action links and
  supporting resources provide validated URLs or uploads.

The models continue to lean on the object management helpers that are shared
across the project (:class:`~utils.object_management.models.NamedUserCreatedObject`,
``get_default_owner`` …) so that moderation and attribution behave consistently
with the rest of BRIT.
"""

from __future__ import annotations

from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from bibliography.models import Source
from materials.models import Material
from utils.object_management.models import NamedUserCreatedObject
from utils.properties.models import Unit


def validate_internal_or_external_url(value: str) -> None:
    """Validate that ``value`` is either an absolute URL or a root-relative path."""

    if not value:
        return

    candidate = value.strip()
    parsed = urlparse(candidate)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return
    if not parsed.scheme and candidate.startswith("/") and " " not in candidate:
        return
    raise ValidationError(
        _("Provide either an absolute http(s) URL or a root-relative path."),
    )


class AppPermission(models.Model):
    """Model that defines app specific permissions for processes."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("access_app_feature", "Can access the app feature"),
        ]


class ProcessCategory(NamedUserCreatedObject):
    """High level grouping for processes (e.g. *Thermochemical*)."""

    url_format = "processes:{name_lower}-{action}{suffix}"

    class Meta:
        verbose_name = "Process category"
        verbose_name_plural = "Process categories"
        permissions = [
            ("can_moderate_processcategory", "Can moderate process categories"),
        ]


class Process(NamedUserCreatedObject):
    """Describes a process or process technology."""

    url_format = "processes:{name_lower}-{action}{suffix}"

    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="variants",
        help_text="Optional parent process that groups this technology.",
    )
    categories = models.ManyToManyField(
        ProcessCategory,
        blank=True,
        related_name="processes",
        help_text="High level categories such as thermochemical or biochemical.",
    )
    short_description = models.CharField(
        max_length=512,
        blank=True,
        help_text="One sentence summary used in cards and list views.",
    )
    mechanism = models.CharField(
        max_length=255,
        blank=True,
        help_text="Dominant conversion mechanism (e.g. fermentation, pyrolysis).",
    )
    materials = models.ManyToManyField(
        Material,
        through="ProcessMaterial",
        related_name="processes",
        blank=True,
    )
    image = models.ImageField(
        upload_to="processes/process_images/",
        blank=True,
        null=True,
        help_text="Optional illustrative image for cards or detail views.",
    )

    class Meta:
        ordering = ["name", "id"]
        permissions = [
            ("can_moderate_process", "Can moderate processes"),
        ]

    @property
    def sources(self):
        """Return distinct literature sources referenced by this process."""

        return Source.objects.filter(process_references__process=self).distinct()

    def _material_links_for_role(self, role: ProcessMaterial.Role):
        """Return prefetched material links for ``role`` if available."""

        links = None
        cache = getattr(self, "_prefetched_objects_cache", None)
        if cache and "process_materials" in cache:
            links = [link for link in cache["process_materials"] if link.role == role]
        if links is None:
            links = list(
                self.process_materials.select_related("material")
                .filter(role=role)
                .order_by("order", "id")
            )
        return links

    @property
    def input_materials(self):
        """Return material instances used as inputs."""

        return [
            link.material
            for link in self._material_links_for_role(ProcessMaterial.Role.INPUT)
        ]

    @property
    def output_materials(self):
        """Return material instances produced by the process."""

        return [
            link.material
            for link in self._material_links_for_role(ProcessMaterial.Role.OUTPUT)
        ]

    def operating_parameters_for(self, parameter: ProcessOperatingParameter.Parameter):
        """Convenience helper returning parameters of a specific type."""

        return self.operating_parameters.filter(parameter=parameter).order_by(
            "order", "id"
        )


class ProcessMaterial(models.Model):
    """Through model describing the role of a material in a process."""

    class Role(models.TextChoices):
        INPUT = "input", _("Input")
        OUTPUT = "output", _("Output")

    process = models.ForeignKey(
        Process,
        on_delete=models.CASCADE,
        related_name="process_materials",
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name="process_materials",
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    order = models.PositiveIntegerField(
        default=0,
        help_text="Optional order for display purposes.",
    )
    stage = models.CharField(
        max_length=128,
        blank=True,
        help_text="Stage of the process where this material is relevant (e.g. preprocessing).",
    )
    stream_label = models.CharField(
        max_length=128,
        blank=True,
        help_text="Optional label to distinguish parallel streams for the same material.",
    )
    quantity_value = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        blank=True,
        null=True,
        help_text="Representative quantity for the material (e.g. 2.5).",
    )
    quantity_unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        help_text="Unit describing the quantity when provided.",
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional context such as required pre-treatment or quality specs.",
    )
    optional = models.BooleanField(
        default=False,
        help_text="Flag inputs/outputs that are optional rather than mandatory.",
    )

    class Meta:
        ordering = ["role", "order", "id"]
        indexes = [
            models.Index(fields=["process", "role", "order"]),
        ]

    def __str__(self):
        return f"{self.material} ({self.get_role_display()})"

    def clean(self):
        super().clean()
        if self.quantity_value is not None and self.quantity_unit is None:
            raise ValidationError(
                {"quantity_unit": _("Select a unit for the provided quantity value.")}
            )
        if self.quantity_unit and self.quantity_value is None:
            raise ValidationError(
                {
                    "quantity_value": _(
                        "Provide a quantity value when a unit is selected."
                    )
                }
            )


class ProcessOperatingParameter(models.Model):
    """Structured representation of operating windows and performance metrics."""

    class Parameter(models.TextChoices):
        TEMPERATURE = "temperature", _("Temperature")
        PRESSURE = "pressure", _("Pressure")
        RESIDENCE_TIME = "residence_time", _("Residence time")
        THROUGHPUT = "throughput", _("Throughput")
        ENERGY_DEMAND = "energy_demand", _("Specific energy demand")
        YIELD = "yield", _("Yield")
        PH = "ph", _("pH")
        CUSTOM = "custom", _("Custom")

    process = models.ForeignKey(
        Process,
        on_delete=models.CASCADE,
        related_name="operating_parameters",
    )
    parameter = models.CharField(
        max_length=32,
        choices=Parameter.choices,
        help_text="Type of operating parameter (e.g. temperature, yield).",
    )
    name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Override label for the parameter (used for custom entries).",
    )
    unit = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        help_text="Unit describing the parameter values.",
    )
    value_min = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        blank=True,
        null=True,
        help_text="Lower bound for the operating window.",
    )
    value_max = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        blank=True,
        null=True,
        help_text="Upper bound for the operating window.",
    )
    nominal_value = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        blank=True,
        null=True,
        help_text="Single representative value when no range is required.",
    )
    basis = models.CharField(
        max_length=100,
        blank=True,
        help_text="Basis or conditions for the measurement (e.g. wet basis).",
    )
    notes = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        indexes = [
            models.Index(fields=["process", "parameter", "order"]),
        ]

    def __str__(self):
        label = self.name or self.get_parameter_display()
        return f"{label} ({self.process})"

    def clean(self):
        super().clean()
        errors = {}
        if self.parameter == self.Parameter.CUSTOM and not self.name:
            errors["name"] = _("Provide a name for custom operating parameters.")
        if (
            self.value_min is not None
            and self.value_max is not None
            and self.value_min > self.value_max
        ):
            errors["value_min"] = _(
                "Minimum value must be less than or equal to the maximum."
            )
        if (
            self.nominal_value is None
            and self.value_min is None
            and self.value_max is None
        ):
            errors["nominal_value"] = _(
                "Provide at least one value for the operating parameter."
            )
        if self.parameter == self.Parameter.YIELD:
            for field_name in ("value_min", "value_max", "nominal_value"):
                value = getattr(self, field_name)
                if value is not None and not (0 <= value <= 100):
                    errors[field_name] = _("Yield values must be between 0 and 100%.")
        if errors:
            raise ValidationError(errors)


class ProcessLink(models.Model):
    """Call-to-action link displayed on process detail cards."""

    process = models.ForeignKey(
        Process,
        on_delete=models.CASCADE,
        related_name="links",
    )
    label = models.CharField(max_length=255)
    url = models.CharField(
        max_length=1023,
        validators=[validate_internal_or_external_url],
        help_text="Relative or absolute URL to navigate to.",
    )
    open_in_new_tab = models.BooleanField(
        default=False,
        help_text="Open the link in a new browser tab/window.",
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.label


class ProcessInfoResource(models.Model):
    """Supplementary material such as info charts linked to a process."""

    class ResourceType(models.TextChoices):
        INTERNAL = "internal", _("Internal page")
        DOCUMENT = "document", _("Document upload")
        EXTERNAL = "external", _("External link")

    process = models.ForeignKey(
        Process,
        on_delete=models.CASCADE,
        related_name="info_resources",
    )
    title = models.CharField(max_length=255)
    resource_type = models.CharField(
        max_length=20,
        choices=ResourceType.choices,
        default=ResourceType.EXTERNAL,
    )
    description = models.TextField(blank=True)
    url = models.CharField(
        max_length=1023,
        blank=True,
        validators=[validate_internal_or_external_url],
        help_text="Target URL for internal or external resources.",
    )
    document = models.FileField(
        upload_to="processes/info_resources/",
        blank=True,
        null=True,
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def clean(self):
        super().clean()
        errors = {}
        cleaned_url = (self.url or "").strip()
        if self.resource_type == self.ResourceType.DOCUMENT:
            if not self.document:
                errors["document"] = _("Upload a document for document resources.")
            if cleaned_url:
                errors["url"] = _(
                    "Remove the URL when uploading a document-based resource."
                )
        else:
            if not cleaned_url:
                errors["url"] = _("Provide a URL for the selected resource type.")
            else:
                parsed = urlparse(cleaned_url)
                if self.resource_type == self.ResourceType.INTERNAL and parsed.scheme:
                    errors["url"] = _(
                        "Internal resources must use a root-relative URL (starting with '/')."
                    )
                if (
                    self.resource_type == self.ResourceType.EXTERNAL
                    and not parsed.scheme
                ):
                    errors["url"] = _(
                        "External resources must use an absolute http(s) URL."
                    )
        if errors:
            raise ValidationError(errors)

    @property
    def target_url(self):
        """Return the URL that should be used in templates."""

        if self.resource_type == self.ResourceType.DOCUMENT and self.document:
            return self.document.url
        return self.url

    def __str__(self):
        return self.title


class ProcessReference(models.Model):
    """Stores literature references for a process."""

    process = models.ForeignKey(
        Process,
        on_delete=models.CASCADE,
        related_name="references",
    )
    source = models.ForeignKey(
        Source,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="process_references",
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Custom title for references that are not stored as sources.",
    )
    url = models.URLField(
        blank=True,
        help_text="Optional URL for the custom reference.",
    )
    reference_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Type/category of the reference (e.g. website, article).",
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def clean(self):
        super().clean()
        if not self.source and not self.title:
            raise ValidationError(
                {
                    "title": _(
                        "Provide either a bibliographic source or a custom reference title."
                    )
                }
            )

    def __str__(self):
        if self.source:
            return str(self.source)
        return self.title
