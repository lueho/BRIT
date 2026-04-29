from datetime import timedelta
from unittest.mock import patch
from urllib.parse import urlencode

from django.contrib.auth.models import AnonymousUser, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save, pre_save
from django.http import HttpResponseRedirect
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from django_filters import CharFilter, FilterSet
from django_filters.views import FilterView
from factory.django import mute_signals

from bibliography.models import Author, Source
from distributions.models import TemporalDistribution
from maps.models import Catchment, Region
from sources.waste_collection.models import (
    Collection,
    CollectionPropertyValue,
    Collector,
)
from sources.waste_collection.views import CollectionDetailView
from utils.object_management.models import ReviewAction, UserCreatedObject
from utils.object_management.views import (
    ReviewDashboardView,
    UserCreatedObjectCreateView,
)
from utils.properties.models import Property, Unit

from ..views import FilterDefaultsMixin, PublishedObjectFilterView


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
