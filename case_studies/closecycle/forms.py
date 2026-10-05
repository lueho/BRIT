from django import forms
from django_tomselect.forms import (
    TomSelectConfig,
    TomSelectModelChoiceField,
    TomSelectModelMultipleChoiceField,
)
from extra_views import InlineFormSetFactory
from leaflet.forms.widgets import LeafletWidget

from maps.views import CatchmentAutocompleteView
from materials.models import Material, Sample, SampleSeries
from processes.models import Process
from utils.forms import DynamicTableInlineFormSetHelper, SimpleModelForm

from .models import Showcase, ShowcaseMaterial, ShowcaseProcess


class ShowcaseModelForm(SimpleModelForm):
    region = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="region-autocomplete",
            label_field="display_name",
        ),
        label="Region",
    )
    catchment = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="catchment-autocomplete",
            filter_by=("region", CatchmentAutocompleteView.IN_REGION_LOOKUP),
            label_field="name",
        ),
        label="Catchment",
        required=False,
    )
    samples = TomSelectModelMultipleChoiceField(
        queryset=Sample.objects.all(),
        required=False,
        config=TomSelectConfig(url="sample-autocomplete", label_field="name"),
        label="Samples",
    )
    sample_series = TomSelectModelMultipleChoiceField(
        queryset=SampleSeries.objects.all(),
        required=False,
        config=TomSelectConfig(url="sampleseries-autocomplete", label_field="name"),
        label="Sample series",
    )

    class Meta:
        model = Showcase
        fields = (
            "name",
            "geom",
            "region",
            "catchment",
            "description",
            "samples",
            "sample_series",
        )
        widgets = {"geom": LeafletWidget()}


class ShowcaseMaterialInlineForm(forms.ModelForm):
    material = TomSelectModelChoiceField(
        queryset=Material.objects.filter(publication_status="published"),
        config=TomSelectConfig(url="material-autocomplete", label_field="name"),
        label="Material",
    )

    class Meta:
        model = ShowcaseMaterial
        fields = ("material", "role", "order")


class ShowcaseMaterialInline(InlineFormSetFactory):
    model = ShowcaseMaterial
    form_class = ShowcaseMaterialInlineForm
    factory_kwargs = {"extra": 1, "can_delete": True}
    formset_helper_class = DynamicTableInlineFormSetHelper


class ShowcaseProcessInlineForm(forms.ModelForm):
    process = TomSelectModelChoiceField(
        queryset=Process.objects.filter(publication_status="published"),
        config=TomSelectConfig(
            url="processes:process-autocomplete", label_field="name"
        ),
        label="Process",
    )

    class Meta:
        model = ShowcaseProcess
        fields = ("process", "order")


class ShowcaseProcessInline(InlineFormSetFactory):
    model = ShowcaseProcess
    form_class = ShowcaseProcessInlineForm
    factory_kwargs = {"extra": 1, "can_delete": True}
    formset_helper_class = DynamicTableInlineFormSetHelper
