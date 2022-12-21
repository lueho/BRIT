from django.forms import CheckboxSelectMultiple
from django_filters.filters import MultipleChoiceFilter, NumberFilter

from utils.filters import SimpleFilterSet
from .models import HamburgRoadsideTrees

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


class TreeFilter(SimpleFilterSet):
    gattung_deutsch = MultipleChoiceFilter(widget=CheckboxSelectMultiple, choices=GATTUNG_CHOICES, label='Tree genus',
                                           method='filter_genus')
    bezirk = MultipleChoiceFilter(widget=CheckboxSelectMultiple, choices=BEZIRK_CHOICES, label='City district')
    pflanzjahr__gt = NumberFilter(field_name='pflanzjahr', lookup_expr='gt', label='Planted after year')
    pflanzjahr__lt = NumberFilter(field_name='pflanzjahr', lookup_expr='lt', label='Planted after year')
    stammumfang__gt = NumberFilter(field_name='stammumfang', lookup_expr='gt',
                                   label='Stem circumference [cm] greater than')
    stammumfang__lt = NumberFilter(field_name='stammumfang', lookup_expr='lt',
                                   label='Stem circumference [cm] less than')

    class Meta:
        model = HamburgRoadsideTrees
        fields = ('gattung_deutsch', 'bezirk', 'pflanzjahr__gt', 'pflanzjahr__lt', 'stammumfang__gt', 'stammumfang__lt')

    @staticmethod
    def filter_genus(qs, _, value):
        if 'Other' in value:
            qs = qs.exclude(gattung_deutsch__in=[choice[0] for choice in GATTUNG_CHOICES if choice[0] not in value])
        else:
            qs = qs.filter(gattung_deutsch__in=value)
        return qs
