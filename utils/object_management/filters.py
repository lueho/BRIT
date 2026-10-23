from crispy_forms.bootstrap import Accordion
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.forms import CheckboxSelectMultiple
from django_filters import (
    CharFilter,
    ChoiceFilter,
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
                "scope",
                "ordering",
            ),
        )
    )


class ReviewDashboardFilterSet(BaseCrispyFilterSet):
    """FilterSet for the review dashboard supporting multi-model filtering.

    IMPORTANT: This FilterSet generates the filter form UI using a dummy queryset.
    ReviewDashboardView applies filters to each model queryset, sorts lightweight
    references, and loads full objects only for the selected HTML page.

    Provides filter form fields for:
    - Text search across object names
    - Model type (ContentType) filtering
    - Owner/submitter filtering
    - Submission date range
    - Sorting options

    See ReviewDashboardView for filtering and pagination, and ReviewItemFilter
    for the shared Python ordering semantics.
    """

    search = CharFilter(
        method="form_only_filter", label="Search", help_text="Search by object name"
    )

    model_type = ModelMultipleChoiceFilter(
        queryset=ContentType.objects.none(),  # Set dynamically in __init__
        widget=CheckboxSelectMultiple,
        label="Model Type",
        method="form_only_filter",
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
        method="form_only_filter",
        help_text="Filter by who submitted the item",
    )

    submitted_after = DateFilter(
        field_name="submitted_at",
        lookup_expr="gte",
        label="Submitted after",
        help_text="Show items submitted after this date",
        method="form_only_filter",
    )

    submitted_before = DateFilter(
        field_name="submitted_at",
        lookup_expr="lte",
        label="Submitted before",
        help_text="Show items submitted before this date",
        method="form_only_filter",
    )

    scope = ChoiceFilter(
        choices=(
            ("review", "Pending review"),
            ("declined", "Declined"),
        ),
        label="Review state",
        empty_label=None,
        method="filter_scope",
        help_text="Pending moderation queue or declined follow-up history",
    )

    ordering = OrderingFilter(
        label="Sort by",
        choices=(
            ("-submitted_at", "Newest first"),
            ("submitted_at", "Oldest first"),
            ("name", "Name (A–Z)"),
            ("-name", "Name (Z–A)"),
        ),
        method="form_only_filter",
    )

    class Meta:
        form_helper = ReviewDashboardFilterFormHelper

    def __init__(self, *args, **kwargs):
        # Extract available_models from kwargs before passing to parent
        self.available_models = kwargs.pop("available_models", [])

        # TomSelect resolves bound model-choice values while rendering. A malformed
        # owner value would otherwise reach an integer primary-key lookup and turn
        # a harmless query parameter into a server error.
        data = kwargs.get("data", args[0] if args else None)
        if data and (owner := data.get("owner")) and not str(owner).isdigit():
            normalized_data = data.copy()
            normalized_data.pop("owner", None)
            if "data" in kwargs:
                kwargs["data"] = normalized_data
            else:
                args = (normalized_data, *args[1:])

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

    def filter_scope(self, queryset, name, value):
        """Form-only filter; the dashboard resolves the scope itself."""
        return queryset

    def form_only_filter(self, queryset, name, value):
        """No-op so this FilterSet can validate input and render its form.

        These widgets exist to drive the dashboard's own request handling;
        the queryset returned here is unused.
        """
        return queryset

    def filter_search(self, queryset, name, value):
        """Filter by object name (case-insensitive contains).

        The view applies the real filtering and sorting to each model queryset
        via ``ReviewItemCollector``; the ``queryset`` seen here is only the
        FilterView plumbing dummy.
        """
        return queryset
