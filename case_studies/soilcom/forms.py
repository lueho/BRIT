from brit.forms import CustomModelForm, CustomModalModelForm
from . import models

from materials.models import Material, MaterialGroup


class CollectorModelForm(CustomModelForm):
    class Meta:
        model = models.Collector
        fields = ('name', 'description')


class CollectorModalModelForm(CustomModalModelForm):
    class Meta:
        model = models.Collector
        fields = ('name', 'description')


class CollectionSystemModelForm(CustomModelForm):
    class Meta:
        model = models.CollectionSystem
        fields = ('name', 'description')


class CollectionSystemModalModelForm(CustomModalModelForm):
    class Meta:
        model = models.CollectionSystem
        fields = ('name', 'description')


class WasteCategoryModelForm(CustomModelForm):
    class Meta:
        model = models.WasteCategory
        fields = ('name', 'description')


class WasteCategoryModalModelForm(CustomModalModelForm):
    class Meta:
        model = models.WasteCategory
        fields = ('name', 'description')


class WasteStreamModelForm(CustomModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        groups = MaterialGroup.objects.filter(name='Biowaste component')
        self.fields['allowed_materials'].queryset = Material.objects.filter(groups__in=groups)

    class Meta:
        model = models.WasteStream
        fields = ('name', 'category', 'allowed_materials', 'composition', 'description')


class WasteStreamModalModelForm(CustomModalModelForm):
    class Meta:
        model = models.WasteStream
        fields = ('name', 'category', 'allowed_materials', 'composition', 'description')
