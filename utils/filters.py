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
    A custom filter for Django that filters a range of values, optionally including null values. The range can be
    specified using the `range_min`, `range_max` and `range_step` either as class attributes or as kwargs during class
    initialization. Fallback can be set using the `default_range_min`, `default_range_max` and `default_range_step`
    as class attributes or kwargs during class initialization.
    """

    # --- Configuration attributes (override in subclasses or via kwargs) ---
    field_class = NullableRangeField
    range_min: int | float | None = None
    range_max: int | float | None = None
    range_step: int | float | None = None
    default_range_min: int | float = 0
    default_range_max: int | float = 100
    default_range_step: int | float = 1
    default_include_null: bool = False
    unit: str = ""

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

    def get_filter_range_min(self):
        return self.range_min or self.default_range_min

    def get_filter_range_max(self):
        return self.range_max or self.default_range_max

    def _build_range_slice(self, value_range: slice) -> slice:
        """Return a concrete ``slice`` for *value_range*.

        Subclasses rarely need to override this, but advanced filters can extend it to
        implement clamping or rounding logic.
        """
        start = (
            value_range.start
            if value_range.start is not None
            else self.get_filter_range_min()
        )
        stop = (
            value_range.stop
            if value_range.stop is not None
            else self.get_filter_range_max()
        )
        return slice(start, stop)

    def apply_range(self, qs, value_slice: slice, include_nulls: bool):
        """Apply *value_slice* (+ optional nulls) against ``self.field_name``.

        Subclasses can override for complex lookups (annotations, joins, etc.).
        """
        filtered = qs.filter(
            **{
                f"{self.field_name}__gte": value_slice.start,
                f"{self.field_name}__lte": value_slice.stop,
            }
        )
        if include_nulls:
            filtered = filtered | qs.filter(**{f"{self.field_name}__isnull": True})
        return filtered

    def filter(self, queryset, range_with_null_flag):
        """Filter *queryset* according to a numeric range and an *include_nulls* flag."""
        if not range_with_null_flag:
            return queryset

        value_slice, include_nulls = range_with_null_flag
        value_slice = self._build_range_slice(value_slice)

        # If no numeric restriction and nulls not requested → return as-is
        if value_slice.start is None and value_slice.stop is None:
            return queryset

        return self.apply_range(queryset, value_slice, include_nulls).distinct()


class NullablePercentageRangeFilter(NullableRangeFilter):
    """
    A custom filter for Django that filters a range of percentages, optionally including nullable values.
    """

    field_class = NullablePercentageRangeField

    def _build_range_slice(self, value_range: slice) -> slice:
        """Convert *value_range* expressed in percent to a decimal slice (0.0 - 1.0)."""
        base_slice = super()._build_range_slice(value_range)
        start = None if base_slice.start is None else base_slice.start / 100
        stop = None if base_slice.stop is None else base_slice.stop / 100
        return slice(start, stop)

    #     return super().filter(queryset, (decimal_range, include_nulls))


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
            ("review", "Review"),
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
        elif value == "review":
            return queryset.filter(publication_status="review")
        # Default / fallback: only published objects
        return queryset.filter(publication_status="published")
