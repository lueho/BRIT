from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save, pre_save
from django.test import TestCase
from django.urls import reverse
from factory.django import mute_signals

from case_studies.soilcom.models import Collection
from utils.object_management.models import UserCreatedObject


class ReviewWorkflowModalViewTests(TestCase):
    """Tests for modal review action views (submit, withdraw, approve, reject)."""

    @classmethod
    def setUpTestData(cls):
        # Users
        cls.owner = User.objects.create_user(username="owner")
        cls.moderator = User.objects.create_user(username="moderator")
        cls.regular_user = User.objects.create_user(username="regular")

        # Moderator permission for Collection
        content_type = ContentType.objects.get_for_model(Collection)
        permission = Permission.objects.create(
            codename="can_moderate_collection",
            name="Can moderate collections",
            content_type=content_type,
        )
        cls.moderator.user_permissions.add(permission)

        # Collections in different states
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

        cls.ct_id = ContentType.objects.get_for_model(Collection).id

    # --- Submit modal ---
    def test_submit_for_review_modal_get_and_post(self):
        url = reverse(
            "object_management:submit_for_review_modal",
            kwargs={
                "content_type_id": self.ct_id,
                "object_id": self.private_collection.id,
            },
        )

        # GET should render modal for owner
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # POST should submit for review
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        # State change
        self.private_collection.refresh_from_db()
        self.assertEqual(
            self.private_collection.publication_status,
            UserCreatedObject.STATUS_REVIEW,
        )

        # Regular user cannot submit someone else's object
        with mute_signals(post_save, pre_save):
            self.private_collection.publication_status = UserCreatedObject.STATUS_PRIVATE
            self.private_collection.save()
        self.client.force_login(self.regular_user)
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    # --- Withdraw modal ---
    def test_withdraw_from_review_modal_get_and_post(self):
        url = reverse(
            "object_management:withdraw_from_review_modal",
            kwargs={
                "content_type_id": self.ct_id,
                "object_id": self.review_collection.id,
            },
        )

        # GET should render modal for owner
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # POST should withdraw from review
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        # State change
        self.review_collection.refresh_from_db()
        self.assertEqual(
            self.review_collection.publication_status,
            UserCreatedObject.STATUS_PRIVATE,
        )

        # Regular user cannot withdraw someone else's object
        with mute_signals(post_save, pre_save):
            self.review_collection.publication_status = UserCreatedObject.STATUS_REVIEW
            self.review_collection.save()
        self.client.force_login(self.regular_user)
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    # --- Approve modal ---
    def test_approve_item_modal_get_and_post(self):
        url = reverse(
            "object_management:approve_item_modal",
            kwargs={
                "content_type_id": self.ct_id,
                "object_id": self.review_collection.id,
            },
        )

        # GET should render modal for moderator
        self.client.force_login(self.moderator)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # POST should approve and set approved_by
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        self.review_collection.refresh_from_db()
        self.assertEqual(
            self.review_collection.publication_status,
            UserCreatedObject.STATUS_PUBLISHED,
        )
        self.assertEqual(self.review_collection.approved_by, self.moderator)

        # Regular user cannot approve
        with mute_signals(post_save, pre_save):
            self.review_collection.publication_status = UserCreatedObject.STATUS_REVIEW
            self.review_collection.approved_by = None
            self.review_collection.approved_at = None
            self.review_collection.save()
        self.client.force_login(self.regular_user)
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    # --- Reject modal ---
    def test_reject_item_modal_get_and_post(self):
        url = reverse(
            "object_management:reject_item_modal",
            kwargs={
                "content_type_id": self.ct_id,
                "object_id": self.review_collection.id,
            },
        )

        # GET should render modal for moderator
        self.client.force_login(self.moderator)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # POST should reject
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        self.review_collection.refresh_from_db()
        self.assertEqual(
            self.review_collection.publication_status,
            UserCreatedObject.STATUS_DECLINED,
        )

        # Regular user cannot reject
        with mute_signals(post_save, pre_save):
            self.review_collection.publication_status = UserCreatedObject.STATUS_REVIEW
            self.review_collection.save()
        self.client.force_login(self.regular_user)
        with mute_signals(post_save, pre_save):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
