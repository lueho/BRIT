import django_tables2 as tables
from django.urls import reverse
from django.utils.html import format_html


class StandardItemTable(tables.Table):
    """
    Table template for standard items owned and editable by the current user. This is meant to be a template for the
    django-tables2 table_factory. Constructor does not work by itself.
    """

    def __init__(self, *args, **kwargs):
        name = tables.Column(linkify=lambda record: record.detail_url)
        description = tables.Column()
        kwargs['extra_columns'] = [('name', name), ('description', description)]
        super().__init__(*args, **kwargs)

    class Meta:
        fields = ()


class UserItemTable(tables.Table):
    """
    Table template for items owned and editable by the current user. This is meant to be a template for the
    django-tables2 table_factory. Constructor does not work by itself.
    """

    def __init__(self, *args, **kwargs):
        name = tables.Column(footer=self.get_create_url(), linkify=lambda record: record.detail_url)
        description = tables.Column()
        edit = tables.TemplateColumn(
            '<a href="javascript:void(0);" class="modal-link" data-link="{{ record.update_url }}"><i class="fas fa-fw fa-edit"></i></a>')
        delete = tables.TemplateColumn(
            '<a href="javascript:void(0);" class="modal-link" data-link="{{ record.delete_url }}"><i class="fas fa-fw fa-trash"></i></a>')
        kwargs['extra_columns'] = [('name', name), ('description', description), ('edit', edit), ('delete', delete)]
        super().__init__(*args, **kwargs)

    def get_create_url(self):
        return format_html(
            '''
            <a href="javascript:void(0);" class="modal-link" data-link="{0}">
                <i class="fas fa-fw fa-plus"></i> Create new {1}
            </a>
            ''',
            reverse(f'{self.Meta.model._meta.verbose_name}_create'),
            # TODO: Find better way, that is not dependent on url pattern convention.
            self.Meta.model._meta.verbose_name
        )

    class Meta:
        fields = ()
