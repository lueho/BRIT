from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save, pre_save
from django.test import RequestFactory, TestCase
from django.urls import reverse
from factory.django import mute_signals

from case_studies.soilcom.models import Collection
from distributions.models import TemporalDistribution
from maps.models import Catchment, Region
from utils.object_management.models import UserCreatedObject
from utils.object_management.views import ReviewDashboardView


class ReviewDashboardViewTests(TestCase):
    """Test the review dashboard view with filtering and multi-model support."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data: users with different permission levels and test objects."""
        # Create users
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

        # Add collection moderation permissions
        collection_ct = ContentType.objects.get_for_model(Collection)
        collection_perm, _ = Permission.objects.get_or_create(
            codename="can_moderate_collection",
            content_type=collection_ct,
            defaults={"name": "Can moderate collections"},
        )
        cls.moderator_user.user_permissions.add(collection_perm)
        cls.collection_moderator.user_permissions.add(collection_perm)

        # Create test collections in different states
        with mute_signals(post_save, pre_save):
            # Owner's private collection (should not appear in dashboard)
            cls.private_collection = Collection.objects.create(
                name="Private Collection",
                owner=cls.owner_user,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )

            # Owner's collection in review (should appear for moderators)
            cls.review_collection_1 = Collection.objects.create(
                name="Review Collection Alpha",
                owner=cls.owner_user,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )

            # Another owner's collection in review
            cls.review_collection_2 = Collection.objects.create(
                name="Review Collection Beta",
                owner=cls.owner_user,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )

            # Moderator's own collection in review (should NOT appear in their dashboard)
            cls.moderator_collection = Collection.objects.create(
                name="Moderator Review Collection",
                owner=cls.moderator_user,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )

            # Published collection (should not appear)
            cls.published_collection = Collection.objects.create(
                name="Published Collection",
                owner=cls.owner_user,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )

    def test_anonymous_user_cannot_access_dashboard(self):
        """Anonymous users should be redirected to login page."""
        url = reverse("object_management:review_dashboard")
        response = self.client.get(url)

        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn("/users/login/", response.url)

    def test_regular_user_cannot_access_dashboard(self):
        """Regular users without moderation permissions cannot access dashboard."""
        self.client.force_login(self.regular_user)
        url = reverse("object_management:review_dashboard")
        response = self.client.get(url)

        # Should show empty dashboard (no permissions for any model)
        self.assertEqual(response.status_code, 200)
        self.assertIn("review_items", response.context)
        # Should have empty or near-empty list since user can't moderate anything
        review_items = list(response.context["review_items"])
        self.assertEqual(len(review_items), 0)

    def test_moderator_can_access_dashboard(self):
        """Moderators should see the dashboard with items they can moderate."""
        self.client.force_login(self.moderator_user)
        url = reverse("object_management:review_dashboard")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("review_items", response.context)

        # Should see review items but not their own
        review_items = list(response.context["review_items"])
        self.assertGreater(len(review_items), 0)

        # Should not see their own collection
        item_names = [item.name for item in review_items]
        self.assertNotIn("Moderator Review Collection", item_names)

        # Should see other users' collections
        self.assertIn("Review Collection Alpha", item_names)

    def test_staff_user_can_access_dashboard(self):
        """Staff users should see all review items."""
        self.client.force_login(self.staff_user)
        url = reverse("object_management:review_dashboard")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("review_items", response.context)

        review_items = list(response.context["review_items"])
        self.assertGreater(len(review_items), 0)

    def test_dashboard_excludes_private_items(self):
        """Dashboard should not show private items."""
        self.client.force_login(self.moderator_user)
        url = reverse("object_management:review_dashboard")
        response = self.client.get(url)

        review_items = list(response.context["review_items"])
        item_names = [item.name for item in review_items]

        # Private collection should not appear
        self.assertNotIn("Private Collection", item_names)

    def test_dashboard_excludes_published_items(self):
        """Dashboard should not show published items."""
        self.client.force_login(self.moderator_user)
        url = reverse("object_management:review_dashboard")
        response = self.client.get(url)

        review_items = list(response.context["review_items"])
        item_names = [item.name for item in review_items]

        # Published collection should not appear
        self.assertNotIn("Published Collection", item_names)

    def test_dashboard_search_filter(self):
        """Test search filter functionality."""
        self.client.force_login(self.moderator_user)
        url = reverse("object_management:review_dashboard")

        # Search for "Alpha"
        response = self.client.get(url, {"search": "Alpha"})
        self.assertEqual(response.status_code, 200)

        review_items = list(response.context["review_items"])
        item_names = [item.name for item in review_items]

        # Should only see items matching "Alpha"
        self.assertIn("Review Collection Alpha", item_names)
        self.assertNotIn("Review Collection Beta", item_names)

    def test_dashboard_owner_filter(self):
        """Test filtering by owner."""
        self.client.force_login(self.moderator_user)
        url = reverse("object_management:review_dashboard")

        # Filter by owner_user
        response = self.client.get(url, {"owner": self.owner_user.id})
        self.assertEqual(response.status_code, 200)

        review_items = list(response.context["review_items"])

        # All items should be owned by owner_user
        for item in review_items:
            self.assertEqual(item.owner_id, self.owner_user.id)

    def test_dashboard_model_type_filter(self):
        """Test filtering by model type (ContentType)."""
        self.client.force_login(self.moderator_user)
        url = reverse("object_management:review_dashboard")

        # Get Collection content type
        collection_ct = ContentType.objects.get_for_model(Collection)

        # Filter by Collection model type
        response = self.client.get(url, {"model_type": [collection_ct.id]})
        self.assertEqual(response.status_code, 200)

        review_items = list(response.context["review_items"])

        # All items should be Collections
        for item in review_items:
            self.assertIsInstance(item, Collection)

    def test_dashboard_ordering_newest_first(self):
        """Test ordering by newest first (default)."""
        self.client.force_login(self.moderator_user)
        url = reverse("object_management:review_dashboard")

        response = self.client.get(url, {"ordering": "-submitted_at"})
        self.assertEqual(response.status_code, 200)

        review_items = list(response.context["review_items"])

        if len(review_items) >= 2:
            # Items should be ordered newest first
            # (If submitted_at is None, they get current time, so they're newest)
            for i in range(len(review_items) - 1):
                item1 = review_items[i]
                item2 = review_items[i + 1]
                if item1.submitted_at and item2.submitted_at:
                    self.assertGreaterEqual(item1.submitted_at, item2.submitted_at)

    def test_dashboard_ordering_by_name(self):
        """Test ordering by name alphabetically."""
        self.client.force_login(self.moderator_user)
        url = reverse("object_management:review_dashboard")

        response = self.client.get(url, {"ordering": "name"})
        self.assertEqual(response.status_code, 200)

        review_items = list(response.context["review_items"])

        if len(review_items) >= 2:
            # Items should be ordered alphabetically
            item_names = [item.name for item in review_items]
            sorted_names = sorted(item_names)
            self.assertEqual(item_names, sorted_names)

    def test_dashboard_pagination(self):
        """Test that pagination works correctly."""
        self.client.force_login(self.moderator_user)
        url = reverse("object_management:review_dashboard")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Check pagination context
        self.assertIn("page_obj", response.context)
        self.assertIn("paginator", response.context)

    def test_dashboard_shows_correct_context(self):
        """Test that dashboard provides correct context variables."""
        self.client.force_login(self.moderator_user)
        url = reverse("object_management:review_dashboard")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Check required context
        self.assertEqual(response.context["title"], "Content Review Dashboard")
        self.assertEqual(response.context["list_type"], "review")
        self.assertIn("filter", response.context)

    def test_dashboard_uses_correct_template(self):
        """Test that dashboard uses the filtered_list template."""
        self.client.force_login(self.moderator_user)
        url = reverse("object_management:review_dashboard")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Check template used
        template_names = [t.name for t in response.templates]
        self.assertIn("object_management/review_dashboard.html", template_names)
        self.assertIn("filtered_list.html", template_names)

    def test_moderator_only_sees_models_they_can_moderate(self):
        """Test that collection_moderator only sees Collections."""
        self.client.force_login(self.collection_moderator)
        url = reverse("object_management:review_dashboard")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        review_items = list(response.context["review_items"])

        # Should only see Collections
        for item in review_items:
            self.assertIsInstance(item, Collection)

    def test_moderator_sees_collections(self):
        """Test that moderator with permissions sees collections in review."""
        self.client.force_login(self.moderator_user)
        url = reverse("object_management:review_dashboard")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        review_items = list(response.context["review_items"])

        # Should see Collections
        has_collections = any(isinstance(item, Collection) for item in review_items)
        self.assertTrue(has_collections)

    def test_empty_dashboard_when_no_items_in_review(self):
        """Test dashboard shows appropriate message when no items in review."""
        # Create a new moderator with permissions but no items to review
        new_moderator = User.objects.create_user(
            username="new_moderator", password="test123"
        )
        collection_ct = ContentType.objects.get_for_model(Collection)
        collection_perm, _ = Permission.objects.get_or_create(
            codename="can_moderate_collection",
            content_type=collection_ct,
            defaults={"name": "Can moderate collections"},
        )
        new_moderator.user_permissions.add(collection_perm)

        # Move all collections out of review
        with mute_signals(post_save, pre_save):
            Collection.objects.filter(
                publication_status=UserCreatedObject.STATUS_REVIEW
            ).update(publication_status=UserCreatedObject.STATUS_PUBLISHED)

        self.client.force_login(new_moderator)
        url = reverse("object_management:review_dashboard")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Should have empty review_items
        review_items = list(response.context["review_items"])
        self.assertEqual(len(review_items), 0)

        # Template should handle empty state
        self.assertContains(response, "There are no items currently in review")

    def test_dashboard_includes_temporal_distribution_with_plain_manager(self):
        """Models without manager.in_review() must still appear in the dashboard."""
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
        """Models with custom managers must still be resolved to in-review querysets."""
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

    def test_get_available_models_accepts_models_module_subpackages(self):
        """Models in ``<app>.models.<submodule>`` are discoverable for moderation."""
        request = RequestFactory().get(reverse("object_management:review_dashboard"))
        request.user = self.moderator_user

        view = ReviewDashboardView()
        view.setup(request)

        submodule_path = f"{Collection._meta.app_label}.models.submodule"
        with (
            patch("django.apps.apps.get_models", return_value=[Collection]),
            patch.object(Collection, "__module__", submodule_path),
        ):
            available_models = view.get_available_models()

        self.assertIn(Collection, available_models)

    def test_collect_review_items_ignores_models_with_unresolvable_review_queryset(
        self,
    ):
        """collect_review_items should skip failing models instead of crashing."""
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


