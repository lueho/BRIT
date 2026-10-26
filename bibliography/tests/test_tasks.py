"""Tests for bibliography.tasks."""

from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from ..models import Source
from ..tasks import check_stale_source_urls


class CheckStaleSourceUrlsTestCase(TestCase):
    """#391: periodic re-validation must cover never-checked and stale URLs
    while skipping fresh checks and URL-less sources."""

    @classmethod
    def setUpTestData(cls):
        today = timezone.localdate()
        cls.unchecked = Source.objects.create(
            title="Unchecked", url="https://example.org/unchecked"
        )
        cls.stale = Source.objects.create(
            title="Stale",
            url="https://example.org/stale",
            url_checked=today - timedelta(days=60),
        )
        cls.fresh = Source.objects.create(
            title="Fresh",
            url="https://example.org/fresh",
            url_checked=today,
        )
        cls.no_url = Source.objects.create(title="No URL")
        cls.stale_flyer = Source.objects.create(
            title="Stale flyer",
            type="waste_flyer",
            url="https://example.org/flyer.pdf",
            url_checked=today - timedelta(days=60),
        )

    def _enqueued(self, **kwargs):
        with patch("bibliography.tasks.chord") as mock_chord:
            check_stale_source_urls(**kwargs)
        signatures = mock_chord.call_args[0][0]
        return {sig.args[0]: sig.task for sig in signatures}

    def _enqueued_pks(self, **kwargs):
        return set(self._enqueued(**kwargs))

    def test_routes_waste_flyers_to_flyer_task_with_wayback_recovery(self):
        enqueued = self._enqueued()
        self.assertEqual(enqueued[self.stale_flyer.pk], "check_wasteflyer_url")
        self.assertEqual(enqueued[self.stale.pk], "check_source_url")
        self.assertEqual(enqueued[self.unchecked.pk], "check_source_url")

    def test_enqueues_unchecked_and_stale_sources(self):
        enqueued = self._enqueued_pks()
        self.assertIn(self.unchecked.pk, enqueued)
        self.assertIn(self.stale.pk, enqueued)

    def test_skips_fresh_and_url_less_sources(self):
        enqueued = self._enqueued_pks()
        self.assertNotIn(self.fresh.pk, enqueued)
        self.assertNotIn(self.no_url.pk, enqueued)

    def test_stale_days_threshold_is_respected(self):
        boundary = Source.objects.create(
            title="Boundary",
            url="https://example.org/boundary",
            url_checked=timezone.localdate() - timedelta(days=10),
        )
        self.assertIn(boundary.pk, self._enqueued_pks(stale_days=5))
        self.assertNotIn(boundary.pk, self._enqueued_pks(stale_days=30))

    def test_stale_url_recheck_is_on_the_beat_schedule(self):
        scheduled_tasks = {
            entry["task"] for entry in settings.CELERY_BEAT_SCHEDULE.values()
        }
        self.assertIn("check_stale_source_urls", scheduled_tasks)
