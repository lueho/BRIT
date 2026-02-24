from collections import namedtuple
from datetime import date
from unittest.mock import patch

from celery import chord
from django.db.models import signals
from django.http.request import MultiValueDict, QueryDict
from django.test import TestCase
from factory.django import mute_signals

from ..models import (
    Collection,
    WasteFlyer,
)
from ..tasks import (
    check_wasteflyer_url,
    check_wasteflyer_urls,
    check_wasteflyer_urls_callback,
)


@patch("case_studies.soilcom.tests.test_tasks.check_wasteflyer_urls.apply")
@patch("case_studies.soilcom.tests.test_tasks.chord")
class CheckWasteFlyerUrlsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with mute_signals(signals.post_save):
            for i in range(1, 5):
                WasteFlyer.objects.create(
                    title=f"Waste flyer {i}",
                    abbreviation=f"WF{i}",
                    url_valid=i % 2 == 0,
                )

    def setUp(self):
        self.flyer = WasteFlyer.objects.first

    def test_initial(self, mock_chord, mock_apply):
        MockAsyncResult = namedtuple("MockAsyncResult", ["status", "get"])
        mock_apply.return_value = MockAsyncResult(status="SUCCESS", get=lambda: None)
        self.assertEqual(4, WasteFlyer.objects.count())
        params = {
            "csrfmiddlewaretoken": [
                "Hm7MXB2NjRCOIpNbGaRKR87VCHM5KwpR1t4AdZFgaqKfqui1EJwhKKmkxFKDfL3h"
            ],
            "url_valid": ["False"],
            "page": ["2"],
        }
        qdict = QueryDict("", mutable=True)
        qdict.update(MultiValueDict(params))
        newparams = qdict.copy()
        newparams.pop("csrfmiddlewaretoken")
        newparams.pop("page")
        result = check_wasteflyer_urls.apply(args=[newparams])
        while result.status == "PENDING":
            self.assertEqual("PENDING", result.status)
        if result.status == "FAILURE":
            result.get()
        self.assertEqual("SUCCESS", result.status)

    def test_chord(self, mock_chord, mock_apply):
        mock_chord.return_value = lambda x: type(
            "task", (object,), {"task_id": "fake_task_id"}
        )
        mock_apply.side_effect = [
            type("task", (object,), {"status": "SUCCESS"})
            for _ in WasteFlyer.objects.all()
        ]
        callback = check_wasteflyer_urls_callback.s()
        header = [
            check_wasteflyer_url.s(flyer.pk) for flyer in WasteFlyer.objects.all()
        ]
        result = chord(header)(callback)
        self.assertEqual(result.task_id, "fake_task_id")


@patch("case_studies.soilcom.tasks.find_wayback_snapshot_for_year")
@patch("case_studies.soilcom.tasks.check_url")
class CheckWasteFlyerUrlWaybackFallbackTestCase(TestCase):
    def setUp(self):
        with mute_signals(signals.post_save):
            self.flyer = WasteFlyer.objects.create(
                title="Waste flyer",
                abbreviation="WF",
                url="https://example.com/dead-flyer.pdf",
            )

        self.collection = Collection.objects.create(valid_from=date(2021, 1, 1))
        self.collection.flyers.add(self.flyer)

    def test_replaces_broken_url_with_year_snapshot(self, mock_check_url, mock_wayback):
        original_url = self.flyer.url
        mock_check_url.return_value = False
        mock_wayback.return_value = (
            "https://web.archive.org/web/20211230153000/"
            "https://example.com/dead-flyer.pdf"
        )

        check_wasteflyer_url(self.flyer.pk)

        self.flyer.refresh_from_db()
        self.assertTrue(self.flyer.url_valid)
        self.assertEqual(self.flyer.url, mock_wayback.return_value)
        mock_wayback.assert_called_once_with(original_url, 2021)

    def test_keeps_original_url_when_no_snapshot_exists(
        self, mock_check_url, mock_wayback
    ):
        original_url = self.flyer.url
        mock_check_url.return_value = False
        mock_wayback.return_value = None

        check_wasteflyer_url(self.flyer.pk)

        self.flyer.refresh_from_db()
        self.assertFalse(self.flyer.url_valid)
        self.assertEqual(self.flyer.url, original_url)
        mock_wayback.assert_called_once_with(original_url, 2021)

    def test_replaces_live_url_with_year_snapshot(self, mock_check_url, mock_wayback):
        original_url = self.flyer.url
        mock_check_url.return_value = True
        mock_wayback.return_value = (
            "https://web.archive.org/web/20211230153000/"
            "https://example.com/dead-flyer.pdf"
        )

        check_wasteflyer_url(self.flyer.pk)

        self.flyer.refresh_from_db()
        self.assertTrue(self.flyer.url_valid)
        self.assertEqual(self.flyer.url, mock_wayback.return_value)
        mock_wayback.assert_called_once_with(original_url, 2021)

    def test_keeps_live_url_when_no_snapshot_exists(self, mock_check_url, mock_wayback):
        original_url = self.flyer.url
        mock_check_url.return_value = True
        mock_wayback.return_value = None

        check_wasteflyer_url(self.flyer.pk)

        self.flyer.refresh_from_db()
        self.assertTrue(self.flyer.url_valid)
        self.assertEqual(self.flyer.url, original_url)
        mock_wayback.assert_called_once_with(original_url, 2021)

    def test_skips_wayback_lookup_when_url_is_already_archived(
        self, mock_check_url, mock_wayback
    ):
        with mute_signals(signals.post_save):
            self.flyer.url = (
                "https://web.archive.org/web/20211230153000/"
                "https://example.com/dead-flyer.pdf"
            )
            self.flyer.save()
        mock_check_url.return_value = True

        check_wasteflyer_url(self.flyer.pk)

        mock_wayback.assert_not_called()

    def test_returns_false_when_wasteflyer_was_deleted(
        self, mock_check_url, mock_wayback
    ):
        flyer_pk = self.flyer.pk
        self.flyer.delete()

        result = check_wasteflyer_url(flyer_pk)

        self.assertFalse(result)
        mock_check_url.assert_not_called()
        mock_wayback.assert_not_called()