class ReviewDashboardFilterTests(TestCase):
    """Test the ReviewDashboardFilterSet functionality."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for filter tests."""
        cls.moderator = User.objects.create_user(
            username="moderator", password="test123", is_staff=True
        )
        cls.owner = User.objects.create_user(username="owner", password="test123")

        # Create multiple collections with different attributes
        # Owned by different user so moderator can see them
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
        """Test that filter form renders correctly."""
        self.client.force_login(self.moderator)
        url = reverse("object_management:review_dashboard")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Check that filter form is in context
        self.assertIn("filter", response.context)
        filter_obj = response.context["filter"]

        # Check that expected filters exist
        self.assertIn("search", filter_obj.filters)
        self.assertIn("model_type", filter_obj.filters)
        self.assertIn("owner", filter_obj.filters)
        self.assertIn("ordering", filter_obj.filters)

    def test_filter_preserves_query_parameters(self):
        """Test that filter parameters are preserved in filter form."""
        self.client.force_login(self.moderator)
        url = reverse("object_management:review_dashboard")

        response = self.client.get(url, {"search": "Collection"})
        self.assertEqual(response.status_code, 200)

        # The filter should be in the context
        self.assertIn("filter", response.context)

        # The search value should be preserved in the filter form
        # Check if the form has the search value
        filter_obj = response.context["filter"]
        self.assertEqual(filter_obj.data.get("search"), "Collection")
