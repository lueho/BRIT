from django.test import TestCase
from django.contrib.auth.models import User, Permission
from mock import patch, Mock

from maps.models import Catchment
from users.models import get_default_owner

from ..models import (Collection, CollectionSystem, CollectionFrequency, Collector, MaterialCategory, WasteCategory,
                      WasteComponent, WasteFlyer, WasteStream)
from ..renderers import CollectionXLSXRenderer
from ..serializers import CollectionFlatSerializer
from ..tasks import export_collections_to_file


@patch('brit.storages.write_file_for_download')
class ExportCollectionToFileTestCase(TestCase):

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
        for i in range(1, 3):
            collection = Collection.objects.create(
                owner=owner,
                name=f'collection{i}',
                catchment=Catchment.objects.create(owner=owner, name='Test catchment'),
                collector=Collector.objects.create(owner=owner, name=f'collector{i}'),
                collection_system=CollectionSystem.objects.create(owner=owner, name='Test system'),
                waste_stream=waste_stream,
                connection_rate=0.7,
                connection_rate_year=2020,
                frequency=frequency,
                description='This is a test case.'
            )
            collection.flyers.add(waste_flyer)

    def setUp(self):
        self.collector = Collector.objects.get(name='collector1')
        self.mock_task = Mock()
        self.mock_task.request.id = 1234
        self.wrapped_export_collections_to_file = export_collections_to_file.__wrapped__.__func__
        qs = Collection.objects.filter(collector__pk=self.collector.pk)
        self.data = CollectionFlatSerializer(qs, many=True).data

    def test_url_is_passed_through(self, mock_write):
        mock_write.return_value = 'https://download.file'
        url = self.wrapped_export_collections_to_file(self.mock_task, 'xlsx', {'collector': [str(self.collector.pk)]})
        self.assertEqual(url, 'https://download.file')

    def test_write_function_is_called_once_with_correct_data(self, mock_write):
        mock_write.return_value = 'https://download.file'
        self.wrapped_export_collections_to_file(self.mock_task, 'xlsx', {'collector': [str(self.collector.pk)]})
        mock_write.assert_called_once_with('collections_1234.xlsx', self.data, CollectionXLSXRenderer)

    def test_integration(self, mock_write):
        task = export_collections_to_file.apply(args=['xlsx', {'collector': [str(self.collector.pk)]}])
        while task.status == 'PENDING':
            self.assertEqual('PENDING', task.status)
        self.assertEqual('SUCCESS', task.status)
