from django.forms import MultiValueField, FloatField, BooleanField

from utils.widgets import NullableRangeSliderWidget, NullablePercentageRangeSliderWidget


class NullableRangeField(MultiValueField):
    widget = NullableRangeSliderWidget

    def __init__(self, fields=None, *args, **kwargs):
        if fields is None:
            fields = (
                FloatField(),
                FloatField(),
                BooleanField())
        super().__init__(fields, *args, **kwargs)

    def compress(self, data_list):
        if data_list:
            min_value, max_value, is_null = data_list
            return slice(min_value, max_value), is_null
        return None


class NullablePercentageRangeField(NullableRangeField):
    widget = NullablePercentageRangeSliderWidget
