import django_tables2 as tables

from .models import LiteratureSource


class SourceTable(tables.Table):
    class Meta:
        model = LiteratureSource
