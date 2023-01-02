from crispy_forms.layout import Field


class ForeignkeyField(Field):
    """
    Similar to a ModelChoiceField. Additional to the model choice by dropdown, this adds a plus symbol next to the field
    as a shortcut to create a new model though a modal form.
    """
    template = 'fields/foreignkey_field.html'


class RangeSliderField(Field):
    """
    Field containing a range slider that is suitable for the RangeFilter from the django-filters package.
    """
    template = 'fields/range_slider_field.html'
