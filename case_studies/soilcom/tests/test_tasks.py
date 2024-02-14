from celery import chord
from factory.django import mute_signals

from django.contrib.auth.models import User, Permission
from django.db.models import signals
from django.http.request import QueryDict, MultiValueDict
from django.test import TestCase
from mock import patch, Mock

from maps.models import Region
from users.models import get_default_owner

from ..models import (Collection, CollectionCatchment, CollectionSystem, CollectionFrequency, Collector,
                      MaterialCategory, WasteCategory, WasteComponent, WasteFlyer, WasteStream)
from ..renderers import CollectionXLSXRenderer
from ..serializers import CollectionFlatSerializer
from ..tasks import (export_collections_to_file, check_wasteflyer_urls, check_wasteflyer_url,
                     check_wasteflyer_urls_callback)


@patch('utils.file_export.storages.write_file_for_download')
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
        with mute_signals(signals.post_save):
            waste_flyer = WasteFlyer.objects.create(
                owner=owner,
                abbreviation='WasteFlyer123',
                url='https://www.test-flyer.org'
            )
        frequency = CollectionFrequency.objects.create(owner=owner, name='Test Frequency')
        region = Region.objects.create(owner=owner, name='Test Region')
        catchment = CollectionCatchment.objects.create(owner=owner, name='Test catchment', region=region)
        for i in range(1, 3):
            collection = Collection.objects.create(
                owner=owner,
                name=f'collection{i}',
                catchment=catchment,
                collector=Collector.objects.create(owner=owner, name=f'collector{i}'),
                collection_system=CollectionSystem.objects.create(owner=owner, name='Test system'),
                waste_stream=waste_stream,
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


class CheckWasteFlyerUrlsTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        with mute_signals(signals.post_save):
            for i in range(1, 5):
                WasteFlyer.objects.create(
                    owner=owner,
                    title=f'Waste flyer {i}',
                    abbreviation=f'WF{i}',
                    url_valid=i % 2 == 0
                )

    def setUp(self):
        self.flyer = WasteFlyer.objects.first

    def test_initial(self):
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

    def test_something(self):
        callback = check_wasteflyer_urls_callback.s()
        header = [check_wasteflyer_url.s(flyer.pk) for flyer in WasteFlyer.objects.all()]
        result = chord(header)(callback)
