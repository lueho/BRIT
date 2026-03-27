from django.forms import NumberInput

from ..forms import SimpleModelForm
from .models import Property, Unit


class NumericMeasurementFieldsFormMixin:
    """Shared numeric field widget behavior for domain-owned measurement forms."""

    measurement_field_names = ("average", "standard_deviation")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name in self.measurement_field_names:
            field = self.fields.get(field_name)
            if field is None or not isinstance(field.widget, NumberInput):
                continue
            field.widget.attrs["step"] = "any"


class UnitModelForm(SimpleModelForm):
    class Meta:
        model = Unit
        fields = [
            "name",
            "symbol",
            "dimensionless",
            "reference_quantity",
            "description",
        ]


class PropertyModelForm(SimpleModelForm):
    """Form for the generic ``Property`` table used in shared or transitional flows."""

    class Meta:
        model = Property
        fields = ["name", "allowed_units", "description"]
