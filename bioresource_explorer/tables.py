from django_tables2 import Column, Table, ManyToManyColumn


class DatasetTable(Table):
    region = Column(linkify=True)
    name = Column(linkify=True)
    description = Column()
    sources = ManyToManyColumn(linkify_item=True, attrs={'a': {'class': 'modal-link'}})
