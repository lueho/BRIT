from django.forms import CheckboxSelectMultiple
from django_filters import FilterSet
from django_filters.filters import RangeFilter, MultipleChoiceFilter

from .forms import TreeFilterForm
from .models import HamburgRoadsideTrees
from .widgets import CustomRangeWidget


class TreeAgeRangeFilter(RangeFilter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        values = [p.pflanzjahr for p in HamburgRoadsideTrees.objects.all()]
        min_value = min(values)
        max_value = max(values)
        self.extra['widget'] = CustomRangeWidget(attrs={'data-range_min': min_value, 'data-range_max': max_value})


GATTUNG_CHOICES = (
    ('Linde', 'Linden'),
    ('Eiche', 'Oak'),
    ('Ahorn', 'Maple'),
    ('Other', 'Other')
)

BEZIRK_CHOICES = (
    ('Harburg', 'Harburg'),
    ('Altona', 'Altona'),
    ('Bergedorf', 'Bergedorf'),
    ('Hamburg-Mitte', 'Hamburg-Mitte'),
    ('Hamburg-Nord', 'Hamburg-Nord'),
    ('Eimsbüttel', 'Eimsbüttel'),
    ('Wandsbek', 'Wandsbek')
)


class TreeFilter(FilterSet):
    gattung_deutsch = MultipleChoiceFilter(widget=CheckboxSelectMultiple, choices=GATTUNG_CHOICES, label='Tree genus')
    bezirk = MultipleChoiceFilter(widget=CheckboxSelectMultiple, choices=BEZIRK_CHOICES, label='City district')
    pflanzjahr = TreeAgeRangeFilter(label='Year of plantation')

    class Meta:
        model = HamburgRoadsideTrees
        fields = ['gattung_deutsch', 'bezirk']
        form = TreeFilterForm
