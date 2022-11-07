from rest_framework_csv.renderers import CSVRenderer

from brit.renderers import BaseXLSXRenderer


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
        'fee_system': 'Fee System',
        'frequency': 'Frequency',
        'population': 'Population',
        'population_density': 'Population Density',
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
              'allowed_materials', 'connection_rate', 'connection_rate_year', 'fee_system', 'frequency', 'population',
              'population_density', 'comments', 'sources', 'created_by', 'created_at', 'lastmodified_by',
              'lastmodified_at']
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
        'fee_system': 'Fee System',
        'frequency': 'Frequency',
        'population': 'Population',
        'population_density': 'Population Density',
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
