from urllib.parse import urlencode

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save, pre_save
from django.http import HttpResponseRedirect
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django_filters import CharFilter, FilterSet
from django_filters.views import FilterView
from factory.django import mute_signals

from case_studies.soilcom.models import Collection
from utils.object_management.models import UserCreatedObject
from utils.properties.models import Property

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
        permission = Permission.objects.create(
            codename="can_moderate_collection",
            name="Can moderate collections",
            content_type=content_type,
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
            self.review_collection.publication_status, UserCreatedObject.STATUS_PRIVATE
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

        # Dashboard should contain objects in review
        # expected_name = self.review_collection.construct_name()
        # if expected_name not in response.content.decode():
        #     print("DASHBOARD HTML FOR DEBUGGING:")
        #     print(response.content.decode())
        self.assertContains(response, self.review_collection.name)

        # Regular user should be able to access the dashboard but see no items
        self.client.force_login(self.regular_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Review Collection")


class MockFilterSet(FilterSet):
    name = CharFilter(
        field_name="name", lookup_expr="icontains", initial="Initial name"
    )

    class Meta:
        model = Property
        fields = ["name"]


class MockFilterView(FilterDefaultsMixin, FilterView):
    filterset_class = MockFilterSet


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
        self.view = PublishedObjectFilterView()
        self.view.filterset_class = MockFilterSet
        self.view.model = self.view.filterset_class.Meta.model

    def test_initial_filter_values_extraction(self):
        expected_initial_values = {"name": "Initial name"}
        self.assertEqual(self.view.get_default_filters(), expected_initial_values)

    def test_get_with_empty_query_parameters(self):
        request = self.factory.get("/")
        self.view.request = request
        self.view.kwargs = {}
        response = self.view.get(request)

        self.assertEqual(response.status_code, 302)
        redirect_url = response.url
        self.assertEqual("/?name=Initial+name", redirect_url)

    def test_get_with_query_parameters(self):
        request = self.factory.get("/?name=Other+name")
        self.view.request = request
        self.view.kwargs = {}
        response = self.view.get(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data["filter"].data, {"name": ["Other name"]})
