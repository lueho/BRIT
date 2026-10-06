from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import quote, unquote, urlencode

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models.signals import post_save, pre_save
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase, TestCase
from factory.django import mute_signals

from sources.waste_collection.models import Collection
from utils.object_management.models import UserCreatedObject
from utils.object_management.templatetags.moderation_tags import (
    collection_description_to_html,
    detail_or_review_url,
    has_pending_review_items_for_user,
    markdown_to_html,
    safe_back_url,
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


class DetailOrReviewUrlTagTests(SimpleTestCase):
    """Regression tests for the recursive ?back=/?next= crawler trap.

    Embedding request.get_full_path() into a ``back``/``next`` param must not
    carry over return-path params that are already present on the current URL.
    Otherwise every list->detail->list round trip nests the parameter deeper
    and crawlers discover an unbounded URL space.
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.obj = SimpleNamespace(
            get_absolute_url=lambda: "/materials/samples/9/",
            publication_status="published",
        )

    def tag_url(self, path):
        request = self.factory.get(path)
        return detail_or_review_url({"request": request}, self.obj, use_back=True)

    def test_back_param_contains_current_path(self):
        url = self.tag_url("/materials/samples/?scope=published")

        self.assertEqual(
            url,
            "/materials/samples/9/?back="
            + quote("/materials/samples/?scope=published", safe=""),
        )

    def test_existing_back_param_is_stripped_from_target(self):
        url = self.tag_url("/materials/samples/?scope=published&back=/other/")

        self.assertEqual(
            unquote(url),
            "/materials/samples/9/?back=/materials/samples/?scope=published",
        )

    def test_next_and_return_to_params_are_stripped(self):
        url = self.tag_url("/things/?next=/y/&return_to=/z/&page=2")

        self.assertEqual(unquote(url), "/materials/samples/9/?back=/things/?page=2")

    def test_repeated_back_params_are_all_stripped(self):
        url = self.tag_url("/things/?back=/a/&back=/b/")

        self.assertEqual(unquote(url), "/materials/samples/9/?back=/things/")

    def test_without_request_returns_plain_url(self):
        url = detail_or_review_url({}, self.obj, use_back=True)

        self.assertEqual(url, "/materials/samples/9/")


class SafeBackUrlTagTests(SimpleTestCase):
    """The back breadcrumb must not echo crawler-trap URLs.

    Values carrying nested return-path params are leftovers of the historical
    unbounded ?back=/?next= nesting; echoing them into a followable link keeps
    feeding the crawler the trap. Long ordinary filter URLs stay intact.
    """

    def setUp(self):
        self.factory = RequestFactory()

    def back_url(self, path):
        request = self.factory.get(path)
        return safe_back_url({"request": request})

    def test_simple_back_url_is_returned(self):
        url = self.back_url("/materials/samples/9/?back=/materials/samples/")

        self.assertEqual(url, "/materials/samples/")

    def test_back_url_with_ordinary_query_params_is_returned(self):
        url = self.back_url(
            "/materials/samples/9/?back="
            + quote("/materials/samples/?scope=published&page=2", safe="")
        )

        self.assertEqual(url, "/materials/samples/?scope=published&page=2")

    def test_external_back_url_is_dropped(self):
        url = self.back_url("/x/?back=https://evil.example.com/phish")

        self.assertEqual(url, "")

    def test_nested_back_param_is_dropped(self):
        nested = "/materials/samples/?back=" + quote("/materials/samples/", safe="")
        url = self.back_url("/x/?back=" + quote(nested, safe=""))

        self.assertEqual(url, "")

    def test_nested_next_and_return_to_params_are_dropped(self):
        for nested_param in ("next", "return_to"):
            with self.subTest(nested_param=nested_param):
                nested = f"/list/?{nested_param}=/detail/1/"
                url = self.back_url("/x/?back=" + quote(nested, safe=""))

                self.assertEqual(url, "")

    def test_back_url_to_modal_fragment_is_dropped(self):
        for modal_path in (
            "/materials/componentgroups/5/modal/",
            "/object_management/modal/approve/1/2/",
        ):
            with self.subTest(modal_path=modal_path):
                url = self.back_url(
                    "/materials/componentgroups/5/?back=" + quote(modal_path, safe="")
                )

                self.assertEqual(url, "")

    def test_back_url_with_modal_in_query_only_is_returned(self):
        url = self.back_url("/x/?back=" + quote("/materials/samples/?q=modal", safe=""))

        self.assertEqual(url, "/materials/samples/?q=modal")

    def test_long_ordinary_filtered_back_url_is_returned(self):
        filters = urlencode(
            [("scope", "published")]
            + [("material", str(pk)) for pk in range(1000, 1120)]
        )
        list_url = f"/materials/samples/?{filters}"
        self.assertGreater(len(list_url), 1000)

        url = self.back_url("/materials/samples/9/?back=" + quote(list_url, safe=""))

        self.assertEqual(url, list_url)

    def test_without_request_returns_empty(self):
        self.assertEqual(safe_back_url({}), "")


class ContextNavNoFollowTests(SimpleTestCase):
    """Back breadcrumbs are crawlable anchors into the ?back= URL space, so
    every context nav must mark them nofollow."""

    CONTEXT_NAV_TEMPLATES = (
        "includes/sdv2_context_nav.html",
        "materials/includes/sample_context_nav.html",
        "processes/includes/process_context_nav.html",
    )

    def test_back_link_is_nofollow(self):
        request = RequestFactory().get("/x/?back=/materials/samples/")

        for template_name in self.CONTEXT_NAV_TEMPLATES:
            with self.subTest(template=template_name):
                rendered = Template(f'{{% include "{template_name}" %}}').render(
                    Context({"request": request})
                )

                self.assertIn('href="/materials/samples/"', rendered)
                self.assertIn('rel="nofollow"', rendered)


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
