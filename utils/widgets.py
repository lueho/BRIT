from django.forms.widgets import HiddenInput, SelectMultiple
from django_filters.widgets import SuffixedMultiWidget


class RangeSliderWidget(SuffixedMultiWidget):
    """
    A range slider widget that is compatible with django-crispy-forms.

    This widget allows users to select a range of values using a slider interface.
    It renders as two hidden inputs for the minimum and maximum values, with a
    visual slider representation.

    Attributes:
        template_name (str): The template used to render the widget.
        widgets (list): List of widget instances for each subfield.
        suffixes (list): List of suffixes for the subfield names.
        unit (str): The unit to display after the values (e.g., '%', 'kg').
        range_min (float): The minimum value for the slider.
        range_max (float): The maximum value for the slider.
        range_step (float): The step size for the slider.
        default_range_min (float): Default minimum value if not specified.
        default_range_max (float): Default maximum value if not specified.
        default_range_step (float): Default step size if not specified.
        default_include_null (bool): Whether to include null values by default.
        number_format (str): Format to use when displaying numbers. Options:
            - 'integer': No decimal places (e.g., years)
            - 'float-1': One decimal place
            - 'float-2': Two decimal places
            - 'auto': Smart formatting based on step size (default)
    """

    template_name = "widgets/range_slider_widget.html"
    widgets = [HiddenInput(), HiddenInput()]
    suffixes = ["min", "max"]
    unit = ""
    range_min = None
    range_max = None
    range_step = None
    default_range_min = 0
    default_range_max = 100
    default_range_step = 1
    number_format = "auto"
    default_include_null = True

    class Media:
        css = {
            "all": (
                "https://cdnjs.cloudflare.com/ajax/libs/noUiSlider/15.8.1/nouislider.min.css",
            )
        }
        js = (
            "https://cdnjs.cloudflare.com/ajax/libs/noUiSlider/15.8.1/nouislider.min.js",
            "js/range_slider.min.js",
        )

    def __init__(self, attrs=None, **kwargs):
        """
        Initialize the RangeSliderWidget.

        Args:
            attrs (dict, optional): HTML attributes for the widget.
                Special data attributes:
                - data-unit: The unit to display after values
                - data-range_min: Minimum value for the slider
                - data-range_max: Maximum value for the slider
                - data-range_step: Step size for the slider
                - data-default_range_min: Default minimum if not specified
                - data-default_range_max: Default maximum if not specified
                - data-default_include_null: Whether to include null values
                - data-number_format: Format for displaying numbers (integer, float-1, float-2, auto)
            **kwargs: Additional keyword arguments passed to the parent class.
        """
        super().__init__(self.widgets, attrs)
        if attrs is not None:
            self.unit = attrs.get("data-unit", self.unit)
            self.range_min = attrs.get("data-range_min", self.range_min)
            self.range_max = attrs.get("data-range_max", self.range_max)
            self.range_step = attrs.get("data-range_step", self.range_step)
            self.default_range_min = attrs.get(
                "data-default_range_min", self.default_range_min
            )
            self.default_range_max = attrs.get(
                "data-default_range_max", self.default_range_max
            )
            self.default_include_null = attrs.get(
                "data-default_include_null", self.default_include_null
            )
            self.number_format = attrs.get("data-number_format", self.number_format)

    def decompress(self, value):
        """
        Decompress the value into a list of values for the individual subwidgets.

        Args:
            value: A slice object representing the range, or None.

        Returns:
            list: A list containing the start and stop values of the range.
        """
        if not value:
            return [None, None]
        return [value.start, value.stop]

    def get_context(self, name, value, attrs):
        """
        Get the context for rendering the widget.

        This method prepares the context dictionary used by the template to render
        the range slider widget. It processes the current values, sets appropriate
        data attributes, and formats the display text.

        Args:
            name (str): The name of the field.
            value: The current value of the field.
            attrs (dict): Additional attributes for the widget.

        Returns:
            dict: The context dictionary for the template.
        """
        if not isinstance(value, list):
            value = self.decompress(value)
        context = super().get_context(name, value, attrs)
        cur_min, cur_max = value[0], value[1]
        if cur_min is None:
            cur_min = context["widget"]["attrs"]["data-range_min"]
        if cur_max is None:
            cur_max = context["widget"]["attrs"]["data-range_max"]
        step = context["widget"]["attrs"].get("data-step", 1)
        context["widget"]["attrs"].update(
            {
                "data-cur_min": cur_min,
                "data-cur_max": cur_max,
                "data-step": step,
                "data-unit": self.unit,
                "data-number_format": self.number_format,
            }
        )
        base_id = context["widget"]["attrs"].get("id", context["widget"]["name"])
        for idx, subwidget in enumerate(context["widget"]["subwidgets"]):
            subwidget["attrs"]["id"] = f"{base_id}_{self.suffixes[idx]}"
        context["widget"]["value_text"] = f"{cur_min}{self.unit} - {cur_max}{self.unit}"
        return context


