from crispy_forms.bootstrap import Accordion
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.forms import CheckboxSelectMultiple
from django_filters import (
    CharFilter,
    DateFilter,
    ModelChoiceFilter,
    ModelMultipleChoiceFilter,
    OrderingFilter,
)
from django_tomselect.app_settings import TomSelectConfig
from django_tomselect.widgets import TomSelectModelWidget

from utils.crispy_fields import FilterAccordionGroup
from utils.filters import BaseCrispyFilterSet


class ReviewDashboardFilterFormHelper(FormHelper):
    """Form helper for review dashboard filters with accordion layout."""

    layout = Layout(
        Accordion(
            FilterAccordionGroup(
                "Filters",
                "search",
                "model_type",
                "owner",
                "submitted_after",
                "submitted_before",
                "ordering",
            ),
        )
    )


class ReviewDashboardFilterSet(BaseCrispyFilterSet):
    """FilterSet for the review dashboard supporting multi-model filtering.

    Provides filters for:
    - Text search across object names
    - Model type (ContentType) filtering
    - Owner/submitter filtering
    - Submission date range
    - Sorting options
    """

    search = CharFilter(
        method="filter_search", label="Search", help_text="Search by object name"
    )

    model_type = ModelMultipleChoiceFilter(
        queryset=ContentType.objects.none(),  # Set dynamically in __init__
        widget=CheckboxSelectMultiple,
        label="Model Type",
        method="filter_model_type",
        help_text="Filter by content type",
    )

    owner = ModelChoiceFilter(
        queryset=User.objects.filter(is_active=True).order_by("username"),
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="user-autocomplete",
                value_field="id",
                label_field="username",
            )
        ),
        label="Submitted by",
        method="filter_owner",
        help_text="Filter by who submitted the item",
    )

    submitted_after = DateFilter(
        field_name="submitted_at",
        lookup_expr="gte",
        label="Submitted after",
        help_text="Show items submitted after this date",
    )

    submitted_before = DateFilter(
        field_name="submitted_at",
        lookup_expr="lte",
        label="Submitted before",
        help_text="Show items submitted before this date",
    )

    ordering = OrderingFilter(
        label="Sort by",
        choices=(
            ("-submitted_at", "Newest first"),
            ("submitted_at", "Oldest first"),
            ("name", "Name (A–Z)"),
            ("-name", "Name (Z–A)"),
        ),
        method="filter_ordering",
    )

    class Meta:
        form_helper = ReviewDashboardFilterFormHelper

    def __init__(self, *args, **kwargs):
        # Extract available_models from kwargs before passing to parent
        self.available_models = kwargs.pop("available_models", [])
        super().__init__(*args, **kwargs)

        # Set model_type queryset to available ContentTypes
        if self.available_models:
            model_ids = [
                ContentType.objects.get_for_model(model).id
                for model in self.available_models
            ]
            self.filters["model_type"].queryset = ContentType.objects.filter(
                id__in=model_ids
            ).order_by("model")

    def filter_search(self, queryset, name, value):
        """Filter by object name (case-insensitive contains).

        Since queryset is actually a list of heterogeneous objects,
        this filter is applied in the view after objects are collected.
        """
        # Return queryset unchanged; filtering happens in view
        return queryset

    def filter_model_type(self, queryset, name, value):
        """Filter by ContentType.

        Since queryset is actually a list of heterogeneous objects,
        this filter is applied in the view after objects are collected.
        """
        # Return queryset unchanged; filtering happens in view
        return queryset

    def filter_owner(self, queryset, name, value):
        """Filter by owner/submitter.

        Since queryset is actually a list of heterogeneous objects,
        this filter is applied in the view after objects are collected.
        """
        # Return queryset unchanged; filtering happens in view
        return queryset

    def filter_ordering(self, queryset, name, value):
        """Apply sorting to the queryset.

        Since queryset is actually a list of heterogeneous objects,
        this is handled in the view after objects are collected.
        """
        # Return queryset unchanged; sorting happens in view
        return queryset
