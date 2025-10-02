from crispy_forms.bootstrap import AccordionGroup
from crispy_forms.layout import Field


class ForeignkeyField(Field):
    """
    A crispy forms field for foreign key relationships with inline creation capability.

    This field adds a button next to the dropdown that opens a modal form for creating a new related object.
    The modal form creates a new object via AJAX and the newly created object is automatically selected in the dropdown
    after creation.

    Attributes:
        template (str): The template used to render the field.
    """
    template = 'fields/foreignkey_field.html'


class RangeSliderField(Field):
    """
    A crispy forms field for range slider inputs.

    This field is designed to work with the RangeFilter from django-filters.
    It renders a slider that allows users to select a range of values.

    Attributes:
        template (str): The template used to render the field.
    """
    template = 'fields/range_slider_field.html'


class FilterAccordionGroup(AccordionGroup):
    """
    A specialized accordion group for filter forms.

    This class allows distributing the form fields over several accordion cards, e.g. for showing or hiding sets
    of standard and advanced fields.

    Attributes:
        template (str): The template used to render the accordion group.
    """
    template = 'fields/filter-accordion-group.html'
