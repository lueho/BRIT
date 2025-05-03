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
from ..tasks import (check_wasteflyer_url, check_wasteflyer_urls, check_wasteflyer_urls_callback)


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
