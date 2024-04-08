from utils.file_export.renderers import BaseCSVRenderer, BaseXLSXRenderer


class CollectionXLSXRenderer(BaseXLSXRenderer):
    labels = {
        'catchment': 'Catchment',
        'nuts_or_lau_id': 'NUTS/LAU Id',
        'collector': 'Collector',
        'collection_system': 'Collection System',
        'country': 'Country',
        'waste_category': 'Waste Category',
        'allowed_materials': 'Allowed Materials',
        'forbidden_materials': 'Forbidden Materials',
        'fee_system': 'Fee System',
        'frequency': 'Frequency',
        'population': 'Population',
        'population_density': 'Population Density',
        'connection_rate_2019': 'Connection Rate 2019 [%]',
        'connection_rate_2020': 'Connection Rate 2020 [%]',
        'connection_rate_2021': 'Connection Rate 2021 [%]',
        'specific_waste_collected_2015': 'Specific waste collected in 2015 [kg/(cap*year)]',
        'specific_waste_collected_2016': 'Specific waste collected in 2016 [kg/(cap*year)]',
        'specific_waste_collected_2017': 'Specific waste collected in 2017 [kg/(cap*year)]',
        'specific_waste_collected_2018': 'Specific waste collected in 2018 [kg/(cap*year)]',
        'specific_waste_collected_2019': 'Specific waste collected in 2019 [kg/(cap*year)]',
        'specific_waste_collected_2020': 'Specific waste collected in 2020 [kg/(cap*year)]',
        'specific_waste_collected_2021': 'Specific waste collected in 2021 [kg/(cap*year)]',
        'comments': 'Comments',
        'sources': 'Sources',
        'valid_from': 'Valid from',
        'valid_until': 'Valid until',
        'created_at': 'Created at',
        'lastmodified_at': 'Last modified at'
    }

    workbook_options = {
        'constant_memory': True,
        'strings_to_urls': False
    }


class CollectionCSVRenderer(BaseCSVRenderer):
    writer_opts = {
        'delimiter': '\t'
    }
    header = ['catchment', 'country', 'nuts_or_lau_id', 'collector', 'collection_system', 'waste_category',
              'allowed_materials', 'forbidden_materials', 'fee_system', 'frequency', 'population',
              'population_density',
              'connection_rate_2019', 'connection_rate_2020', 'connection_rate_2021',
              'specific_waste_collected_2015', 'specific_waste_collected_2016', 'specific_waste_collected_2017',
              'specific_waste_collected_2018', 'specific_waste_collected_2019', 'specific_waste_collected_2020',
              'specific_waste_collected_2021',
              'comments', 'sources', 'valid_from', 'valid_until', 'created_at', 'lastmodified_at']

    labels = {
        'catchment': 'Catchment',
        'nuts_or_lau_id': 'NUTS/LAU Id',
        'collector': 'Collector',
        'collection_system': 'Collection System',
        'country': 'Country',
        'waste_category': 'Waste Category',
        'allowed_materials': 'Allowed Materials',
        'forbidden_materials': 'Forbidden Materials',
        'fee_system': 'Fee System',
        'frequency': 'Frequency',
        'population': 'Population',
        'population_density': 'Population Density',
        'connection_rate_2019': 'Connection Rate 2019 [%]',
        'connection_rate_2020': 'Connection Rate 2020 [%]',
        'connection_rate_2021': 'Connection Rate 2021 [%]',
        'specific_waste_collected_2015': 'Specific waste collected in 2015 [kg/(cap*year)]',
        'specific_waste_collected_2016': 'Specific waste collected in 2016 [kg/(cap*year)]',
        'specific_waste_collected_2017': 'Specific waste collected in 2017 [kg/(cap*year)]',
        'specific_waste_collected_2018': 'Specific waste collected in 2018 [kg/(cap*year)]',
        'specific_waste_collected_2019': 'Specific waste collected in 2019 [kg/(cap*year)]',
        'specific_waste_collected_2020': 'Specific waste collected in 2020 [kg/(cap*year)]',
        'specific_waste_collected_2021': 'Specific waste collected in 2021 [kg/(cap*year)]',
        'comments': 'Comments',
        'sources': 'Sources',
        'valid_from': 'Valid from',
        'valid_until': 'Valid until',
        'created_at': 'Created at',
        'lastmodified_at': 'Last modified at'
    }
