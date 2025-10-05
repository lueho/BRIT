"""Filters for the processes module.

Provides FilterSets for searching and filtering processes and related models.
"""

import django_filters
from django import forms

from utils.object_management.models import STATUS_CHOICES

from .models import Process, ProcessCategory, ProcessMaterial


class ProcessCategoryFilter(django_filters.FilterSet):
    """Filter for ProcessCategory list views."""

    name = django_filters.CharFilter(
        lookup_expr="icontains",
        label="Category Name",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Search by name..."}),
    )
    publication_status = django_filters.ChoiceFilter(
        choices=[("", "All")] + list(STATUS_CHOICES),
        label="Publication Status",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = ProcessCategory
        fields = ["name", "publication_status"]


class ProcessFilter(django_filters.FilterSet):
    """Filter for Process list views with comprehensive search options."""

    name = django_filters.CharFilter(
        lookup_expr="icontains",
        label="Process Name",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Search by name..."}),
    )
    
    categories = django_filters.ModelMultipleChoiceFilter(
        queryset=ProcessCategory.objects.filter(publication_status="published"),
        label="Categories",
        widget=forms.CheckboxSelectMultiple(),
    )
    
    mechanism = django_filters.CharFilter(
        lookup_expr="icontains",
        label="Mechanism",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "e.g., pyrolysis, fermentation..."}
        ),
    )
    
    has_parent = django_filters.BooleanFilter(
        field_name="parent",
        lookup_expr="isnull",
        exclude=True,
        label="Has Parent Process",
        widget=forms.NullBooleanSelect(attrs={"class": "form-select"}),
    )
    
    parent = django_filters.ModelChoiceFilter(
        queryset=Process.objects.filter(publication_status="published", parent__isnull=True),
        label="Parent Process",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    
    publication_status = django_filters.ChoiceFilter(
        choices=[("", "All")] + list(STATUS_CHOICES),
        label="Publication Status",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    
    # Material-based filtering
    input_material = django_filters.CharFilter(
        method="filter_by_input_material",
        label="Input Material",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Search by input material..."}
        ),
    )
    
    output_material = django_filters.CharFilter(
        method="filter_by_output_material",
        label="Output Material",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Search by output material..."}
        ),
    )

    class Meta:
        model = Process
        fields = [
            "name",
            "categories",
            "mechanism",
            "parent",
            "publication_status",
        ]

    def filter_by_input_material(self, queryset, name, value):
        """Filter processes that have a specific material as input."""
        return queryset.filter(
            process_materials__material__name__icontains=value,
            process_materials__role=ProcessMaterial.Role.INPUT,
        ).distinct()

    def filter_by_output_material(self, queryset, name, value):
        """Filter processes that produce a specific material as output."""
        return queryset.filter(
            process_materials__material__name__icontains=value,
            process_materials__role=ProcessMaterial.Role.OUTPUT,
        ).distinct()
