import xlsxwriter
from rest_framework_csv.renderers import CSVRenderer


class BaseXLSXRenderer:
    labels = {}
    workbook_options = {}

    def render(self, file, data, *args, **kwargs):
        workbook = xlsxwriter.Workbook(file, self.workbook_options)
        worksheet = workbook.add_worksheet('sheet 1')

        bold = workbook.add_format({'bold': True})

        header = [self.labels[key] for key in data[0].keys()]
        for col, label in enumerate(header):
            worksheet.write(0, col, label, bold)
        row_idx = 1
        for row in data:
            for col_idx, (key, value) in enumerate(row.items()):
                worksheet.write(row_idx, col_idx, value)
            row_idx += 1
        workbook.close()


class CollectionXLSXRenderer(BaseXLSXRenderer):
    labels = {
        'catchment': 'Catchment',
        'nuts_or_lau_id': 'NUTS/LAU Id',
        'collector': 'Collector',
        'collection_system': 'Collection System',
        'country': 'Country',
        'waste_category': 'Waste Category',
        'allowed_materials': 'Allowed Materials',
        'connection_rate': 'Connection Rate',
        'connection_rate_year': 'Connection Rate Year',
        'frequency': 'Frequency',
        'comments': 'Comments',
        'sources': 'Sources',
        'created_by': 'Created by',
        'created_at': 'Created at',
        'lastmodified_by': 'Last modified by',
        'lastmodified_at': 'Last modified at'
    }

    workbook_options = {
        'constant_memory': True,
        'strings_to_urls': False
    }


class CollectionCSVRenderer(CSVRenderer):
    writer_opts = {
        'delimiter': '\t'
    }
    header = ['catchment', 'country', 'nuts_or_lau_id', 'collector', 'collection_system', 'waste_category',
              'allowed_materials', 'connection_rate', 'connection_rate_year', 'frequency', 'comments', 'sources',
              'created_by', 'created_at', 'lastmodified_by', 'lastmodified_at']
    labels = {
        'catchment': 'Catchment',
        'nuts_or_lau_id': 'NUTS/LAU Id',
        'collector': 'Collector',
        'collection_system': 'Collection System',
        'country': 'Country',
        'waste_category': 'Waste Category',
        'allowed_materials': 'Allowed Materials',
        'connection_rate': 'Connection Rate',
        'connection_rate_year': 'Connection Rate Year',
        'frequency': 'Frequency',
        'comments': 'Comments',
        'sources': 'Sources',
        'created_by': 'Created by',
        'created_at': 'Created at',
        'lastmodified_by': 'Last modified by',
        'lastmodified_at': 'Last modified at'
    }

    def render(self, file, data, *args, **kwargs):
        content = super().render(data, **kwargs)
        file.write(content)
