from .models import Property, Unit
from ..forms import SimpleModelForm


class UnitModelForm(SimpleModelForm):
    class Meta:
        model = Unit
        fields = ['name', 'dimensionless', 'reference_quantity', 'description']


class PropertyModelForm(SimpleModelForm):
    class Meta:
        model = Property
        fields = ['name', 'allowed_units', 'description']
