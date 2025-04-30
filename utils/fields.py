from django.forms import MultiValueField, FloatField, BooleanField

from utils.widgets import NullableRangeSliderWidget, NullablePercentageRangeSliderWidget


class NullableRangeField(MultiValueField):
    """
    A form field for selecting a range of values with an option to include null values.

    This field combines two FloatField instances for the minimum and maximum values
    of the range, and a BooleanField for indicating whether to include null values.
    It uses the NullableRangeSliderWidget for rendering.

    Attributes:
        widget: The widget class to use for rendering the field.
    """
    widget = NullableRangeSliderWidget

    def __init__(self, fields=None, *args, **kwargs):
        """
        Initialize the NullableRangeField.

        Args:
            fields (tuple, optional): A tuple of form fields for the subfields.
                If not provided, defaults to (FloatField(), FloatField(), BooleanField()).
            *args: Additional positional arguments passed to the parent class.
            **kwargs: Additional keyword arguments passed to the parent class.
        """
        if fields is None:
            fields = (
                FloatField(),
                FloatField(),
                BooleanField())
        super().__init__(fields, *args, **kwargs)

    def compress(self, data_list):
        """
        Compress the list of values from the subfields into a single value.

        Args:
            data_list (list): A list containing the values from the subfields.
                Expected to contain [min_value, max_value, is_null].

        Returns:
            tuple or None: A tuple containing a slice object (min_value, max_value)
                and the is_null flag, or None if data_list is empty.
        """
        if data_list:
            min_value, max_value, is_null = data_list
            return slice(min_value, max_value), is_null
        return None


class NullablePercentageRangeField(NullableRangeField):
    """
    A specialized version of NullableRangeField for percentage values.

    This field inherits all functionality from NullableRangeField but uses
    the NullablePercentageRangeSliderWidget for rendering, which displays
    values as percentages.

    Attributes:
        widget: The widget class to use for rendering the field.
    """
    widget = NullablePercentageRangeSliderWidget
