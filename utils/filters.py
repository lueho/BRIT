from crispy_forms.helper import FormHelper
from dal_select2.widgets import Select2WidgetMixin
from django_filters import FilterSet, RangeFilter

from utils.fields import NullableRangeField, NullablePercentageRangeField


class BaseCrispyFilterSet(FilterSet):

    def get_form_helper(self):
        if hasattr(self.Meta, 'form_helper'):
            return self.Meta.form_helper()
        else:
            return FormHelper()

    @property
    def form(self):
        form = super().form
        if not hasattr(form, 'helper'):
            form.helper = self.get_form_helper()
        form.helper.form_tag = False
        return form


class CrispyAutocompleteFilterSet(BaseCrispyFilterSet):

    @property
    def form(self):
        form = super().form
        form.helper.include_media = False
        for name, field in form.fields.items():
            if isinstance(field.widget, Select2WidgetMixin):
                field.widget.attrs = {'data-theme': 'bootstrap4'}
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
    unit = ''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.range_min = kwargs.get('range_min', self.range_min)
        self.range_max = kwargs.get('range_max', self.range_max)
        self.range_step = kwargs.get('range_step', self.range_step)
        self.default_range_min = kwargs.get('default_range_min', self.default_range_min)
        self.default_range_max = kwargs.get('default_range_max', self.default_range_max)
        self.default_range_step = kwargs.get('default_range_step', self.default_range_step)
        self.default_include_null = kwargs.get('default_include_null', self.default_include_null)
        self.unit = kwargs.get('unit', self.unit)

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
            return super().filter(queryset, range_with_null_flag)
        value_range, is_null = range_with_null_flag
        isnull_lookup = f'{self.field_name}__isnull'
        if is_null:
            return (super().filter(queryset, value_range) | queryset.filter(**{isnull_lookup: True})).distinct()
        return super().filter(queryset, value_range)


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
            return super().filter(qs, percentage_range_with_null_flag)
        percentage_range, is_null = percentage_range_with_null_flag
        decimal_range_with_null_flag = slice(percentage_range.start / 100, percentage_range.stop / 100), is_null
        return super().filter(qs, decimal_range_with_null_flag)
