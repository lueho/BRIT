from django.core.exceptions import ValidationError
from django.db import models


class WasteAtlasMapConfiguration(models.Model):
    """Client-side rendering configuration for a Waste Atlas map."""

    key = models.SlugField(
        max_length=100,
        unique=True,
        help_text="Stable key referenced by the Waste Atlas page registry.",
    )
    configuration = models.JSONField(
        default=dict,
        help_text="JSON object passed to the Waste Atlas choropleth renderer.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("key",)
        verbose_name = "Waste Atlas map configuration"
        verbose_name_plural = "Waste Atlas map configurations"

    def __str__(self):
        return self.key

    def clean(self):
        super().clean()
        if not isinstance(self.configuration, dict):
            raise ValidationError(
                {"configuration": "Map configuration must be a JSON object."}
            )
