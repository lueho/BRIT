from django.forms.widgets import HiddenInput
from django_filters.widgets import RangeWidget


class RangeSlider(RangeWidget):
    template_name = 'widgets/range_slider_widget.html'

    def __init__(self, attrs=None):
        widgets = (HiddenInput(), HiddenInput())
        super(RangeWidget, self).__init__(widgets, attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        if not isinstance(value, list):
            value = self.decompress(value)
        cur_min, cur_max = value
        if cur_min is None:
            cur_min = context['widget']['attrs']['data-range_min']
        if cur_max is None:
            cur_max = context['widget']['attrs']['data-range_max']
        context['widget']['attrs'].update({'data-cur_min': cur_min, 'data-cur_max': cur_max})
        base_id = context['widget']['attrs']['id']
        for swx, subwidget in enumerate(context['widget']['subwidgets']):
            subwidget['attrs']['id'] = base_id + "_" + self.suffixes[swx]
        context['widget']['value_text'] = "{} - {}".format(cur_min, cur_max)
        return context


class PercentageRangeSlider(RangeSlider):
    template_name = 'widgets/percentage_range_slider_widget.html'

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        cur_min = context['widget']['attrs']['data-cur_min']
        cur_max = context['widget']['attrs']['data-cur_max']
        context['widget']['value_text'] = "{}% - {}%".format(cur_min, cur_max)
        return context
