from django.forms.widgets import HiddenInput
from django_filters.widgets import RangeWidget


class CustomRangeWidget(RangeWidget):
    template_name = 'range-slider-widget.html'

    def __init__(self, attrs=None):
        widgets = (HiddenInput(), HiddenInput())
        super(RangeWidget, self).__init__(widgets, attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        current_min, current_max = value
        if current_min is None:
            current_min = context['widget']['attrs']['data-range_min']
        if current_max is None:
            current_max = context['widget']['attrs']['data-range_max']
        context['widget']['attrs'].update({'data-cur_min': current_min, 'data-cur_max': current_max})
        base_id = context['widget']['attrs']['id']
        for swx, subwidget in enumerate(context['widget']['subwidgets']):
            subwidget['attrs']['id'] = base_id + "_" + self.suffixes[swx]
        context['widget']['value_text'] = "{} - {}".format(current_min, current_max)
        return context
