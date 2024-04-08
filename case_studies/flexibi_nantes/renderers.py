from rest_framework_csv.renderers import CSVRenderer

from utils.file_export.renderers import BaseXLSXRenderer


class NantesGreenhousesXLSXRenderer(BaseXLSXRenderer):
    labels = {
        'nb_cycles': 'Number of cycles',
        'culture_1': 'Culture 1',
        'culture_2': 'Culture 2',
        'culture_3': 'Culture 3',
        'heated': 'Heated',
        'lighted': 'Artificial Lighting',
        'high_wire': 'High wire',
        'above_ground': 'Above ground',
        'surface_ha': 'Surface (ha)'
    }

    workbook_options = {
        'constant_memory': True,
        'strings_to_urls': False
    }


class NantesGreenhousesCSVRenderer(CSVRenderer):
    writer_opts = {
        'delimiter': '\t'
    }
    header = ['nb_cycles', 'culture_1', 'culture_2', 'culture_3', 'heated', 'lighted', 'high_wire', 'above_ground',
              'surface_ha']

    labels = {
        'nb_cycles': 'Number of cycles',
        'culture_1': 'Culture 1',
        'culture_2': 'Culture 2',
        'culture_3': 'Culture 3',
        'heated': 'Heated',
        'lighted': 'Artificial Lighting',
        'high_wire': 'High wire',
        'above_ground': 'Above ground',
        'surface_ha': 'Surface (ha)'
    }

    def render(self, file, data, *args, **kwargs):
        content = super().render(data, **kwargs)
        file.write(content)
