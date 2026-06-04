from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models.signals import post_save, pre_save
from django.template import Context, Template
from django.test import TestCase
from factory.django import mute_signals

from sources.waste_collection.models import Collection
from utils.object_management.models import UserCreatedObject
from utils.object_management.templatetags.moderation_tags import (
    collection_description_to_html,
    has_pending_review_items_for_user,
    markdown_to_html,
)


class PendingReviewSignalTagTests(TestCase):
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
        cache.delete(f"has_pending_review_items_{self.user.id}")

    def test_pending_review_signal_is_true_when_review_items_exist(self):
        has_items = has_pending_review_items_for_user(self.user)

        self.assertIs(has_items, True)

    def test_pending_review_signal_returns_boolean(self):
        has_items = has_pending_review_items_for_user(self.user)

        self.assertIs(has_items, True)

    def test_pending_review_signal_uses_cache_on_second_call(self):
        first = has_pending_review_items_for_user(self.user)
        second = has_pending_review_items_for_user(self.user)

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

    def test_collection_description_filter_normalizes_legacy_double_semicolons(self):
        rendered = collection_description_to_html("First comment ;; Second comment")

        self.assertIn("<p>First comment</p>", rendered)
        self.assertIn("<p>Second comment</p>", rendered)
        self.assertNotIn(";;", rendered)

    def test_collection_description_filter_normalizes_spaced_legacy_semicolons(self):
        rendered = collection_description_to_html("First comment ; ; Second comment")

        self.assertIn("<p>First comment</p>", rendered)
        self.assertIn("<p>Second comment</p>", rendered)
        self.assertNotIn("; ;", rendered)

    @patch(
        "utils.object_management.templatetags.moderation_tags.import_module",
        side_effect=ModuleNotFoundError(
            "sources.waste_collection.description_formatting"
        ),
    )
    def test_collection_description_filter_works_without_plugin_formatter(
        self, _mock_import_module
    ):
        rendered = collection_description_to_html("First comment ;; Second comment")

        self.assertIn("<p>First comment</p>", rendered)
        self.assertIn("<p>Second comment</p>", rendered)

    def test_headings_are_not_rendered_as_h_tags(self):
        rendered = markdown_to_html("## Heading\nNormal")

        self.assertNotIn("<h2>", rendered)
        self.assertIn("<p>## Heading</p>", rendered)
