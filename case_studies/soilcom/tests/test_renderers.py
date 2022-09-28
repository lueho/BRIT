import codecs
import csv
from io import BytesIO
from openpyxl import load_workbook

from django.contrib.auth.models import User, Permission
from django.test import TestCase

from maps.models import Catchment, NutsRegion
from materials.models import MaterialCategory
from users.models import get_default_owner

from ..models import (Collection, Collector, CollectionSystem, WasteCategory, WasteComponent, WasteFlyer, WasteStream,
                      CollectionFrequency)
from ..renderers import CollectionCSVRenderer, CollectionXLSXRenderer
from ..serializers import CollectionFlatSerializer


class CollectionCSVRendererTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        member.user_permissions.add(Permission.objects.get(codename='add_collection'))

        MaterialCategory.objects.create(owner=owner, name='Biowaste component')
        material1 = WasteComponent.objects.create(owner=owner, name='Test material 1')
        material2 = WasteComponent.objects.create(owner=owner, name='Test material 2')
        waste_stream = WasteStream.objects.create(
            owner=owner,
            name='Test waste stream',
            category=WasteCategory.objects.create(owner=owner, name='Test category'),
        )
        waste_stream.allowed_materials.add(material1)
        waste_stream.allowed_materials.add(material2)

        waste_flyer = WasteFlyer.objects.create(
            owner=owner,
            abbreviation='WasteFlyer123',
            url='https://www.test-flyer.org'
        )
        frequency = CollectionFrequency.objects.create(owner=owner, name='Test Frequency')
        nuts = NutsRegion.objects.create(owner=owner, name='Test NUTS', nuts_id='DE123', cntr_code='DE')
        catchment = Catchment.objects.create(owner=owner, name='Test catchment', region=nuts.region_ptr)
        for i in range(1, 3):
            collection = Collection.objects.create(
                name=f'collection{i}',
                catchment=catchment,
                collector=Collector.objects.create(owner=owner, name=f'collector{1}'),
                collection_system=CollectionSystem.objects.create(owner=owner, name='Test system'),
                waste_stream=waste_stream,
                connection_rate=0.7,
                connection_rate_year=2020,
                frequency=frequency,
                description='This is a test case.'
            )
            collection.flyers.add(waste_flyer)

    def setUp(self):
        self.file = BytesIO()
        self.content = CollectionFlatSerializer(Collection.objects.all(), many=True).data

    def test_fieldnames_in_right_order(self):
        renderer = CollectionCSVRenderer()
        renderer.render(self.file, self.content)
        self.file.seek(0)
        reader = csv.DictReader(codecs.getreader('utf-8')(self.file), delimiter='\t')
        fieldnames = ['Catchment', 'Country', 'NUTS/LAU Id', 'Collector', 'Collection System', 'Waste Category',
                      'Allowed Materials', 'Connection Rate', 'Connection Rate Year', 'Frequency', 'Population',
                      'Population Density', 'Comments', 'Sources', 'Created by', 'Created at', 'Last modified by',
                      'Last modified at']
        self.assertListEqual(fieldnames, list(reader.fieldnames))
        self.assertEqual(2, sum(1 for _ in reader))

    def test_allowed_materials_formatted_as_comma_separated_list_in_one_field(self):
        renderer = CollectionCSVRenderer()
        renderer.render(self.file, self.content)
        self.file.seek(0)
        reader = csv.DictReader(codecs.getreader('utf-8')(self.file), delimiter='\t')
        for row in reader:
            self.assertEqual('Test material 1, Test material 2', row['Allowed Materials'])

    def test_regression_flyers_without_urls_dont_raise_type_error(self):
        rogue_flyer = WasteFlyer.objects.create(owner=self.owner, title='Rogue flyer without url', abbreviation='RF')
        defected_collection = Collection.objects.get(name='collection1')
        defected_collection.flyers.add(rogue_flyer)
        renderer = CollectionCSVRenderer()
        renderer.render(self.file, self.content)
        self.file.seek(0)
        reader = csv.DictReader(codecs.getreader('utf-8')(self.file), delimiter='\t')
        self.assertEqual(Collection.objects.count(), len(list(reader)))


class CollectionXLSXRendererTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        member.user_permissions.add(Permission.objects.get(codename='add_collection'))

        MaterialCategory.objects.create(owner=owner, name='Biowaste component')
        material1 = WasteComponent.objects.create(owner=owner, name='Test material 1')
        material2 = WasteComponent.objects.create(owner=owner, name='Test material 2')
        waste_stream = WasteStream.objects.create(
            owner=owner,
            name='Test waste stream',
            category=WasteCategory.objects.create(owner=owner, name='Test category'),
        )
        waste_stream.allowed_materials.add(material1)
        waste_stream.allowed_materials.add(material2)

        waste_flyer = WasteFlyer.objects.create(
            owner=owner,
            abbreviation='WasteFlyer123',
            url='https://www.test-flyer.org'
        )
        frequency = CollectionFrequency.objects.create(owner=owner, name='Test Frequency')
        nuts = NutsRegion.objects.create(owner=owner, name='Test NUTS', nuts_id='DE123', cntr_code='DE')
        catchment = Catchment.objects.create(owner=owner, name='Test catchment', region=nuts.region_ptr)
        for i in range(1, 3):
            collection = Collection.objects.create(
                owner=owner,
                name=f'collection{i}',
                catchment=catchment,
                collector=Collector.objects.create(owner=owner, name=f'collector{1}'),
                collection_system=CollectionSystem.objects.create(owner=owner, name='Test system'),
                waste_stream=waste_stream,
                connection_rate=0.7,
                connection_rate_year=2020,
                frequency=frequency,
                description='This is a test case.'
            )
            collection.flyers.add(waste_flyer)

    def setUp(self):
        self.file = BytesIO()

    def test_contains_all_labels_in_right_order(self):
        renderer = CollectionXLSXRenderer()
        qs = Collection.objects.all()
        content = CollectionFlatSerializer(qs, many=True).data
        renderer.render(self.file, content)
        wb = load_workbook(self.file)
        ws = wb.active
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
            'population': 'Population',
            'population_density': 'Population Density',
            'comments': 'Comments',
            'sources': 'Sources',
            'created_by': 'Created by',
            'created_at': 'Created at',
            'lastmodified_by': 'Last modified by',
            'lastmodified_at': 'Last modified at'
        }
        for column, (key, value) in enumerate(content[0].items(), start=1):
            self.assertEqual(labels[key], ws.cell(row=1, column=column).value)