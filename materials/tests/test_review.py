"""Tests for the review workflow integration with materials models."""

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save, pre_save
from django.test import TestCase
from django.urls import reverse
from factory.django import mute_signals

from materials.models import Material, Sample, SampleSeries
from utils.object_management.models import ReviewAction, UserCreatedObject


class MaterialsReviewWorkflowTests(TestCase):
    """Test the full review workflow (submit → approve/reject → withdraw) for Sample."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner", password="test123")
        cls.moderator = User.objects.create_user(
            username="moderator", password="test123"
        )
        cls.regular_user = User.objects.create_user(
            username="regular", password="test123"
        )

        # Add moderator permission for Sample
        sample_ct = ContentType.objects.get_for_model(Sample)
        perm, _ = Permission.objects.get_or_create(
            codename="can_moderate_sample",
            content_type=sample_ct,
            defaults={"name": "Can moderate samples"},
        )
        cls.moderator.user_permissions.add(perm)

        with mute_signals(post_save, pre_save):
            cls.material = Material.objects.create(
                name="Test Material",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )
            cls.private_sample = Sample.objects.create(
                name="Private Sample",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )
            cls.review_sample = Sample.objects.create(
                name="Review Sample",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )

    def setUp(self):
        self.sample_ct_id = ContentType.objects.get_for_model(Sample).id

    # --- Submit for Review ---

    def test_owner_can_submit_private_sample_for_review(self):
        self.client.force_login(self.owner)
        url = reverse(
            "object_management:submit_for_review",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.private_sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.private_sample.refresh_from_db()
        self.assertEqual(
            self.private_sample.publication_status, UserCreatedObject.STATUS_REVIEW
        )

    def test_non_owner_cannot_submit_sample_for_review(self):
        self.client.force_login(self.regular_user)
        url = reverse(
            "object_management:submit_for_review",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.private_sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.private_sample.refresh_from_db()
        self.assertEqual(
            self.private_sample.publication_status, UserCreatedObject.STATUS_PRIVATE
        )

    def test_anonymous_cannot_submit_sample_for_review(self):
        url = reverse(
            "object_management:submit_for_review",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.private_sample.id,
            },
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/users/login/", response.url)

    # --- Withdraw from Review ---

    def test_owner_can_withdraw_sample_from_review(self):
        self.client.force_login(self.owner)
        url = reverse(
            "object_management:withdraw_from_review",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.review_sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.review_sample.refresh_from_db()
        self.assertEqual(
            self.review_sample.publication_status, UserCreatedObject.STATUS_PRIVATE
        )

    def test_non_owner_cannot_withdraw_sample_from_review(self):
        self.client.force_login(self.regular_user)
        url = reverse(
            "object_management:withdraw_from_review",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.review_sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.review_sample.refresh_from_db()
        self.assertEqual(
            self.review_sample.publication_status, UserCreatedObject.STATUS_REVIEW
        )

    # --- Approve ---

    def test_moderator_can_approve_sample(self):
        self.client.force_login(self.moderator)
        url = reverse(
            "object_management:approve_item",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.review_sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.review_sample.refresh_from_db()
        self.assertEqual(
            self.review_sample.publication_status, UserCreatedObject.STATUS_PUBLISHED
        )
        self.assertEqual(self.review_sample.approved_by, self.moderator)

    def test_regular_user_cannot_approve_sample(self):
        self.client.force_login(self.regular_user)
        url = reverse(
            "object_management:approve_item",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.review_sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.review_sample.refresh_from_db()
        self.assertEqual(
            self.review_sample.publication_status, UserCreatedObject.STATUS_REVIEW
        )

    def test_owner_cannot_approve_own_sample(self):
        self.client.force_login(self.owner)
        url = reverse(
            "object_management:approve_item",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.review_sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.review_sample.refresh_from_db()
        self.assertEqual(
            self.review_sample.publication_status, UserCreatedObject.STATUS_REVIEW
        )

    # --- Reject ---

    def test_moderator_can_reject_sample(self):
        self.client.force_login(self.moderator)
        url = reverse(
            "object_management:reject_item",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.review_sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.review_sample.refresh_from_db()
        self.assertEqual(
            self.review_sample.publication_status, UserCreatedObject.STATUS_DECLINED
        )

    def test_regular_user_cannot_reject_sample(self):
        self.client.force_login(self.regular_user)
        url = reverse(
            "object_management:reject_item",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.review_sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.review_sample.refresh_from_db()
        self.assertEqual(
            self.review_sample.publication_status, UserCreatedObject.STATUS_REVIEW
        )

    # --- Re-submit after rejection ---

    def test_owner_can_resubmit_declined_sample(self):
        with mute_signals(post_save, pre_save):
            self.private_sample.publication_status = UserCreatedObject.STATUS_DECLINED
            self.private_sample.save()

        self.client.force_login(self.owner)
        url = reverse(
            "object_management:submit_for_review",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.private_sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.private_sample.refresh_from_db()
        self.assertEqual(
            self.private_sample.publication_status, UserCreatedObject.STATUS_REVIEW
        )


class MaterialsReviewDetailAccessTests(TestCase):
    """Test access to the review detail view for materials models."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner", password="test123")
        cls.moderator = User.objects.create_user(
            username="moderator", password="test123"
        )
        cls.other_user = User.objects.create_user(username="other", password="test123")

        sample_ct = ContentType.objects.get_for_model(Sample)
        cls.sample_ct_id = sample_ct.id
        perm, _ = Permission.objects.get_or_create(
            codename="can_moderate_sample",
            content_type=sample_ct,
            defaults={"name": "Can moderate samples"},
        )
        cls.moderator.user_permissions.add(perm)

        with mute_signals(post_save, pre_save):
            cls.material = Material.objects.create(
                name="Test Material",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )
            cls.review_sample = Sample.objects.create(
                name="Review Sample",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )
            cls.declined_sample = Sample.objects.create(
                name="Declined Sample",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_DECLINED,
            )

    def _review_detail_url(self, obj):
        return reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": obj.id,
            },
        )

    def test_owner_can_access_review_detail_for_review_sample(self):
        self.client.force_login(self.owner)
        response = self.client.get(self._review_detail_url(self.review_sample))
        self.assertEqual(response.status_code, 200)

    def test_owner_can_access_review_detail_for_declined_sample(self):
        self.client.force_login(self.owner)
        response = self.client.get(self._review_detail_url(self.declined_sample))
        self.assertEqual(response.status_code, 200)

    def test_moderator_can_access_review_detail(self):
        self.client.force_login(self.moderator)
        response = self.client.get(self._review_detail_url(self.review_sample))
        self.assertEqual(response.status_code, 200)

    def test_non_owner_non_moderator_cannot_access_review_detail(self):
        self.client.force_login(self.other_user)
        response = self.client.get(self._review_detail_url(self.review_sample))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_access_review_detail(self):
        response = self.client.get(self._review_detail_url(self.review_sample))
        self.assertEqual(response.status_code, 403)


