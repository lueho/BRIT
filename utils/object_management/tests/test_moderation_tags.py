from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models.signals import post_save, pre_save
from django.template import Context, Template
from django.test import RequestFactory, TestCase
from factory.django import mute_signals

from case_studies.soilcom.models import Collection
from utils.object_management.models import UserCreatedObject
from utils.object_management.templatetags.moderation_tags import (
    markdown_to_html,
    pending_review_count_for_user,
)
from utils.object_management.views import ReviewDashboardView


class PendingReviewCountTagTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="moderation-tag-staff",
            password="irrelevant",
            is_staff=True,
        )
        cls.owner = get_user_model().objects.create_user(
            username="moderation-tag-owner",
            password="irrelevant",
        )

        with mute_signals(post_save, pre_save):
            for index in range(11):
                Collection.objects.create(
                    name=f"Review Collection {index}",
                    owner=cls.owner,
                    publication_status=UserCreatedObject.STATUS_REVIEW,
                )

    def setUp(self):
        cache.delete(f"pending_review_count_{self.user.id}")

    def test_pending_review_count_matches_unfiltered_dashboard_results(self):
        with patch.object(ReviewDashboardView, "paginate_by", 1):
            request = RequestFactory().get("/")
            request.user = self.user

            view = ReviewDashboardView()
            view.setup(request)
            view.request = request

            expected_count = len(view.collect_review_items())
            actual_count = pending_review_count_for_user(self.user)

        self.assertEqual(actual_count, expected_count)
        self.assertEqual(actual_count, 10)

    def test_pending_review_count_uses_cache_on_second_call(self):
        first = pending_review_count_for_user(self.user)
        second = pending_review_count_for_user(self.user)

        self.assertEqual(first, second)

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


class MarkdownToHtmlFilterTests(TestCase):
    def test_allows_bold_and_lists(self):
        rendered = markdown_to_html("**Bold**\n- one\n- two\n1. three")

        self.assertIn("<strong>Bold</strong>", rendered)
        self.assertIn("<ul>", rendered)
        self.assertIn("<ol>", rendered)
        self.assertIn("<li>one</li>", rendered)

    def test_headings_are_not_rendered_as_h_tags(self):
        rendered = markdown_to_html("## Heading\nNormal")

        self.assertNotIn("<h2>", rendered)
        self.assertIn("<p>## Heading</p>", rendered)
