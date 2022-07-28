import xlsxwriter


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


