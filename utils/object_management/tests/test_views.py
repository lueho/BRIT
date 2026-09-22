import inspect
from datetime import timedelta
from typing import get_type_hints
from unittest.mock import patch
from urllib.parse import urlencode

from django.contrib.auth.models import AnonymousUser, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.db.models.signals import post_save, pre_save
from django.http import HttpResponse, HttpResponseRedirect
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from django_filters import CharFilter, FilterSet
from django_filters.views import FilterView
from factory.django import mute_signals

from bibliography.models import Author, Source
from distributions.models import TemporalDistribution
from maps.models import Catchment, Region
from maps.views import GeoDataSetPrivateGalleryView, GeoDataSetPublishedGalleryView
from sources.waste_collection.models import (
    Collection,
    CollectionPropertyValue,
    Collector,
)
from sources.waste_collection.views import (
    CollectionDetailView,
    CollectionPrivateListView,
    CollectionPublishedListView,
    CollectionReviewFilterView,
)
from utils.object_management.models import (
    ObjectEditorGrant,
    ReviewAction,
    UserCreatedObject,
    annotate_owner_review_feedback,
    populate_owner_review_feedback,
)
from utils.object_management.permissions import get_object_policy
from utils.object_management.views import (
    ReviewDashboardView,
    ReviewItemReference,
    UserCreatedObjectCreateView,
)
from utils.properties.models import Property, Unit

from ..views import (
    FilterDefaultsMixin,
    PrivateObjectFilterView,
    PublishedObjectFilterView,
    ReviewObjectFilterView,
)


class ReviewWorkflowViewTests(TestCase):
    """Test the views for the review workflow."""

    @classmethod
    def setUpTestData(cls):
        # Create users
        cls.owner = User.objects.create_user(username="owner")
        cls.moderator = User.objects.create_user(username="moderator")
        cls.regular_user = User.objects.create_user(username="regular")

        # Add moderator permissions
        content_type = ContentType.objects.get_for_model(Collection)
        permission, _ = Permission.objects.get_or_create(
            codename="can_moderate_collection",
            content_type=content_type,
            defaults={"name": "Can moderate collections"},
        )
        cls.moderator.user_permissions.add(permission)

        with mute_signals(post_save, pre_save):
            # Create test collections in different states
            cls.private_collection = Collection.objects.create(
                name="Private Collection",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )

        with mute_signals(post_save, pre_save):
            cls.review_collection = Collection.objects.create(
                name="Review Collection",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )

        cls.review_source = Source.objects.create(
            owner=cls.owner,
            title="Review Workflow Source",
        )
        cls.private_collection.sources.add(cls.review_source)
        cls.review_collection.sources.add(cls.review_source)

    def setUp(self):
        # Get content type for URLs
        self.content_type_id = ContentType.objects.get_for_model(Collection).id

    def test_submit_for_review_view(self):
        """Test the submit for review view."""
        url = reverse(
            "object_management:submit_for_review",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.private_collection.id,
            },
        )

        # Owner should be able to submit their private object
        self.client.force_login(self.owner)
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)  # Redirect after success

        # Refresh from database
        self.private_collection.refresh_from_db()
        self.assertEqual(
            self.private_collection.publication_status, UserCreatedObject.STATUS_REVIEW
        )

        # Regular user should not be able to submit someone else's private object
        with mute_signals(post_save, pre_save):
            self.private_collection.publication_status = (
                UserCreatedObject.STATUS_PRIVATE
            )
            self.private_collection.save()

        self.client.force_login(self.regular_user)
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)  # Permission denied

        # Refresh from database
        self.private_collection.refresh_from_db()
        self.assertEqual(
            self.private_collection.publication_status, UserCreatedObject.STATUS_PRIVATE
        )

    def test_submit_for_review_success_redirects_to_review_detail_next(self):
        url = reverse(
            "object_management:submit_for_review",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.private_collection.id,
            },
        )
        next_url = reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.private_collection.id,
            },
        )

        self.client.force_login(self.owner)
        with mute_signals(post_save, pre_save):
            response = self.client.post(url, {"next": next_url})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, next_url)
        self.private_collection.refresh_from_db()
        self.assertEqual(
            self.private_collection.publication_status,
            UserCreatedObject.STATUS_REVIEW,
        )
        self.assertIn(
            "Collection has been submitted for review.",
            [str(message) for message in get_messages(response.wsgi_request)],
        )

    def test_submit_for_review_without_source_or_flyer_succeeds(self):
        with mute_signals(post_save, pre_save):
            collection = Collection.objects.create(
                name="Collection Without Evidence",
                owner=self.owner,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )
        url = reverse(
            "object_management:submit_for_review",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": collection.id,
            },
        )
        next_url = reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": collection.id,
            },
        )

        self.client.force_login(self.owner)
        with mute_signals(post_save, pre_save):
            response = self.client.post(url, {"next": next_url})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, next_url)
        collection.refresh_from_db()
        self.assertEqual(
            collection.publication_status,
            UserCreatedObject.STATUS_REVIEW,
        )
        self.assertIn(
            "Collection has been submitted for review.",
            [str(message) for message in get_messages(response.wsgi_request)],
        )

    def test_submit_for_review_view_ajax_preflight_returns_204_without_state_change(
        self,
    ):
        url = reverse(
            "object_management:submit_for_review",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.private_collection.id,
            },
        )

        self.client.force_login(self.owner)
        response = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        self.assertEqual(response.status_code, 204)
        self.private_collection.refresh_from_db()
        self.assertEqual(
            self.private_collection.publication_status, UserCreatedObject.STATUS_PRIVATE
        )

    def test_submit_for_review_view_ajax_preflight_returns_403_without_permission(self):
        url = reverse(
            "object_management:submit_for_review",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.private_collection.id,
            },
        )

        self.client.force_login(self.regular_user)
        response = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        self.assertEqual(response.status_code, 403)
        self.private_collection.refresh_from_db()
        self.assertEqual(
            self.private_collection.publication_status, UserCreatedObject.STATUS_PRIVATE
        )

    def test_withdraw_from_review_view(self):
        """Test the withdraw from review view."""
        url = reverse(
            "object_management:withdraw_from_review",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )

        # Owner should be able to withdraw their object from review
        self.client.force_login(self.owner)
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)  # Redirect after success

        # Refresh from database
        self.review_collection.refresh_from_db()
        self.assertEqual(
            self.review_collection.publication_status, UserCreatedObject.STATUS_PRIVATE
        )

        # Regular user should not be able to withdraw someone else's object
        with mute_signals(post_save, pre_save):
            self.review_collection.publication_status = UserCreatedObject.STATUS_REVIEW
            self.review_collection.save()

        self.client.force_login(self.regular_user)
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)  # Permission denied

        # Refresh from database
        self.review_collection.refresh_from_db()
        self.assertEqual(
            self.review_collection.publication_status, UserCreatedObject.STATUS_REVIEW
        )

    def test_withdraw_from_review_view_redirects_to_detail_when_next_is_review_page(
        self,
    ):
        url = reverse(
            "object_management:withdraw_from_review",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )
        next_url = reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )

        self.client.force_login(self.owner)
        with mute_signals(post_save, pre_save):
            response = self.client.post(url, {"next": next_url})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.review_collection.get_absolute_url())
        self.review_collection.refresh_from_db()
        self.assertEqual(
            self.review_collection.publication_status, UserCreatedObject.STATUS_PRIVATE
        )

    def test_approve_view(self):
        """Test the approve view."""
        url = reverse(
            "object_management:approve_item",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )

        # Moderator should be able to approve an object in review
        self.client.force_login(self.moderator)
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)  # Redirect after success

        # Refresh from database
        self.review_collection.refresh_from_db()
        self.assertEqual(
            self.review_collection.publication_status,
            UserCreatedObject.STATUS_PUBLISHED,
        )
        self.assertEqual(self.review_collection.approved_by, self.moderator)

        # Regular user should not be able to approve any object
        with mute_signals(post_save, pre_save):
            self.review_collection.publication_status = UserCreatedObject.STATUS_REVIEW
            self.review_collection.approved_by = None
            self.review_collection.approved_at = None
            self.review_collection.save()

        self.client.force_login(self.regular_user)
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)  # Permission denied

        # Refresh from database
        self.review_collection.refresh_from_db()
        self.assertEqual(
            self.review_collection.publication_status, UserCreatedObject.STATUS_REVIEW
        )
        self.assertIsNone(self.review_collection.approved_by)

    def test_reject_view(self):
        """Test the reject view."""
        url = reverse(
            "object_management:reject_item",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )

        # Moderator should be able to reject an object in review
        self.client.force_login(self.moderator)
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)  # Redirect after success

        # Refresh from database
        self.review_collection.refresh_from_db()
        self.assertEqual(
            self.review_collection.publication_status, UserCreatedObject.STATUS_DECLINED
        )

        # Regular user should not be able to reject any object
        with mute_signals(post_save, pre_save):
            self.review_collection.publication_status = UserCreatedObject.STATUS_REVIEW
            self.review_collection.save()

        self.client.force_login(self.regular_user)
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)  # Permission denied

        # Refresh from database
        self.review_collection.refresh_from_db()
        self.assertEqual(
            self.review_collection.publication_status, UserCreatedObject.STATUS_REVIEW
        )

    def test_dashboard_view(self):
        """Test the review dashboard view."""
        url = reverse("object_management:review_dashboard")

        # Moderator should be able to see the dashboard
        self.client.force_login(self.moderator)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_add_review_comment_view_moderator_can_comment(self):
        """Moderator can add a review comment to an item."""
        url = reverse(
            "object_management:add_review_comment",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )

        self.client.force_login(self.moderator)
        response = self.client.post(url, data={"message": "Looks good"})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ReviewAction.objects.filter(
                content_type_id=self.content_type_id,
                object_id=self.review_collection.id,
                action=ReviewAction.ACTION_COMMENT,
                user=self.moderator,
                comment="Looks good",
            ).exists()
        )

    def test_add_review_comment_view_regular_user_forbidden(self):
        """Regular users cannot add a review comment to someone else's item."""
        url = reverse(
            "object_management:add_review_comment",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )

        self.client.force_login(self.regular_user)
        response = self.client.post(url, data={"message": "I should not post this"})

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type_id=self.content_type_id,
                object_id=self.review_collection.id,
                action=ReviewAction.ACTION_COMMENT,
                user=self.regular_user,
            ).exists()
        )


