"""Filters for the processes module.

Provides FilterSets for searching and filtering processes and related models.
"""

import django_filters
from django import forms
from django_tomselect.app_settings import TomSelectConfig
from django_tomselect.widgets import TomSelectModelWidget

from utils.filters import UserCreatedObjectScopedFilterSet
from utils.object_management.models import STATUS_CHOICES
from utils.object_management.permissions import (
    apply_scope_filter,
    filter_queryset_for_user,
)

from .models import Process, ProcessCategory, ProcessMaterial


class ProcessCategoryFilter(django_filters.FilterSet):
    """Filter for ProcessCategory list views."""

    name = django_filters.CharFilter(
        lookup_expr="icontains",
        label="Category Name",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Search by name..."}
        ),
    )
    publication_status = django_filters.ChoiceFilter(
        choices=[("", "All")] + list(STATUS_CHOICES),
        label="Publication Status",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = ProcessCategory
        fields = ["name", "publication_status"]


class ProcessFilter(UserCreatedObjectScopedFilterSet):
    """Filter for Process list views with comprehensive search options."""

    name = django_filters.ModelChoiceFilter(
        queryset=Process.objects.none(),
        field_name="name",
        label="Process Name",
        empty_label="All",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="processes:process-autocomplete",
                filter_by=("scope", "name"),
            )
        ),
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
            attrs={
                "class": "form-control",
                "placeholder": "e.g., pyrolysis, fermentation...",
            }
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
        queryset=Process.objects.none(),
        label="Parent Process",
        empty_label="All",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="processes:process-autocomplete",
                filter_by=("scope", "name"),
            )
        ),
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
            attrs={
                "class": "form-control",
                "placeholder": "Search by input material...",
            }
        ),
    )

    output_material = django_filters.CharFilter(
        method="filter_by_output_material",
        label="Output Material",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Search by output material...",
            }
        ),
    )

    class Meta:
        model = Process
        fields = [
            "scope",
            "name",
            "categories",
            "mechanism",
            "parent",
            "publication_status",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = getattr(self, "request", None)
        queryset = Process.objects.all()
        category_queryset = ProcessCategory.objects.all()

        if request and hasattr(request, "user"):
            queryset = filter_queryset_for_user(queryset, request.user)
            category_queryset = filter_queryset_for_user(
                category_queryset, request.user
            )

        scope_value = None
        if hasattr(self, "data") and self.data:
            scope_value = self.data.get("scope")

        if scope_value:
            queryset = apply_scope_filter(
                queryset, scope_value, user=getattr(request, "user", None)
            )
            category_queryset = apply_scope_filter(
                category_queryset, scope_value, user=getattr(request, "user", None)
            )

        self.filters["name"].queryset = queryset
        self.filters["parent"].queryset = queryset.filter(parent__isnull=True)
        self.filters["categories"].queryset = category_queryset

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
