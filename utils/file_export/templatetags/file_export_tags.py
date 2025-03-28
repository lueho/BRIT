from django import template
from django.urls import reverse

register = template.Library()


@register.inclusion_tag('../templates/export_link.html')
def export_link(file_format, export_url_name, progress_url_name=None):
    if file_format not in ['csv', 'xlsx']:
        raise ValueError('file_format must be "csv" or "xlsx"')
    if file_format == 'csv':
        icon_class = 'fa fa-fw fa-file-csv'
    elif file_format == 'xlsx':
        icon_class = 'fa fa-fw fa-file-excel'
    else:
        icon_class = 'fa fa-fw fa-file'
    if not progress_url_name:
        progress_url_name = 'file-export-progress'
    progress_url = reverse(progress_url_name, kwargs={'task_id': 0})
    text = f'Export to {file_format}'
    return {
        'id': f'export_{file_format}',
        'file_format': file_format,
        'export_url': reverse(export_url_name),
        'progress_url': progress_url,
        'icon_class': icon_class,
        'text': text,
    }
