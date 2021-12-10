import django_tables2 as tables

from . import models


class CollectorsTable(tables.Table):
    class Meta:
        model = models.Collector
        fields = ('name', 'description',)