class ReviewDetailAccessTests(TestCase):
    """Ensure owner access to review detail works as intended."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner")
        cls.other = User.objects.create_user(username="other")
        ct = ContentType.objects.get_for_model(Collection)
        cls.ct_id = ct.id

        with mute_signals(post_save, pre_save):
            cls.obj_private = Collection.objects.create(
                name="Private",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )
            cls.obj_review = Collection.objects.create(
                name="In Review",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )
            cls.obj_declined = Collection.objects.create(
                name="Declined",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_DECLINED,
            )
            cls.obj_published = Collection.objects.create(
                name="Published",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )

    def test_owner_can_access_review_detail_in_review(self):
        url = reverse(
            "object_management:review_item_detail",
            kwargs={"content_type_id": self.ct_id, "object_id": self.obj_review.id},
        )
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_owner_can_access_review_detail_declined(self):
        url = reverse(
            "object_management:review_item_detail",
            kwargs={"content_type_id": self.ct_id, "object_id": self.obj_declined.id},
        )
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_owner_can_access_review_detail_private(self):
        url = reverse(
            "object_management:review_item_detail",
            kwargs={"content_type_id": self.ct_id, "object_id": self.obj_private.id},
        )
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_owner_can_access_review_detail_published(self):
        url = reverse(
            "object_management:review_item_detail",
            kwargs={"content_type_id": self.ct_id, "object_id": self.obj_published.id},
        )
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_non_owner_without_perm_cannot_access(self):
        url = reverse(
            "object_management:review_item_detail",
            kwargs={"content_type_id": self.ct_id, "object_id": self.obj_review.id},
        )
        self.client.force_login(self.other)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_review_detail_renders_markdown_comments(self):
        """Markdown comments are rendered as HTML in the review panel."""
        ReviewAction.objects.create(
            content_type_id=self.ct_id,
            object_id=self.obj_review.id,
            action=ReviewAction.ACTION_COMMENT,
            comment="**Bold observation**\n\n- first point",
            user=self.owner,
        )
        url = reverse(
            "object_management:review_item_detail",
            kwargs={"content_type_id": self.ct_id, "object_id": self.obj_review.id},
        )
        self.client.force_login(self.owner)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<strong>Bold observation</strong>")
        self.assertContains(response, "<li>first point</li>")

    # Dashboard behavior is covered in ReviewWorkflowViewTests.


class ReviewPipelineTypeHintTests(TestCase):
    """The review dashboard's filtering/collection pipeline is type-annotated.

    ``typing.get_type_hints`` resolves string annotations; a bad forward
    reference would raise, so this also guards against stale annotations.
    """

    def test_review_item_filter_is_fully_annotated(self):
        from utils.object_management.review_filtering import ReviewItemFilter

        for method_name in (
            "__init__",
            "filter",
            "_apply_search",
            "_apply_model_type_filter",
            "_apply_owner_filter",
            "_apply_date_filter",
            "_apply_ordering",
            "_apply_default_sort",
        ):
            with self.subTest(method=method_name):
                method = getattr(ReviewItemFilter, method_name)
                hints = get_type_hints(method)
                self.assertIn("return", hints)
                self.assertTrue(
                    all(
                        name in hints
                        for name in inspect.signature(method).parameters
                        if name != "self"
                    )
                )

    def test_review_dashboard_pipeline_methods_are_annotated(self):
        for method_name in (
            "get_available_models",
            "_get_review_references",
            "_hydrate_review_references",
            "collect_review_items",
            "has_review_items",
            "get_queryset",
            "_apply_database_review_filters",
            "_apply_requested_ordering",
        ):
            with self.subTest(method=method_name):
                hints = get_type_hints(getattr(ReviewDashboardView, method_name))
                self.assertIn("return", hints)

    def test_review_item_reference_is_a_typed_namedtuple(self):
        hints = get_type_hints(ReviewItemReference)
        self.assertEqual(list(hints), ["model", "pk", "name", "submitted_at"])
        self.assertTrue(issubclass(ReviewItemReference, tuple))


class MockFilterSet(FilterSet):
    name = CharFilter(
        field_name="name", lookup_expr="icontains", initial="Initial name"
    )

    class Meta:
        model = Property
        fields = ["name"]


class MockFilterView(FilterDefaultsMixin, FilterView):
    filterset_class = MockFilterSet


class TestPropertyCreateView(UserCreatedObjectCreateView):
    model = Property
    fields = ["name", "unit"]
    permission_required = "properties.add_property"


class FilterDefaultsMixinTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_get_default_filters(self):
        view = MockFilterView()
        default_filters = view.get_default_filters()
        self.assertEqual(default_filters, {"name": "Initial name"})

    def test_redirect_with_default_filters(self):
        request = self.factory.get("/")
        response = MockFilterView.as_view()(request)
        self.assertIsInstance(response, HttpResponseRedirect)
        expected_query = urlencode({"name": "Initial name"})
        self.assertTrue(expected_query in response.url)

    def test_redirect_skips_filter_view_get(self):
        request = self.factory.get("/filtered/")

        with patch.object(FilterView, "get") as get:
            response = MockFilterView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/filtered/?name=Initial+name")
        get.assert_not_called()

    def test_redirect_encodes_overridden_defaults(self):
        request = self.factory.get("/filtered/")
        defaults = {"name": "A&B / café", "scope": "private"}

        with patch.object(MockFilterView, "get_default_filters", return_value=defaults):
            response = MockFilterView.as_view()(request)

        self.assertEqual(response.url, f"/filtered/?{urlencode(defaults)}")

    def test_existing_query_parameters_use_filter_view(self):
        for query in ("?name=Other+name", "?name=", "?page=2", "?scope=private"):
            with self.subTest(query=query):
                request = self.factory.get(f"/filtered/{query}")
                expected_response = HttpResponse()
                with (
                    patch.object(
                        FilterView, "get", return_value=expected_response
                    ) as get,
                    patch.object(MockFilterView, "get_default_filters") as defaults,
                ):
                    response = MockFilterView.as_view()(request)

                self.assertIs(response, expected_response)
                get.assert_called_once_with(request)
                defaults.assert_not_called()

    def test_no_defaults_uses_filter_view(self):
        request = self.factory.get("/filtered/")
        expected_response = HttpResponse()

        with (
            patch.object(MockFilterView, "get_default_filters", return_value={}),
            patch.object(FilterView, "get", return_value=expected_response) as get,
        ):
            response = MockFilterView.as_view()(request)

        self.assertIs(response, expected_response)
        get.assert_called_once_with(request)

    def test_head_uses_filter_view_without_default_redirect(self):
        request = self.factory.head("/filtered/")
        expected_response = HttpResponse()

        with (
            patch.object(FilterView, "get", return_value=expected_response) as get,
            patch.object(MockFilterView, "get_default_filters") as defaults,
        ):
            response = MockFilterView.as_view()(request)

        self.assertIs(response, expected_response)
        get.assert_called_once_with(request)
        defaults.assert_not_called()

    def test_scoped_list_redirects_do_not_query_database(self):
        for view_class, scope in (
            (CollectionPublishedListView, "published"),
            (CollectionPrivateListView, "private"),
            (CollectionReviewFilterView, "review"),
            (GeoDataSetPublishedGalleryView, "published"),
            (GeoDataSetPrivateGalleryView, "private"),
        ):
            with self.subTest(view=view_class.__name__):
                request = self.factory.get("/filtered/")
                request.user = (
                    AnonymousUser()
                    if scope == "published"
                    else User(pk=1, is_staff=True)
                )

                with self.assertNumQueries(0):
                    response = view_class.as_view()(request)

                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, f"/filtered/?scope={scope}")

    def test_anonymous_private_and_review_requests_still_require_login(self):
        for view_class in (CollectionPrivateListView, CollectionReviewFilterView):
            with self.subTest(view=view_class.__name__):
                request = self.factory.get("/filtered/")
                request.user = AnonymousUser()

                with patch.object(view_class, "get_default_filters") as defaults:
                    response = view_class.as_view()(request)

                self.assertEqual(response.status_code, 302)
                self.assertEqual(
                    response.url, f"{reverse('auth_login')}?next=/filtered/"
                )
                defaults.assert_not_called()

    def test_non_moderator_review_request_is_denied_before_defaults(self):
        request = self.factory.get("/filtered/")
        request.user = User.objects.create_user(username="redirect-non-moderator")

        with patch.object(
            CollectionReviewFilterView, "get_default_filters"
        ) as defaults:
            with self.assertRaises(PermissionDenied):
                CollectionReviewFilterView.as_view()(request)

        defaults.assert_not_called()


class PublishedObjectsFilterViewTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        # Prepare a callable view that behaves like a URL-dispatched CBV
        self.view_callable = PublishedObjectFilterView.as_view(
            filterset_class=MockFilterSet,
            model=MockFilterSet.Meta.model,
        )

    def test_initial_filter_values_extraction(self):
        # Instantiate a view instance just to call get_default_filters()
        view = PublishedObjectFilterView()
        view.filterset_class = MockFilterSet
        expected_initial_values = {"name": "Initial name"}
        self.assertEqual(view.get_default_filters(), expected_initial_values)

    def test_get_with_empty_query_parameters(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()
        response = self.view_callable(request)

        self.assertEqual(response.status_code, 302)
        redirect_url = response.url
        self.assertEqual("/?name=Initial+name", redirect_url)

    def test_get_with_query_parameters(self):
        request = self.factory.get("/?name=Other+name")
        request.user = AnonymousUser()
        response = self.view_callable(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data["filter"].data, {"name": ["Other name"]})


class OwnerReviewFeedbackQueryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="feedback-owner")
        cls.moderator = User.objects.create_user(username="feedback-moderator")
        cls.staff = User.objects.create_user(username="feedback-staff", is_staff=True)
        cls.content_type = ContentType.objects.get_for_model(Property)
        permission, _ = Permission.objects.get_or_create(
            content_type=cls.content_type,
            codename="can_moderate_property",
            defaults={"name": "Can moderate property"},
        )
        cls.moderator.user_permissions.add(permission)
        cls.items = Property.objects.bulk_create(
            [
                Property(
                    name=f"Feedback {index:02d}",
                    owner=cls.owner,
                    publication_status="published",
                )
                for index in range(10)
            ]
        )
        ReviewAction.objects.bulk_create(
            [
                ReviewAction(
                    content_type=cls.content_type,
                    object_id=item.pk,
                    action=action,
                    user=user,
                )
                for item in cls.items
                for action, user in (
                    (ReviewAction.ACTION_SUBMITTED, cls.owner),
                    (ReviewAction.ACTION_COMMENT, cls.moderator),
                )
            ]
        )

    def setUp(self):
        ContentType.objects.get_for_model(Property)
        for user in (self.owner, self.moderator, self.staff):
            user.get_all_permissions()
            get_object_policy(user, self.items[0])

    def get_queryset(self, user, view_class=PublishedObjectFilterView):
        request = RequestFactory().get("/properties/", {"name": "Feedback"})
        request.user = user
        view = view_class(model=Property, filterset_class=MockFilterSet)
        view.setup(request)
        return view.get_queryset().filter(name__startswith="Feedback")

    def test_feedback_queries_do_not_grow_with_page_size_for_any_role(self):
        for user in (AnonymousUser(), self.owner, self.moderator, self.staff):
            for size in (1, 10):
                with self.subTest(user=user.pk, size=size):
                    queryset = self.get_queryset(user)[:size]
                    expected_queries = 2 if user.pk == self.owner.pk else 1
                    with self.assertNumQueries(expected_queries):
                        items = list(queryset)
                        populate_owner_review_feedback(items, user)
                        policies = [get_object_policy(user, item) for item in items]
                    self.assertEqual(
                        [policy["has_review_feedback"] for policy in policies],
                        [user.pk == self.owner.pk] * size,
                    )

    def test_distinct_list_batches_feedback_only_for_the_selected_page(self):
        request = RequestFactory().get("/properties/", {"name": "Feedback"})
        request.user = self.owner
        with (
            patch(
                "utils.object_management.models.annotate_owner_review_feedback",
                wraps=annotate_owner_review_feedback,
            ) as annotate,
            self.assertNumQueries(3),
        ):
            response = PublishedObjectFilterView.as_view(
                model=Property,
                queryset=Property.objects.all().distinct(),
                filterset_class=MockFilterSet,
                paginate_by=3,
            )(request)
            items = list(response.context_data["object_list"])
            self.assertTrue(all(item.has_review_feedback for item in items))

        self.assertEqual(len(items), 3)
        self.assertEqual(response.context_data["paginator"].count, 10)
        annotate.assert_called_once()
        feedback_queryset = annotate.call_args.args[0]
        self.assertFalse(feedback_queryset.query.distinct)
        self.assertSetEqual(
            set(feedback_queryset.values_list("pk", flat=True)),
            {item.pk for item in items},
        )

    def test_unpaginated_views_do_not_evaluate_their_object_list(self):
        request = RequestFactory().get("/properties/", {"name": "Feedback"})
        request.user = self.owner
        with self.assertNumQueries(0):
            response = PublishedObjectFilterView.as_view(
                model=Property, filterset_class=MockFilterSet, paginate_by=None
            )(request)
        self.assertEqual(response.status_code, 200)

    def test_gallery_context_does_not_fetch_unused_feedback(self):
        class GalleryView(PublishedObjectFilterView):
            representation_mode = "gallery"

        request = RequestFactory().get("/properties/", {"name": "Feedback"})
        request.user = self.owner
        with self.assertNumQueries(1):
            response = GalleryView.as_view(
                model=Property, filterset_class=MockFilterSet
            )(request)
        self.assertEqual(response.status_code, 200)

    def create_item(self):
        return Property.objects.create(
            name="Feedback cycle", owner=self.owner, publication_status="published"
        )

    def action(self, item, action, user, when=None, content_type=None):
        event = ReviewAction.objects.create(
            content_type=content_type or self.content_type,
            object_id=item.pk,
            action=action,
            user=user,
        )
        if when is not None:
            ReviewAction.objects.filter(pk=event.pk).update(created_at=when)
        return event

    def assert_feedback(self, item, expected, user=None):
        user = user or self.owner
        raw = Property.objects.get(pk=item.pk)
        self.assertEqual(raw.has_review_feedback, expected)
        optimized = self.get_queryset(user).get(pk=item.pk)
        populate_owner_review_feedback([optimized], user)
        with self.assertNumQueries(0):
            self.assertEqual(optimized.has_review_feedback, expected)

    def test_feedback_requires_a_submission_and_a_non_owner_action(self):
        item = self.create_item()
        self.action(item, ReviewAction.ACTION_COMMENT, self.moderator)
        self.assert_feedback(item, False)
        self.action(item, ReviewAction.ACTION_SUBMITTED, self.owner)
        self.action(item, ReviewAction.ACTION_COMMENT, self.owner)
        self.assert_feedback(item, False)
        self.action(item, ReviewAction.ACTION_COMMENT, self.moderator)
        self.assert_feedback(item, True)

    def test_new_submission_resets_feedback_and_equal_times_use_event_id(self):
        item = self.create_item()
        when = timezone.now()
        self.action(item, ReviewAction.ACTION_SUBMITTED, self.owner, when)
        self.action(item, ReviewAction.ACTION_REJECTED, self.moderator, when)
        self.assert_feedback(item, True)
        self.action(item, ReviewAction.ACTION_SUBMITTED, self.owner, when)
        self.assert_feedback(item, False)
        self.action(item, ReviewAction.ACTION_COMMENT, self.moderator, when)
        self.assert_feedback(item, True)

    def test_event_timestamp_takes_precedence_over_event_id(self):
        item = self.create_item()
        when = timezone.now()
        self.action(item, ReviewAction.ACTION_SUBMITTED, self.owner, when)
        self.action(
            item, ReviewAction.ACTION_COMMENT, self.moderator, when - timedelta(days=1)
        )
        self.assert_feedback(item, False)

    def test_feedback_does_not_cross_content_types(self):
        item = self.create_item()
        self.action(item, ReviewAction.ACTION_SUBMITTED, self.owner)
        self.action(
            item,
            ReviewAction.ACTION_COMMENT,
            self.moderator,
            content_type=ContentType.objects.get_for_model(Author),
        )
        self.assert_feedback(item, False)

    def test_later_owner_comment_does_not_hide_moderator_feedback(self):
        item = self.create_item()
        self.action(item, ReviewAction.ACTION_SUBMITTED, self.owner)
        self.action(item, ReviewAction.ACTION_COMMENT, self.moderator)
        self.action(item, ReviewAction.ACTION_COMMENT, self.owner)
        self.assert_feedback(item, True)

    def test_feedback_uses_the_current_owner(self):
        item = self.items[0]
        Property.objects.filter(pk=item.pk).update(owner=self.moderator)
        self.assert_feedback(item, False, user=self.moderator)

    def test_editor_visibility_does_not_grant_owner_feedback_capabilities(self):
        item = self.items[0]
        Property.objects.filter(pk=item.pk).update(publication_status="private")
        ObjectEditorGrant.objects.create(
            content_object=item, editor=self.moderator, granted_by=self.owner
        )
        self.moderator.__dict__.pop("_editor_grant_cache", None)
        shared = self.get_queryset(self.moderator, PrivateObjectFilterView).get(
            pk=item.pk
        )
        policy = get_object_policy(self.moderator, shared)
        self.assertTrue(policy["is_editor"])
        self.assertFalse(policy["is_owner"])
        self.assertFalse(policy["has_review_feedback"])
        self.assertFalse(policy["can_view_review_feedback"])
        self.assertTrue(shared.has_review_feedback)


class SharedListScopeCountTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            username="scope-count-staff", is_staff=True
        )
        cls.other = User.objects.create_user(username="scope-count-other")
        Property.objects.bulk_create(
            [
                Property(name=name, owner=owner, publication_status=status)
                for name, owner, status in (
                    ("Selected public 1", cls.staff, "published"),
                    ("Selected public 2", cls.other, "published"),
                    ("Excluded public", cls.other, "published"),
                    ("Selected mine", cls.staff, "private"),
                    ("Selected review", cls.other, "review"),
                    ("Selected hidden", cls.other, "private"),
                )
            ]
        )

    def get_response(self, view_class, user):
        request = RequestFactory().get("/properties/", {"name": "Selected"})
        request.user = user
        return view_class.as_view(model=Property, filterset_class=MockFilterSet)(
            request
        )

    def test_lists_only_count_the_filtered_paginator_results(self):
        ContentType.objects.get_for_model(Property)
        for view_class, user, expected, query_budget in (
            (PublishedObjectFilterView, AnonymousUser(), 2, 1),
            (PublishedObjectFilterView, self.staff, 2, 3),
            (PrivateObjectFilterView, self.staff, 2, 3),
            (ReviewObjectFilterView, self.staff, 1, 2),
        ):
            with self.subTest(
                view=view_class.__name__, authenticated=user.is_authenticated
            ):
                with CaptureQueriesContext(connection) as queries:
                    response = self.get_response(view_class, user)
                    self.assertEqual(response.context_data["paginator"].count, expected)

                self.assertEqual(len(queries), query_budget)
                self.assertEqual(
                    sum("COUNT(" in query["sql"].upper() for query in queries), 1
                )
                self.assertEqual(response.status_code, 200)
                for key in ("public_count", "private_count", "review_count"):
                    self.assertNotIn(key, response.context_data)

    def test_result_total_and_active_scope_buttons_still_render(self):
        response = self.get_response(PublishedObjectFilterView, self.staff)
        response.render()

        self.assertContains(response, "of 2 results")
        self.assertContains(response, 'aria-label="Scope toggle"')
        self.assertContains(response, "scope=private")
        self.assertContains(response, "scope=review")


class BreadcrumbContractViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="breadcrumb-owner")
        cls.creator = User.objects.create_user(username="breadcrumb-creator")
        cls.creator.user_permissions.add(
            Permission.objects.get(
                content_type=ContentType.objects.get_for_model(Property),
                codename="add_property",
            )
        )
        cls.author = Author.objects.create(
            first_names="Ada",
            last_names="Lovelace",
            owner=cls.owner,
            publication_status=UserCreatedObject.STATUS_PUBLISHED,
        )

    def setUp(self):
        self.factory = RequestFactory()

    def test_author_list_uses_module_and_section_breadcrumbs(self):
        response = self.client.get(reverse("author-list"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<a href="{reverse("bibliography-explorer")}">Bibliography</a>',
            html=True,
        )
        self.assertContains(
            response,
            '<li aria-current="page" class="breadcrumb-item active">Authors</li>',
            html=True,
        )
        self.assertNotContains(
            response,
            f'<a href="{reverse("bibliography-explorer")}">Explorer</a>',
            html=True,
        )

    def test_author_detail_uses_string_label_in_breadcrumbs(self):
        response = self.client.get(self.author.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<a href="{reverse("bibliography-explorer")}">Bibliography</a>',
            html=True,
        )
        self.assertContains(
            response,
            f'<a href="{reverse("author-list")}">Authors</a>',
            html=True,
        )
        self.assertContains(
            response,
            f'<li aria-current="page" class="breadcrumb-item active">{self.author.get_breadcrumb_object_label()}</li>',
            html=True,
        )
        self.assertContains(
            response,
            f"<title>\n  BRIT | {self.author.get_breadcrumb_object_label()}\n</title>",
            html=True,
        )

    def test_shared_create_form_renders_module_section_and_action_breadcrumbs(self):
        request = self.factory.get(reverse("property-create"))
        request.user = self.creator

        response = TestPropertyCreateView.as_view()(request)
        response.render()

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<a href="{reverse("properties-dashboard")}">Properties</a>',
            html=True,
        )
        self.assertContains(
            response,
            f'<a href="{reverse("property-list")}">Properties</a>',
            html=True,
        )
        self.assertContains(
            response,
            '<li aria-current="page" class="breadcrumb-item active">Create</li>',
            html=True,
        )
        self.assertContains(
            response,
            "<title>\n  BRIT | Create Property\n</title>",
            html=True,
        )


class ReadAccessArchivedDetailTests(TestCase):
    """Ensure archived objects' detail views are NOT publicly accessible."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner")
        # Create a Collection in archived state
        with mute_signals(post_save, pre_save):
            cls.archived = Collection.objects.create(
                name="Archived Collection",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_ARCHIVED,
            )

    def test_archived_detail_is_not_public(self):
        url = reverse("collection-detail", kwargs={"pk": self.archived.id})
        # Unauthenticated request should be redirected to login (302)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)


class DetailViewObjectCachingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="detail-cache-owner")
        with mute_signals(post_save, pre_save):
            cls.collection = Collection.objects.create(
                name="Cache Target Collection",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )

    def test_get_object_returns_cached_instance_on_second_call(self):
        request = RequestFactory().get(
            reverse("collection-detail", kwargs={"pk": self.collection.pk})
        )
        request.user = self.owner
        view = CollectionDetailView()
        view.setup(request, pk=self.collection.pk)

        first = view.get_object()

        with self.assertNumQueries(0):
            second = view.get_object()

        self.assertEqual(first.pk, second.pk)


class ReviewWorkflowModalViewTests(TestCase):
    """Tests for modal review action views (submit, withdraw, approve, reject)."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner")
        cls.moderator = User.objects.create_user(username="moderator")
        cls.regular_user = User.objects.create_user(username="regular")

        content_type = ContentType.objects.get_for_model(Collection)
        permission, _ = Permission.objects.get_or_create(
            codename="can_moderate_collection",
            content_type=content_type,
            defaults={"name": "Can moderate collections"},
        )
        cls.moderator.user_permissions.add(permission)

        with mute_signals(post_save, pre_save):
            cls.private_collection = Collection.objects.create(
                name="Private Collection",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )
        with mute_signals(post_save, pre_save):
            cls.review_collection = Collection.objects.create(
                name="Review Collection",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )

        cls.review_source = Source.objects.create(
            owner=cls.owner,
            title="Review Workflow Modal Source",
        )
        cls.private_collection.sources.add(cls.review_source)
        cls.review_collection.sources.add(cls.review_source)

        cls.ct_id = ContentType.objects.get_for_model(Collection).id

    def test_submit_for_review_modal_get_and_post(self):
        url = reverse(
            "object_management:submit_for_review_modal",
            kwargs={
                "content_type_id": self.ct_id,
                "object_id": self.private_collection.id,
            },
        )

        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        self.private_collection.refresh_from_db()
        self.assertEqual(
            self.private_collection.publication_status,
            UserCreatedObject.STATUS_REVIEW,
        )

        with mute_signals(post_save, pre_save):
            self.private_collection.publication_status = (
                UserCreatedObject.STATUS_PRIVATE
            )
            self.private_collection.save()
        self.client.force_login(self.regular_user)
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_withdraw_from_review_modal_get_and_post(self):
        url = reverse(
            "object_management:withdraw_from_review_modal",
            kwargs={
                "content_type_id": self.ct_id,
                "object_id": self.review_collection.id,
            },
        )

        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        self.review_collection.refresh_from_db()
        self.assertEqual(
            self.review_collection.publication_status,
            UserCreatedObject.STATUS_PRIVATE,
        )

        with mute_signals(post_save, pre_save):
            self.review_collection.publication_status = UserCreatedObject.STATUS_REVIEW
            self.review_collection.save()
        self.client.force_login(self.regular_user)
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_approve_item_modal_get_and_post(self):
        url = reverse(
            "object_management:approve_item_modal",
            kwargs={
                "content_type_id": self.ct_id,
                "object_id": self.review_collection.id,
            },
        )

        self.client.force_login(self.moderator)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        self.review_collection.refresh_from_db()
        self.assertEqual(
            self.review_collection.publication_status,
            UserCreatedObject.STATUS_PUBLISHED,
        )
        self.assertEqual(self.review_collection.approved_by, self.moderator)

        with mute_signals(post_save, pre_save):
            self.review_collection.publication_status = UserCreatedObject.STATUS_REVIEW
            self.review_collection.approved_by = None
            self.review_collection.approved_at = None
            self.review_collection.save()
        self.client.force_login(self.regular_user)
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_reject_item_modal_get_and_post(self):
        url = reverse(
            "object_management:reject_item_modal",
            kwargs={
                "content_type_id": self.ct_id,
                "object_id": self.review_collection.id,
            },
        )

        self.client.force_login(self.moderator)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        self.review_collection.refresh_from_db()
        self.assertEqual(
            self.review_collection.publication_status,
            UserCreatedObject.STATUS_DECLINED,
        )

        with mute_signals(post_save, pre_save):
            self.review_collection.publication_status = UserCreatedObject.STATUS_REVIEW
            self.review_collection.save()
        self.client.force_login(self.regular_user)
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)


class CollectionPropertyValueReviewDashboardTest(TestCase):
    """CollectionPropertyValue rows should be visible and filterable in dashboard."""

    @classmethod
    def setUpTestData(cls):
        cls.staff_user = User.objects.create_user(
            username="staff", password="test123", is_staff=True
        )
        cls.owner_user = User.objects.create_user(username="owner", password="test123")

        cls.unit = Unit.objects.create(name="kg")
        cls.property = Property.objects.create(name="Test Property", unit="kg")

        with mute_signals(post_save, pre_save):
            cls.collection = Collection.objects.create(
                name="Test Collection",
                owner=cls.owner_user,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )

            cls.cpv = CollectionPropertyValue.objects.create(
                name="Test CPV",
                property=cls.property,
                unit=cls.unit,
                collection=cls.collection,
                average=100.0,
                owner=cls.owner_user,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )

    def test_cpv_appears_in_unfiltered_dashboard(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("object_management:review_dashboard"))
        self.assertEqual(response.status_code, 200)

        review_items = list(response.context["review_items"])
        item_types = [type(item).__name__ for item in review_items]
        self.assertIn("Collection", item_types)
        self.assertIn("CollectionPropertyValue", item_types)

        cpvs = [
            item for item in review_items if isinstance(item, CollectionPropertyValue)
        ]
        self.assertEqual(len(cpvs), 1)
        self.assertEqual(cpvs[0].id, self.cpv.id)

    def test_filtering_by_cpv_model_type(self):
        self.client.force_login(self.staff_user)
        cpv_ct = ContentType.objects.get_for_model(CollectionPropertyValue)
        response = self.client.get(
            reverse("object_management:review_dashboard"), {"model_type": cpv_ct.id}
        )
        self.assertEqual(response.status_code, 200)

        review_items = list(response.context["review_items"])
        for item in review_items:
            self.assertIsInstance(item, CollectionPropertyValue)

        self.assertEqual(len(review_items), 1)
        self.assertEqual(review_items[0].id, self.cpv.id)

    def test_cpv_model_appears_in_filter_options(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("object_management:review_dashboard"))
        self.assertEqual(response.status_code, 200)

        filter_obj = response.context["filter"]
        model_type_choices = filter_obj.filters["model_type"].queryset
        cpv_ct = ContentType.objects.get_for_model(CollectionPropertyValue)
        self.assertIn(cpv_ct, model_type_choices)

    def test_declined_only_cpv_model_is_hidden_from_filter_options(self):
        with mute_signals(post_save, pre_save):
            self.cpv.publication_status = UserCreatedObject.STATUS_DECLINED
            self.cpv.save()

        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("object_management:review_dashboard"))
        self.assertEqual(response.status_code, 200)

        filter_obj = response.context["filter"]
        model_type_choices = filter_obj.filters["model_type"].queryset
        cpv_ct = ContentType.objects.get_for_model(CollectionPropertyValue)
        collection_ct = ContentType.objects.get_for_model(Collection)
        self.assertNotIn(cpv_ct, model_type_choices)
        self.assertIn(collection_ct, model_type_choices)


class ReviewDashboardPaginationQueryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(username="queue-staff", is_staff=True)
        cls.owner = User.objects.create_user(username="queue-owner")
        cls.now = (timezone.now() - timedelta(days=1)).replace(
            hour=12, minute=0, second=0, microsecond=0
        )
        cls.properties = Property.objects.bulk_create(
            [
                Property(
                    name=f"Queue {index:03d}",
                    description="Long review description " * 100,
                    owner=cls.owner,
                    publication_status="review",
                    submitted_at=cls.now - timedelta(minutes=index),
                )
                for index in range(90)
            ]
        )
        cls.collections = Collection.objects.bulk_create(
            [
                Collection(
                    name=f"queue {index:03d}",
                    owner=cls.owner,
                    publication_status="review",
                    submitted_at=cls.now - timedelta(minutes=index, seconds=30),
                )
                for index in range(10)
            ]
        )
        Property.objects.bulk_create(
            [
                Property(
                    name="Excluded",
                    owner=owner,
                    publication_status=status,
                    submitted_at=cls.now,
                )
                for owner, status in (
                    (cls.staff, "review"),
                    (cls.owner, "published"),
                    (cls.owner, "private"),
                )
            ]
        )

    def get_view(self, params=None):
        request = RequestFactory().get("/review/", params or {})
        request.user = self.staff
        view = ReviewDashboardView(paginate_by=5)
        view.setup(request)
        return view

    def response(self, params=None, models=None):
        view = self.get_view(params)
        with patch.object(
            view, "get_available_models", return_value=models or [Property, Collection]
        ):
            return view.get(view.request)

    def identities(self, items):
        return [(type(item), item.pk) for item in items]

    def expected(self, ordering):
        field = ordering.lstrip("-")
        return sorted(
            [*self.properties, *self.collections],
            key=lambda item: (
                item.name.lower() if field == "name" else item.submitted_at
            ),
            reverse=ordering.startswith("-"),
        )

    def test_unfiltered_total_and_last_page_are_not_truncated(self):
        response = self.response({"page": 20})
        self.assertEqual(response.context_data["paginator"].count, 100)
        self.assertEqual(response.context_data["page_obj"].number, 20)
        self.assertEqual(
            self.identities(response.context_data["review_items"]),
            self.identities(self.expected("-submitted_at")[-5:]),
        )

    def test_filtered_dashboard_only_instantiates_the_selected_page(self):
        with (
            patch.object(
                Property, "from_db", wraps=Property.from_db
            ) as properties_loaded,
            patch.object(
                Collection, "from_db", wraps=Collection.from_db
            ) as collections_loaded,
        ):
            response = self.response({"search": "Queue", "page": 2})
        self.assertEqual(response.context_data["paginator"].count, 100)
        self.assertEqual(len(response.context_data["review_items"]), 5)
        self.assertEqual(
            properties_loaded.call_count + collections_loaded.call_count, 5
        )

    def test_all_sort_directions_and_later_pages_match_python_ordering(self):
        for ordering in ("-submitted_at", "submitted_at", "name", "-name"):
            expected = self.expected(ordering)
            for number in (1, 2, 20):
                with self.subTest(ordering=ordering, page=number):
                    response = self.response(
                        {"search": "Queue", "ordering": ordering, "page": number}
                    )
                    start = (number - 1) * 5
                    self.assertEqual(
                        self.identities(response.context_data["review_items"]),
                        self.identities(expected[start : start + 5]),
                    )

    def test_name_sort_reaches_records_outside_the_old_date_window(self):
        target = Property.objects.create(
            name="Zulu oldest",
            owner=self.owner,
            publication_status="review",
            submitted_at=self.now - timedelta(days=365),
        )
        response = self.response({"ordering": "-name"})
        self.assertEqual(response.context_data["review_items"][0].pk, target.pk)
        self.assertEqual(response.context_data["paginator"].count, 101)

    def test_model_owner_and_date_filters_are_applied_before_pagination(self):
        Property.objects.create(
            name="Queue old",
            owner=self.owner,
            publication_status="review",
            submitted_at=self.now - timedelta(days=2),
        )
        response = self.response(
            {
                "model_type": ContentType.objects.get_for_model(Property).pk,
                "owner": self.owner.pk,
                "submitted_after": self.now.date().isoformat(),
                "submitted_before": self.now.date().isoformat(),
                "ordering": "name",
                "page": 2,
            }
        )
        expected = [
            item
            for item in self.properties
            if item.submitted_at.date() == self.now.date()
        ]
        self.assertEqual(response.context_data["paginator"].count, len(expected))
        self.assertEqual(
            self.identities(response.context_data["review_items"]),
            self.identities(expected[5:10]),
        )

    def test_null_submission_and_models_without_name_keep_existing_sort_semantics(self):
        source = Source.objects.create(
            title="Nameless model", owner=self.owner, publication_status="review"
        )
        for ordering in ("-submitted_at", "name"):
            with self.subTest(ordering=ordering):
                response = self.response(
                    {"ordering": ordering}, models=[Property, Source]
                )
                self.assertEqual(
                    self.identities(response.context_data["review_items"])[0],
                    (Source, source.pk),
                )
                self.assertEqual(response.context_data["paginator"].count, 91)

    def test_unicode_name_ordering_matches_python_on_later_pages(self):
        additional = Property.objects.bulk_create(
            [
                Property(
                    name=name,
                    owner=self.owner,
                    publication_status="review",
                    submitted_at=self.now,
                )
                for name in ("ÄPFEL", "äpfel", "Éclair", "eclair", "Ωmega", "東京")
            ]
        )
        expected = sorted(
            [*self.properties, *self.collections, *additional],
            key=lambda item: item.name.lower(),
        )
        for number in (1, 21, 22):
            with self.subTest(page=number):
                response = self.response({"ordering": "name", "page": number})
                start = (number - 1) * 5
                self.assertEqual(
                    self.identities(response.context_data["review_items"]),
                    self.identities(expected[start : start + 5]),
                )

    def test_page_loading_rechecks_review_status_after_reference_selection(self):
        view = self.get_view()
        hydrate = view._hydrate_review_references

        def approve_before_loading(references, querysets):
            Property.objects.filter(pk=self.properties[0].pk).update(
                publication_status="published"
            )
            return hydrate(references, querysets)

        with (
            patch.object(
                view, "get_available_models", return_value=[Property, Collection]
            ),
            patch.object(
                view, "_hydrate_review_references", side_effect=approve_before_loading
            ),
        ):
            response = view.get(view.request)

        self.assertNotIn(
            (Property, self.properties[0].pk),
            self.identities(response.context_data["review_items"]),
        )
        self.assertEqual(len(response.context_data["review_items"]), 4)

    def test_unpaginated_collector_keeps_json_queue_limits_and_filtered_results(self):
        for params, expected_count in (({}, 60), ({"search": "Queue"}, 100)):
            with self.subTest(params=params):
                view = self.get_view(params)
                with patch.object(
                    view, "get_available_models", return_value=[Property, Collection]
                ):
                    items = view.collect_review_items()
                self.assertIsInstance(items, list)
                self.assertEqual(len(items), expected_count)


class ReviewDashboardViewTests(TestCase):
    """Review dashboard view behaviour for access, filtering and model coverage."""

    @classmethod
    def setUpTestData(cls):
        cls.owner_user = User.objects.create_user(username="owner", password="test123")
        cls.moderator_user = User.objects.create_user(
            username="moderator", password="test123"
        )
        cls.collection_moderator = User.objects.create_user(
            username="collection_moderator", password="test123"
        )
        cls.regular_user = User.objects.create_user(
            username="regular", password="test123"
        )
        cls.staff_user = User.objects.create_user(
            username="staff", password="test123", is_staff=True
        )

        collection_ct = ContentType.objects.get_for_model(Collection)
        collection_perm, _ = Permission.objects.get_or_create(
            codename="can_moderate_collection",
            content_type=collection_ct,
            defaults={"name": "Can moderate collections"},
        )
        cls.moderator_user.user_permissions.add(collection_perm)
        cls.collection_moderator.user_permissions.add(collection_perm)

        with mute_signals(post_save, pre_save):
            cls.private_collection = Collection.objects.create(
                name="Private Collection",
                owner=cls.owner_user,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )
            cls.review_collection_1 = Collection.objects.create(
                name="Review Collection Alpha",
                owner=cls.owner_user,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )
            cls.review_collection_2 = Collection.objects.create(
                name="Review Collection Beta",
                owner=cls.owner_user,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )
            cls.moderator_collection = Collection.objects.create(
                name="Moderator Review Collection",
                owner=cls.moderator_user,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )
            cls.published_collection = Collection.objects.create(
                name="Published Collection",
                owner=cls.owner_user,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )

    def test_anonymous_user_cannot_access_dashboard(self):
        response = self.client.get(reverse("object_management:review_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/users/login/", response.url)

    def test_regular_user_cannot_access_dashboard(self):
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("object_management:review_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("review_items", response.context)
        review_items = list(response.context["review_items"])
        self.assertEqual(len(review_items), 0)

    def test_moderator_can_access_dashboard(self):
        self.client.force_login(self.moderator_user)
        response = self.client.get(reverse("object_management:review_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("review_items", response.context)

        review_items = list(response.context["review_items"])
        self.assertGreater(len(review_items), 0)

        item_names = [item.name for item in review_items]
        self.assertNotIn("Moderator Review Collection", item_names)
        self.assertIn("Review Collection Alpha", item_names)

    def test_dashboard_uses_review_module_breadcrumb(self):
        self.client.force_login(self.moderator_user)
        response = self.client.get(reverse("object_management:review_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BRIT | Content Review")
        self.assertContains(
            response,
            '<li aria-current="page" class="breadcrumb-item active">Review</li>',
            html=True,
        )

    def test_dashboard_search_filter(self):
        self.client.force_login(self.moderator_user)
        response = self.client.get(
            reverse("object_management:review_dashboard"), {"search": "Alpha"}
        )
        self.assertEqual(response.status_code, 200)

        review_items = list(response.context["review_items"])
        item_names = [item.name for item in review_items]
        self.assertIn("Review Collection Alpha", item_names)
        self.assertNotIn("Review Collection Beta", item_names)

    def test_collect_review_items_searches_collections_beyond_prefetch_window(self):
        region = Region.objects.create(
            name="Search Region",
            country="DE",
            owner=self.owner_user,
        )
        catchment = Catchment.objects.create(
            name="Ostalbkreis (DE11D)",
            owner=self.owner_user,
            region=region,
        )
        submitted_at = timezone.now() - timedelta(days=30)

        with mute_signals(post_save, pre_save):
            target = Collection.objects.create(
                name="Legacy Green Waste 2024",
                owner=self.owner_user,
                catchment=catchment,
                publication_status=UserCreatedObject.STATUS_REVIEW,
                submitted_at=submitted_at,
            )
            for index in range(11):
                Collection.objects.create(
                    name=f"Newer Review Collection {index}",
                    owner=self.owner_user,
                    publication_status=UserCreatedObject.STATUS_REVIEW,
                    submitted_at=submitted_at + timedelta(minutes=index + 1),
                )

        request = RequestFactory().get(
            reverse("object_management:review_dashboard"),
            {"search": "Ostalbkreis"},
        )
        request.user = self.staff_user

        view = ReviewDashboardView()
        view.setup(request)
        view.request = request

        with (
            patch.object(view, "get_available_models", return_value=[Collection]),
            patch.object(view, "paginate_by", 1),
        ):
            review_items = view.collect_review_items()

        self.assertEqual([item.id for item in review_items], [target.id])

    def test_dashboard_model_type_filter(self):
        self.client.force_login(self.moderator_user)
        collection_ct = ContentType.objects.get_for_model(Collection)
        response = self.client.get(
            reverse("object_management:review_dashboard"),
            {"model_type": [collection_ct.id]},
        )
        self.assertEqual(response.status_code, 200)

        review_items = list(response.context["review_items"])
        for item in review_items:
            self.assertIsInstance(item, Collection)

    def test_dashboard_ignores_invalid_filter_values(self):
        self.client.force_login(self.moderator_user)
        baseline_response = self.client.get(
            reverse("object_management:review_dashboard")
        )
        baseline_ids = {
            (item._meta.label_lower, item.pk)
            for item in baseline_response.context["review_items"]
        }

        with self.assertLogs("utils.object_management", level="WARNING") as cm:
            response = self.client.get(
                reverse("object_management:review_dashboard"),
                {
                    "model_type": ["not-a-content-type"],
                    "owner": "not-a-user",
                    "submitted_after": "not-a-date",
                    "submitted_before": "2026-99-99",
                    "ordering": "not-a-sort-field",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(cm.records), 4)
        self.assertSetEqual(
            {
                (item._meta.label_lower, item.pk)
                for item in response.context["review_items"]
            },
            baseline_ids,
        )

    def test_dashboard_pagination_clamps_invalid_and_out_of_range_pages(self):
        self.client.force_login(self.moderator_user)
        dashboard_url = reverse("object_management:review_dashboard")

        with patch.object(ReviewDashboardView, "paginate_by", 1):
            first_page = self.client.get(dashboard_url, {"page": "invalid"})
            second_page = self.client.get(dashboard_url, {"page": 2})
            out_of_range_page = self.client.get(dashboard_url, {"page": 999})

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(first_page.context["page_obj"].number, 1)
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(second_page.context["page_obj"].number, 2)
        self.assertEqual(out_of_range_page.status_code, 200)
        self.assertEqual(
            out_of_range_page.context["page_obj"].number,
            out_of_range_page.context["paginator"].num_pages,
        )

    def test_model_type_filter_hides_models_with_only_own_review_items(self):
        owner = User.objects.create_user(
            username="collector_owner_only", password="test123"
        )
        collector_ct = ContentType.objects.get_for_model(Collector)
        collector_permission, _ = Permission.objects.get_or_create(
            codename="can_moderate_collector",
            content_type=collector_ct,
            defaults={"name": "Can moderate collectors"},
        )
        self.collection_moderator.user_permissions.add(collector_permission)

        with mute_signals(post_save, pre_save):
            Collector.objects.create(
                name="Own Review Collector",
                owner=self.collection_moderator,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )
            Collection.objects.create(
                name="Visible Review Collection",
                owner=owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )

        self.client.force_login(self.collection_moderator)
        response = self.client.get(reverse("object_management:review_dashboard"))
        self.assertEqual(response.status_code, 200)

        filter_obj = response.context["filter"]
        model_type_choices = filter_obj.filters["model_type"].queryset
        collection_ct = ContentType.objects.get_for_model(Collection)
        self.assertIn(collection_ct, model_type_choices)
        self.assertNotIn(collector_ct, model_type_choices)

    def test_dashboard_uses_correct_template(self):
        self.client.force_login(self.moderator_user)
        response = self.client.get(reverse("object_management:review_dashboard"))
        self.assertEqual(response.status_code, 200)

        template_names = [t.name for t in response.templates]
        self.assertIn("object_management/review_dashboard.html", template_names)
        self.assertIn("filtered_list.html", template_names)

    def test_dashboard_includes_temporal_distribution_with_plain_manager(self):
        owner = User.objects.create_user(
            username="distribution_owner", password="test123"
        )
        TemporalDistribution.objects.create(
            name="Review Distribution",
            owner=owner,
            publication_status=UserCreatedObject.STATUS_REVIEW,
        )

        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("object_management:review_dashboard"))

        self.assertEqual(response.status_code, 200)
        review_items = list(response.context["review_items"])
        self.assertTrue(
            any(isinstance(item, TemporalDistribution) for item in review_items)
        )

    def test_dashboard_includes_catchment_with_custom_manager(self):
        owner = User.objects.create_user(username="catchment_owner", password="test123")
        region = Region.objects.create(name="Review Region", country="DE", owner=owner)
        Catchment.objects.create(
            name="Review Catchment",
            owner=owner,
            region=region,
            publication_status=UserCreatedObject.STATUS_REVIEW,
        )

        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("object_management:review_dashboard"))

        self.assertEqual(response.status_code, 200)
        review_items = list(response.context["review_items"])
        self.assertTrue(any(isinstance(item, Catchment) for item in review_items))

    def test_dashboard_includes_collector_from_nested_sources_app(self):
        owner = User.objects.create_user(username="collector_owner", password="test123")
        Collector.objects.create(
            name="Review Collector",
            owner=owner,
            publication_status=UserCreatedObject.STATUS_REVIEW,
        )

        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("object_management:review_dashboard"))

        self.assertEqual(response.status_code, 200)
        review_items = list(response.context["review_items"])
        self.assertTrue(any(isinstance(item, Collector) for item in review_items))

    def test_get_available_models_accepts_models_module_subpackages(self):
        request = RequestFactory().get(reverse("object_management:review_dashboard"))
        request.user = self.moderator_user

        view = ReviewDashboardView()
        view.setup(request)

        submodule_path = f"{Collection._meta.app_config.name}.models.submodule"
        with (
            patch("django.apps.apps.get_models", return_value=[Collection]),
            patch.object(Collection, "__module__", submodule_path),
        ):
            available_models = view.get_available_models()

        self.assertIn(Collection, available_models)

    def test_collect_review_items_ignores_models_with_unresolvable_review_queryset(
        self,
    ):
        request = RequestFactory().get(reverse("object_management:review_dashboard"))
        request.user = self.staff_user

        view = ReviewDashboardView()
        view.setup(request)

        with (
            patch.object(view, "get_available_models", return_value=[Collection]),
            patch.object(
                view,
                "_in_review_queryset_for_model",
                side_effect=RuntimeError("boom"),
            ),
            self.assertLogs("utils.object_management.views", level="WARNING"),
        ):
            review_items = view.collect_review_items()

        self.assertEqual(review_items, [])

    def test_get_filterset_kwargs_uses_sources_collection_fallback_queryset(self):
        request = RequestFactory().get(reverse("object_management:review_dashboard"))
        request.user = self.staff_user

        view = ReviewDashboardView()
        view.setup(request)

        fallback_queryset = Collection.objects.none()
        with (
            patch.object(view, "get_available_models", return_value=[]),
            patch.object(
                view, "_get_fallback_queryset", return_value=fallback_queryset
            ),
        ):
            kwargs = view.get_filterset_kwargs(view.filterset_class)

        self.assertIs(kwargs["queryset"], fallback_queryset)

    def test_get_queryset_uses_sources_collection_fallback_queryset(self):
        request = RequestFactory().get(reverse("object_management:review_dashboard"))
        request.user = self.staff_user

        view = ReviewDashboardView()
        view.setup(request)

        fallback_queryset = Collection.objects.none()
        with (
            patch.object(view, "get_available_models", return_value=[]),
            patch.object(
                view, "_get_fallback_queryset", return_value=fallback_queryset
            ),
        ):
            queryset = view.get_queryset()

        self.assertIs(queryset, fallback_queryset)


class ReviewDashboardFilterTests(TestCase):
    """Review dashboard filter form behaviour."""

    @classmethod
    def setUpTestData(cls):
        cls.moderator = User.objects.create_user(
            username="moderator", password="test123", is_staff=True
        )
        cls.owner = User.objects.create_user(username="owner", password="test123")

        with mute_signals(post_save, pre_save):
            cls.collection_a = Collection.objects.create(
                name="Collection A",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )
            cls.collection_b = Collection.objects.create(
                name="Collection B",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )

    def test_filter_form_renders(self):
        self.client.force_login(self.moderator)
        response = self.client.get(reverse("object_management:review_dashboard"))
        self.assertEqual(response.status_code, 200)

        self.assertIn("filter", response.context)
        filter_obj = response.context["filter"]
        self.assertIn("search", filter_obj.filters)
        self.assertIn("model_type", filter_obj.filters)
        self.assertIn("owner", filter_obj.filters)
        self.assertIn("ordering", filter_obj.filters)

    def test_filter_preserves_query_parameters(self):
        self.client.force_login(self.moderator)
        response = self.client.get(
            reverse("object_management:review_dashboard"), {"search": "Collection"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("filter", response.context)

        filter_obj = response.context["filter"]
        self.assertEqual(filter_obj.data.get("search"), "Collection")
