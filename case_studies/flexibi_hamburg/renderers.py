from utils.file_export.renderers import BaseCSVRenderer, BaseXLSXRenderer


class HamburgRoadsideTreesXLSXRenderer(BaseXLSXRenderer):
    labels = {
        'baumid': 'Tree ID',
        'gattung_latein': 'Genus (Latin)',
        'art_latein': 'Species (Latin)',
        'sorte_latein': 'Variety (Latin)',
        'pflanzjahr': 'Planting Year',
        'kronendurchmesser': 'Crown Diameter [m]',
        'stammumfang': 'Stem Circumference [cm]',
        'strasse': 'Street',
        'hausnummer': 'House Number',
        'ortsteil_nr': 'District Number',
        'stadtteil': 'District',
        'bezirk': 'Borough'
    }

    workbook_options = {
        'constant_memory': True,
        'strings_to_urls': False
    }


class HamburgRoadsideTreesCSVRenderer(BaseCSVRenderer):
    writer_opts = {
        'delimiter': '\t'
    }
    header = ['baumid', 'gattung_latein', 'art_latein', 'sorte_latein', 'pflanzjahr', 'kronendurchmesser',
              'stammumfang', 'strasse', 'hausnummer', 'ortsteil_nr', 'stadtteil', 'bezirk']

    labels = {
        'baumid': 'Tree ID',
        'gattung_latein': 'Genus (Latin)',
        'art_latein': 'Species (Latin)',
        'sorte_latein': 'Variety (Latin)',
        'pflanzjahr': 'Planting Year',
        'kronendurchmesser': 'Crown Diameter [m]',
        'stammumfang': 'Stem Circumference [cm]',
        'strasse': 'Street',
        'hausnummer': 'House Number',
        'ortsteil_nr': 'District Number',
        'stadtteil': 'District',
        'bezirk': 'Borough'
    }