class SampleDetailTemplateReviewUITests(TestCase):
    """Test that the sample detail template shows review UI elements correctly."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner", password="test123")

        with mute_signals(post_save, pre_save):
            cls.material = Material.objects.create(
                name="Test Material",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )
            cls.private_sample = Sample.objects.create(
                name="Private Sample",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )
            cls.review_sample = Sample.objects.create(
                name="Review Sample",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )
            cls.published_sample = Sample.objects.create(
                name="Published Sample",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )

    def test_private_sample_shows_submit_button_for_owner(self):
        self.client.force_login(self.owner)
        url = reverse("sample-detail", kwargs={"pk": self.private_sample.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Submit for Review")

    def test_review_sample_shows_review_view_link_for_owner(self):
        self.client.force_login(self.owner)
        url = reverse("sample-detail", kwargs={"pk": self.review_sample.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review view")

    def test_published_sample_does_not_show_submit_button(self):
        self.client.force_login(self.owner)
        url = reverse("sample-detail", kwargs={"pk": self.published_sample.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Submit for Review")

    def test_sample_detail_extends_detail_with_options(self):
        self.client.force_login(self.owner)
        url = reverse("sample-detail", kwargs={"pk": self.private_sample.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        template_names = [t.name for t in response.templates]
        self.assertIn("detail_with_options.html", template_names)


class SampleSeriesDetailTemplateReviewUITests(TestCase):
    """Test that the sample series detail template shows review UI elements."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner", password="test123")

        with mute_signals(post_save, pre_save):
            cls.material = Material.objects.create(
                name="Test Material",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )
            cls.private_series = SampleSeries.objects.create(
                name="Private Series",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )
            cls.review_series = SampleSeries.objects.create(
                name="Review Series",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )

    def test_private_series_shows_submit_button_for_owner(self):
        self.client.force_login(self.owner)
        url = reverse("sampleseries-detail", kwargs={"pk": self.private_series.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Submit for Review")

    def test_review_series_shows_review_view_link_for_owner(self):
        self.client.force_login(self.owner)
        url = reverse("sampleseries-detail", kwargs={"pk": self.review_series.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review view")

    def test_series_detail_extends_detail_with_options(self):
        self.client.force_login(self.owner)
        url = reverse("sampleseries-detail", kwargs={"pk": self.private_series.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        template_names = [t.name for t in response.templates]
        self.assertIn("detail_with_options.html", template_names)


class MaterialsReviewDashboardTests(TestCase):
    """Test that materials models appear correctly in the review dashboard."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner", password="test123")
        cls.staff = User.objects.create_user(
            username="staff", password="test123", is_staff=True
        )
        cls.moderator = User.objects.create_user(
            username="moderator", password="test123"
        )

        sample_ct = ContentType.objects.get_for_model(Sample)
        perm, _ = Permission.objects.get_or_create(
            codename="can_moderate_sample",
            content_type=sample_ct,
            defaults={"name": "Can moderate samples"},
        )
        cls.moderator.user_permissions.add(perm)

        with mute_signals(post_save, pre_save):
            cls.material = Material.objects.create(
                name="Test Material",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )
            cls.review_sample = Sample.objects.create(
                name="Dashboard Review Sample",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )
            cls.private_sample = Sample.objects.create(
                name="Dashboard Private Sample",
                material=cls.material,
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )

    def test_review_sample_appears_in_dashboard_for_staff(self):
        self.client.force_login(self.staff)
        url = reverse("object_management:review_dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        review_items = list(response.context["review_items"])
        item_names = [item.name for item in review_items]
        self.assertIn("Dashboard Review Sample", item_names)

    def test_private_sample_not_in_dashboard(self):
        self.client.force_login(self.staff)
        url = reverse("object_management:review_dashboard")
        response = self.client.get(url)
        review_items = list(response.context["review_items"])
        item_names = [item.name for item in review_items]
        self.assertNotIn("Dashboard Private Sample", item_names)

    def test_moderator_sees_review_sample_in_dashboard(self):
        self.client.force_login(self.moderator)
        url = reverse("object_management:review_dashboard")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        review_items = list(response.context["review_items"])
        sample_items = [item for item in review_items if isinstance(item, Sample)]
        self.assertTrue(len(sample_items) > 0)

    def test_filter_dashboard_by_sample_model_type(self):
        self.client.force_login(self.staff)
        sample_ct = ContentType.objects.get_for_model(Sample)
        url = reverse("object_management:review_dashboard")
        response = self.client.get(url, {"model_type": sample_ct.id})
        self.assertEqual(response.status_code, 200)
        review_items = list(response.context["review_items"])
        for item in review_items:
            self.assertIsInstance(item, Sample)


class ReviewActionLoggingTests(TestCase):
    """Test that review actions create audit log entries."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner", password="test123")
        cls.moderator = User.objects.create_user(
            username="moderator", password="test123"
        )

        sample_ct = ContentType.objects.get_for_model(Sample)
        perm, _ = Permission.objects.get_or_create(
            codename="can_moderate_sample",
            content_type=sample_ct,
            defaults={"name": "Can moderate samples"},
        )
        cls.moderator.user_permissions.add(perm)

        with mute_signals(post_save, pre_save):
            cls.material = Material.objects.create(
                name="Test Material",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )

    def setUp(self):
        self.sample_ct_id = ContentType.objects.get_for_model(Sample).id
        with mute_signals(post_save, pre_save):
            self.sample = Sample.objects.create(
                name="Log Test Sample",
                material=self.material,
                owner=self.owner,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )

    def test_submit_creates_review_action_log(self):
        self.client.force_login(self.owner)
        url = reverse(
            "object_management:submit_for_review",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            self.client.post(url)

        logs = ReviewAction.for_object(self.sample)
        self.assertTrue(logs.filter(action=ReviewAction.ACTION_SUBMITTED).exists())

    def test_approve_creates_review_action_log(self):
        with mute_signals(post_save, pre_save):
            self.sample.publication_status = UserCreatedObject.STATUS_REVIEW
            self.sample.save()

        self.client.force_login(self.moderator)
        url = reverse(
            "object_management:approve_item",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            self.client.post(url)

        logs = ReviewAction.for_object(self.sample)
        self.assertTrue(logs.filter(action=ReviewAction.ACTION_APPROVED).exists())

    def test_reject_creates_review_action_log(self):
        with mute_signals(post_save, pre_save):
            self.sample.publication_status = UserCreatedObject.STATUS_REVIEW
            self.sample.save()

        self.client.force_login(self.moderator)
        url = reverse(
            "object_management:reject_item",
            kwargs={
                "content_type_id": self.sample_ct_id,
                "object_id": self.sample.id,
            },
        )
        with mute_signals(post_save, pre_save):
            self.client.post(url)

        logs = ReviewAction.for_object(self.sample)
        self.assertTrue(logs.filter(action=ReviewAction.ACTION_REJECTED).exists())
