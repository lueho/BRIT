from ..forms import SimpleModelForm
from .models import Property, Unit


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
    class Meta:
        model = Property
        fields = ["name", "allowed_units", "description"]
