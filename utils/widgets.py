from dal import autocomplete
from django.forms import Media
from django.forms.widgets import HiddenInput
from django_filters.widgets import SuffixedMultiWidget


class RangeSliderWidget(SuffixedMultiWidget):
    """A range slider widget that is compatible with django-crispy-forms and jQuery UI range slider."""
    template_name = 'widgets/range_slider_widget.html'
    widgets = [HiddenInput(), HiddenInput()]
    suffixes = ['min', 'max']
    unit = ''
    range_min = None
    range_max = None
    range_step = None
    default_range_min = 0
    default_range_max = 100
    default_range_step = 1
    default_include_null = True

    class Media:
        css = {
            'all': ('css/range_slider.min.css',)
        }
        js = ('js/range_slider.min.js',)

    def __init__(self, attrs=None, **kwargs):
        super().__init__(self.widgets, attrs)
        if attrs is not None:
            self.unit = attrs.get('data-unit', self.unit)
            self.range_min = attrs.get('data-range_min', self.range_min)
            self.range_max = attrs.get('data-range_max', self.range_max)
            self.range_step = attrs.get('data-range_step', self.range_step)
            self.default_range_min = attrs.get('data-default_range_min', self.default_range_min)
            self.default_range_max = attrs.get('data-default_range_max', self.default_range_max)
            self.default_include_null = attrs.get('data-default_include_null', self.default_include_null)

    def decompress(self, value):
        if not value:
            return [None, None]
        return [value.start, value.stop]

    def get_context(self, name, value, attrs):
        if not isinstance(value, list):
            value = self.decompress(value)
        context = super().get_context(name, value, attrs)
        cur_min, cur_max = value[0], value[1]
        if cur_min is None:
            cur_min = context['widget']['attrs']['data-range_min']
        if cur_max is None:
            cur_max = context['widget']['attrs']['data-range_max']
        step = context['widget']['attrs'].get('data-step', 1)
        context['widget']['attrs'].update({
            'data-cur_min': cur_min,
            'data-cur_max': cur_max,
            'data-step': step,
            'data-unit': self.unit,
        })
        base_id = context['widget']['attrs'].get('id', context['widget']['name'])
        for idx, subwidget in enumerate(context['widget']['subwidgets']):
            subwidget['attrs']['id'] = f'{base_id}_{self.suffixes[idx]}'
        context['widget']['value_text'] = f'{cur_min}{self.unit} - {cur_max}{self.unit}'
        return context


class NullableRangeSliderWidget(RangeSliderWidget):
    """
    A range slider widget that is compatible with django-crispy-forms and jQuery UI range slider.
    accepts an additional boolean value to indicate if null values should be included.
    """
    template_name = 'widgets/nullable_range_slider.html'
    widgets = [HiddenInput, HiddenInput, HiddenInput]
    suffixes = ['min', 'max', 'is_null']

    class Media:
        css = {
            'all': ('css/range_slider.min.css',)
        }
        js = ('js/range_slider.min.js', 'js/nullable_range_slider.min.js',)

    def decompress(self, range_with_null_flag):
        if not range_with_null_flag:
            return [None, None, 'true']
        value, is_null = range_with_null_flag
        return [value.start, value.stop, is_null]

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)

        if not isinstance(value, list):
            value = self.decompress(value)
        cur_is_null = value[2]
        if cur_is_null is None:
            cur_is_null = 'true'

        context['widget']['attrs'].update({
            'data-cur_is_null': str(cur_is_null == 'true').lower(),
        })

        return context


class NullablePercentageRangeSliderWidget(NullableRangeSliderWidget):
    unit = '%'


class BSModelSelect2(autocomplete.ModelSelect2):
    @property
    def media(self):
        base_media = super().media
        extra_media = Media(
            css={'screen': ('lib/select2-bootstrap-theme/select2-bootstrap4.min.css',)}
        )
        return base_media + extra_media


class BSModelSelect2Multiple(autocomplete.ModelSelect2Multiple):
    @property
    def media(self):
        base_media = super().media
        extra_media = Media(
            css={'screen': ('lib/select2-bootstrap-theme/select2-bootstrap4.min.css',)}
        )
        return base_media + extra_media


class BSListSelect2(autocomplete.ListSelect2):
    @property
    def media(self):
        base_media = super().media
        extra_media = Media(
            css={'screen': ('lib/select2-bootstrap-theme/select2-bootstrap4.min.css',)}
        )
        return base_media + extra_media
