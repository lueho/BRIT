from utils.forms import ModalModelFormMixin, SimpleModelForm, SourcesFieldMixin

from .models import MechanismCategory, ProcessGroup, ProcessType


class ProcessGroupModelForm(SimpleModelForm):
    class Meta:
        model = ProcessGroup
        fields = ("name", "description")


class ProcessGroupModalModelForm(ModalModelFormMixin, ProcessGroupModelForm):
    pass


class MechanismCategoryModelForm(SimpleModelForm):
    class Meta:
        model = MechanismCategory
        fields = ("name", "description")


class MechanismCategoryModalModelForm(ModalModelFormMixin, MechanismCategoryModelForm):
    pass


class ProcessTypeModelForm(SourcesFieldMixin, SimpleModelForm):
    class Meta:
        model = ProcessType
        fields = (
            "name",
            "description",
            "group",
            "mechanism_categories",
            "short_description",
            "mechanism",
            "temperature_min",
            "temperature_max",
            "yield_min",
            "yield_max",
            "image",
            "input_materials",
            "output_materials",
            "sources",
        )


class ProcessTypeModalModelForm(ModalModelFormMixin, ProcessTypeModelForm):
    pass
