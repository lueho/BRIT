import django_filters
from django_filters import rest_framework as filters

from .models import HamburgRoadsideTrees


class TreeFilter(django_filters.FilterSet):

    def __init__(self, *args, **kwargs):
        super(TreeFilter, self).__init__(*args, **kwargs)
        self.form.initial['gattung_deutsch'] = 'Weissdorn'
        self.form.initial['bezirk'] = 'Eimsbüttel'
        self.form.initial['pflanzjahr'] = '1990'
        self.form.initial['stammumfang'] = ''

    class Meta:
        model = HamburgRoadsideTrees
        fields = ['gattung_deutsch', 'bezirk', 'pflanzjahr', 'stammumfang']


class TreeFilterSet(filters.FilterSet):
    class Meta:
        model = HamburgRoadsideTrees
        fields = ['gattung_deutsch', 'bezirk', 'pflanzjahr', 'stammumfang']
