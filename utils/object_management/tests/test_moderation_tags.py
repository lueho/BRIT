from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.template import Context, Template
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from utils.object_management.templatetags.moderation_tags import (
    pending_review_count_for_user,
)


class PendingReviewCountTagTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="moderation-tag-staff",
            password="irrelevant",
            is_staff=True,
        )

    def setUp(self):
        cache.delete(f"pending_review_count_{self.user.id}")

    def test_pending_review_count_does_not_issue_duplicate_count_queries(self):
        with CaptureQueriesContext(connection) as ctx:
            pending_review_count_for_user(self.user)

        count_queries = [
            query["sql"]
            for query in ctx.captured_queries
            if query["sql"].startswith("SELECT COUNT(*)")
        ]

        self.assertGreater(len(count_queries), 0)
        self.assertEqual(len(count_queries), len(set(count_queries)))

    def test_pending_review_count_uses_cache_on_second_call(self):
        first = pending_review_count_for_user(self.user)

        with CaptureQueriesContext(connection) as ctx:
            second = pending_review_count_for_user(self.user)

        count_queries = [
            query["sql"]
            for query in ctx.captured_queries
            if query["sql"].startswith("SELECT COUNT(*)")
        ]

        self.assertEqual(first, second)
        self.assertEqual(count_queries, [])

    def test_review_status_icon_can_use_precomputed_policy(self):
        obj = SimpleNamespace(
            is_private=True,
            is_in_review=False,
            is_declined=False,
            is_published=False,
            is_archived=False,
        )
        policy = {"is_owner": True, "is_moderator": False, "is_staff": False}
        template = Template(
            '{% include "object_management/review_status_icon.html" with object=obj policy=policy %}'
        )

        rendered = template.render(Context({"obj": obj, "policy": policy}))

        self.assertIn("fa-lock", rendered)
