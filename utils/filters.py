from crispy_forms.helper import FormHelper
from django.forms import HiddenInput
from django_filters import ChoiceFilter, FilterSet, RangeFilter

from utils.fields import NullablePercentageRangeField, NullableRangeField


class BaseCrispyFilterSet(FilterSet):

    def get_form_helper(self):
        if hasattr(self, "Meta") and hasattr(self.Meta, "form_helper"):
            return self.Meta.form_helper()
        else:
            return FormHelper()

    @property
    def form(self):
        form = super().form
        if not hasattr(form, "helper"):
            form.helper = self.get_form_helper()
        form.helper.form_tag = False
        return form


class NullableRangeFilter(RangeFilter):
    """
    A custom filter for Django that filters a range of values, optionally including nullable values.
    """

    field_class = NullableRangeField
    range_min = None
    range_max = None
    range_step = None
    default_range_min = 0
    default_range_max = 100
    default_range_step = 1
    default_include_null = False
    unit = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.range_min = kwargs.get("range_min", self.range_min)
        self.range_max = kwargs.get("range_max", self.range_max)
        self.range_step = kwargs.get("range_step", self.range_step)
        self.default_range_min = kwargs.get("default_range_min", self.default_range_min)
        self.default_range_max = kwargs.get("default_range_max", self.default_range_max)
        self.default_range_step = kwargs.get(
            "default_range_step", self.default_range_step
        )
        self.default_include_null = kwargs.get(
            "default_include_null", self.default_include_null
        )
        self.unit = kwargs.get("unit", self.unit)

    def filter(self, queryset, range_with_null_flag):
        """
        Filters the given queryset based on the value range and null flag.

        Args:
            queryset (QuerySet): The Django queryset to be filtered.
            range_with_null_flag (tuple): A tuple containing a slice object with start and stop values
                                          and a boolean flag to indicate if null values should be included.

        Returns:
            QuerySet: The filtered queryset.
        """
        if not range_with_null_flag:
            return queryset

        value_range, is_null = range_with_null_flag
        start = (
            value_range.start
            if value_range.start is not None
            else self.default_range_min
        )
        stop = (
            value_range.stop
            if value_range.stop is not None
            else self.default_range_max
        )

        final_range = slice(start, stop)
        isnull_lookup = f"{self.field_name}__isnull"

        if final_range.start is None and final_range.stop is None:
            filtered_qs = queryset
        else:
            filtered_qs = super().filter(queryset, final_range)

        if is_null:
            return (filtered_qs | queryset.filter(**{isnull_lookup: True})).distinct()
        return filtered_qs


class NullablePercentageRangeFilter(NullableRangeFilter):
    """
    A custom filter for Django that filters a range of percentages, optionally including nullable values.
    """

    field_class = NullablePercentageRangeField

    def filter(self, qs, percentage_range_with_null_flag):
        """
        Filters the given queryset based on the percentage range and null flag.

        Args:
            qs (QuerySet): The Django queryset to be filtered.
            percentage_range_with_null_flag (tuple): A tuple containing a slice object with start and stop percentages
                                                     and a boolean flag to indicate if null values should be included.

        Returns:
            QuerySet: The filtered queryset.
        """
        if not percentage_range_with_null_flag:
            return qs

        percentage_range, is_null = percentage_range_with_null_flag

        start = (
            percentage_range.start
            if percentage_range.start is not None
            else self.default_range_min
        )
        stop = (
            percentage_range.stop
            if percentage_range.stop is not None
            else self.default_range_max
        )

        start = start / 100 if start is not None else None
        stop = stop / 100 if stop is not None else None

        decimal_range_with_null_flag = (slice(start, stop), is_null)
        return super().filter(qs, decimal_range_with_null_flag)


class UserCreatedObjectScopedFilterSet(BaseCrispyFilterSet):
    """FilterSet base class for user-created objects supporting a `scope` parameter.

    Adds a hidden ``scope`` ChoiceFilter that can take the values ``published`` or
    ``private``. When ``private`` is selected, only objects owned by the
    requesting user are returned (and an empty queryset for anonymous users).
    When ``published`` (the default) is selected, only objects with
    ``publication_status='published'`` are returned.
    """

    scope = ChoiceFilter(
        choices=(
            ("published", "Published"),
            ("private", "Private"),
        ),
        widget=HiddenInput(),
        method="filter_scope",
        label="",
        initial="published",
    )

    def filter_scope(self, queryset, name, value):
        """Filter *queryset* according to *value* of ``scope``.

        - ``private``: return objects owned by the authenticated user; anonymous
          users get an empty queryset.
        - any other value (including ``published`` or empty): return only
          published objects.
        """
        if value == "private":
            user = getattr(self.request, "user", None)
            if user is None or not user.is_authenticated:
                return queryset.none()
            return queryset.filter(owner=user)
        # Default / fallback: only published objects
        return queryset.filter(publication_status="published")
