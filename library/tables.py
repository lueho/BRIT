import django_tables2 as tables

from .models import Source


class SourceTable(tables.Table):
    class Meta:
        model = Source