class NullableRangeSliderWidget(RangeSliderWidget):
    """
    A range slider widget that extends RangeSliderWidget to include null values.

    This widget adds a checkbox to the range slider that allows users to include
    null values in the range. When the checkbox is checked, the range slider is
    disabled and null values are included in the filter.

    Attributes:
        template_name (str): The template used to render the widget.
        widgets (list): List of widget classes for each subfield.
        suffixes (list): List of suffixes for the subfield names.
    """

    template_name = "widgets/nullable_range_slider.html"
    widgets = [HiddenInput, HiddenInput, HiddenInput]
    suffixes = ["min", "max", "is_null"]

    class Media:
        css = {
            "all": (
                "https://cdnjs.cloudflare.com/ajax/libs/noUiSlider/15.8.1/nouislider.min.css",
            )
        }
        js = (
            "https://cdnjs.cloudflare.com/ajax/libs/noUiSlider/15.8.1/nouislider.min.js",
            "js/range_slider.min.js",
            "js/nullable_range_slider.min.js",
        )

    def decompress(self, range_with_null_flag):
        """
        Decompress the value into a list of values for the individual subwidgets.

        Args:
            range_with_null_flag: A tuple containing a slice object representing
                the range and a boolean indicating whether to include null values,
                or None.

        Returns:
            list: A list containing the start value, stop value, and null flag.
        """
        if not range_with_null_flag:
            return [None, None, "true"]
        value, is_null = range_with_null_flag
        return [value.start, value.stop, is_null]

    def get_context(self, name, value, attrs):
        """
        Get the context for rendering the widget.

        This method extends the parent's get_context method to add the null flag
        to the context.

        Args:
            name (str): The name of the field.
            value: The current value of the field.
            attrs (dict): Additional attributes for the widget.

        Returns:
            dict: The context dictionary for the template.
        """
        context = super().get_context(name, value, attrs)

        if not isinstance(value, list):
            value = self.decompress(value)
        cur_is_null = value[2]
        if cur_is_null is None:
            cur_is_null = "true"

        context["widget"]["attrs"].update(
            {
                "data-cur_is_null": str(cur_is_null == "true").lower(),
            }
        )

        return context


class NullablePercentageRangeSliderWidget(NullableRangeSliderWidget):
    """
    A specialized version of NullableRangeSliderWidget for percentage values.

    This widget displays values as percentages with a '%' symbol.
    It inherits all functionality from NullableRangeSliderWidget but
    sets the unit to '%' by default.

    Attributes:
        unit (str): The unit to display after the values, set to '%'.
    """

    unit = "%"


class SourceListWidget(SelectMultiple):
    """
    Widget that displays selected sources as a list (one per line) and uses
    TomSelect autocomplete for adding new sources.

    This avoids loading thousands of sources into the page while still showing
    selected sources with full titles for easy distinction.

    Usage:
        sources = ModelMultipleChoiceField(
            queryset=Source.objects.none(),  # Don't pre-load all sources
            widget=SourceListWidget(
                autocomplete_url='source-autocomplete',
                label_field='label'
            ),
            required=False
        )
    """

    template_name = "widgets/source_list_widget.html"

    def __init__(self, attrs=None, autocomplete_url=None, label_field="label"):
        self.autocomplete_url = autocomplete_url or "source-autocomplete"
        self.label_field = label_field
        super().__init__(attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["autocomplete_url"] = self.autocomplete_url
        context["widget"]["label_field"] = self.label_field
        return context

    def value_from_datadict(self, data, files, name):
        """
        Extract the list of selected source IDs from the submitted form data.
        """
        # Get all values for this field name (multiple selection)
        return data.getlist(name)

    class Media:
        css = {"all": ("utils/css/source_list_widget.min.css",)}
        js = ("utils/js/source_list_widget.min.js",)
