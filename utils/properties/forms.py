from .models import Property, PropertyUnit
from ..forms import SimpleModelForm


class PropertyUnitModelForm(SimpleModelForm):
    class Meta:
        model = PropertyUnit
        fields = ['name', 'dimensionless', 'reference_quantity', 'description']


class PropertyModelForm(SimpleModelForm):
    class Meta:
        model = Property
        fields = ['name', 'allowed_units', 'description']
