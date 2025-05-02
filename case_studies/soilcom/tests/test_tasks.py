from collections import namedtuple

from celery import chord
from django.contrib.auth.models import Permission, User
from django.db.models import signals
from django.http.request import MultiValueDict, QueryDict
from django.test import TestCase
from factory.django import mute_signals
from mock import Mock, patch

from maps.models import Region
from ..models import (Collection, CollectionCatchment, CollectionFrequency, CollectionSystem, Collector,
                      MaterialCategory, WasteCategory, WasteComponent, WasteFlyer, WasteStream)
from ..renderers import CollectionXLSXRenderer
from ..serializers import CollectionFlatSerializer
from ..tasks import (check_wasteflyer_url, check_wasteflyer_urls, check_wasteflyer_urls_callback,
                     export_collections_to_file)


@patch('utils.file_export.storages.write_file_for_download')
class ExportCollectionToFileTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')
        member = User.objects.create(username='member')
        member.user_permissions.add(Permission.objects.get(codename='add_collection'))

        MaterialCategory.objects.create(name='Biowaste component')
        material1 = WasteComponent.objects.create(name='Test material 1')
        material2 = WasteComponent.objects.create(name='Test material 2')
        waste_stream = WasteStream.objects.create(
            name='Test waste stream',
            category=WasteCategory.objects.create(name='Test category'),
        )
        waste_stream.allowed_materials.add(material1)
        waste_stream.allowed_materials.add(material2)
        with mute_signals(signals.post_save):
            waste_flyer = WasteFlyer.objects.create(
                abbreviation='WasteFlyer123',
                url='https://www.test-flyer.org'
            )
        frequency = CollectionFrequency.objects.create(name='Test Frequency')
        region = Region.objects.create(name='Test Region')
        catchment = CollectionCatchment.objects.create(name='Test catchment', region=region)
        # Existing test data for other tests: create both compulsory and voluntary collections
        for i in range(1, 5):
            connection_type = 'COMPULSORY' if i % 2 == 0 else 'VOLUNTARY'
            collection = Collection.objects.create(
                name=f'collection{i}',
                catchment=catchment,
                collector=Collector.objects.create(name=f'collector{i}'),
                collection_system=CollectionSystem.objects.create(name=f'Test system {i}'),
                waste_stream=waste_stream,
                frequency=frequency,
                description='This is a test case.',
                connection_type=connection_type,
            )
            collection.flyers.add(waste_flyer)

    def setUp(self):
        self.collector = Collector.objects.get(name='collector1')
        self.mock_task = Mock()
        self.mock_task.request.id = 1234
        self.wrapped_export_collections_to_file = export_collections_to_file.__wrapped__.__func__
        self.all_collection_ids = list(Collection.objects.values_list('pk', flat=True))
        qs = Collection.objects.filter(collector__pk=self.collector.pk)
        self.data = CollectionFlatSerializer(qs, many=True).data

    def test_url_is_passed_through(self, mock_write):
        mock_write.return_value = 'https://download.file'
        url = self.wrapped_export_collections_to_file(self.mock_task, 'xlsx', {'collector': [str(self.collector.pk)]}, self.all_collection_ids)
        self.assertEqual(url, 'https://download.file')

    def test_write_function_is_called_once_with_correct_data(self, mock_write):
        mock_write.return_value = 'https://download.file'
        self.wrapped_export_collections_to_file(self.mock_task, 'xlsx', {'collector': [str(self.collector.pk)]}, self.all_collection_ids)
        mock_write.assert_called_once_with('collections_1234.xlsx', self.data, CollectionXLSXRenderer)

    def test_integration(self, mock_write):
        task = export_collections_to_file.apply(args=['xlsx', {'collector': [str(self.collector.pk)]}, self.all_collection_ids])
        while task.status == 'PENDING':
            self.assertEqual('PENDING', task.status)
        self.assertEqual('SUCCESS', task.status)

    def test_connection_type_filter_is_respected(self, mock_write):
        """
        Export should only include collections matching the connection_type filter.
        This test now uses only the collections created in setUpTestData via the loop.
        """
        mock_write.return_value = 'https://download.file'
        # There should be 2 compulsory and 2 voluntary collections
        # Export only compulsory
        url = self.wrapped_export_collections_to_file(self.mock_task, 'xlsx', {'connection_type': ['COMPULSORY']}, self.all_collection_ids)
        args, kwargs = mock_write.call_args
        exported_data = args[1]
        self.assertEqual(len(exported_data), 2)
        self.assertTrue(all(row['connection_type'] == 'Compulsory' for row in exported_data))
        # Export only voluntary
        url = self.wrapped_export_collections_to_file(self.mock_task, 'xlsx', {'connection_type': ['VOLUNTARY']}, self.all_collection_ids)
        args, kwargs = mock_write.call_args
        exported_data = args[1]
        self.assertEqual(len(exported_data), 2)
        self.assertTrue(all(row['connection_type'] == 'Voluntary' for row in exported_data))
        # Export with no filter: both types should be present
        url = self.wrapped_export_collections_to_file(self.mock_task, 'xlsx', {}, self.all_collection_ids)
        args, kwargs = mock_write.call_args
        exported_data = args[1]
        exported_types = set(row['connection_type'] for row in exported_data)
        self.assertIn('Compulsory', exported_types)
        self.assertIn('Voluntary', exported_types)


@patch('case_studies.soilcom.tests.test_tasks.check_wasteflyer_urls.apply')
@patch('case_studies.soilcom.tests.test_tasks.chord')
class CheckWasteFlyerUrlsTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        with mute_signals(signals.post_save):
            for i in range(1, 5):
                WasteFlyer.objects.create(
                    title=f'Waste flyer {i}',
                    abbreviation=f'WF{i}',
                    url_valid=i % 2 == 0
                )

    def setUp(self):
        self.flyer = WasteFlyer.objects.first

    def test_initial(self, mock_chord, mock_apply):
        MockAsyncResult = namedtuple('MockAsyncResult', ['status', 'get'])
        mock_apply.return_value = MockAsyncResult(status='SUCCESS', get=lambda: None)
        self.assertEqual(4, WasteFlyer.objects.count())
        params = {
            'csrfmiddlewaretoken': ['Hm7MXB2NjRCOIpNbGaRKR87VCHM5KwpR1t4AdZFgaqKfqui1EJwhKKmkxFKDfL3h'],
            'url_valid': ['False'],
            'page': ['2']
        }
        qdict = QueryDict('', mutable=True)
        qdict.update(MultiValueDict(params))
        newparams = qdict.copy()
        newparams.pop('csrfmiddlewaretoken')
        newparams.pop('page')
        result = check_wasteflyer_urls.apply(args=[newparams])
        while result.status == 'PENDING':
            self.assertEqual('PENDING', result.status)
        if result.status == 'FAILURE':
            result.get()
        self.assertEqual('SUCCESS', result.status)

    def test_chord(self, mock_chord, mock_apply):
        mock_chord.return_value = lambda x: type('task', (object,), {'task_id': 'fake_task_id'})
        mock_apply.side_effect = [type('task', (object,), {'status': 'SUCCESS'}) for _ in WasteFlyer.objects.all()]
        callback = check_wasteflyer_urls_callback.s()
        header = [check_wasteflyer_url.s(flyer.pk) for flyer in WasteFlyer.objects.all()]
        result = chord(header)(callback)
        self.assertEqual(result.task_id, 'fake_task_id')
