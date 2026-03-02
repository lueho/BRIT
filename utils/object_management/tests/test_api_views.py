"""Tests for review workflow API endpoints in object_management."""

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save, pre_save
from django.test import TestCase
from django.urls import reverse
from factory.django import mute_signals

from case_studies.soilcom.models import Collection
from utils.object_management.models import ReviewAction, UserCreatedObject


class ReviewAPIViewsTests(TestCase):
    """Validate review queue, comment, and review-context API behavior."""

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
            cls.review_collection = Collection.objects.create(
                name="Review Collection",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )
            cls.moderator_owned_review_collection = Collection.objects.create(
                name="Moderator Owned Review Collection",
                owner=cls.moderator,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )

        cls.content_type_id = content_type.id

    def test_review_queue_requires_authentication(self):
        """Anonymous callers are denied by API auth requirements."""
        url = reverse("object_management:api_review_queue")

        response = self.client.get(url)

        self.assertIn(response.status_code, (401, 403))

    def test_review_queue_returns_items_for_moderator(self):
        """Moderators receive queue items, excluding their own submissions."""
        url = reverse("object_management:api_review_queue")
        self.client.force_login(self.moderator)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("results", payload)

        names = [item["name"] for item in payload["results"]]
        self.assertIn("Review Collection", names)
        self.assertNotIn("Moderator Owned Review Collection", names)

    def test_add_review_comment_api_allows_moderator(self):
        """Moderators can add review comments via API."""
        url = reverse(
            "object_management:api_add_review_comment",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )
        self.client.force_login(self.moderator)

        response = self.client.post(url, data={"comment": "Looks good"})

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            ReviewAction.objects.filter(
                content_type_id=self.content_type_id,
                object_id=self.review_collection.id,
                action=ReviewAction.ACTION_COMMENT,
                user=self.moderator,
                comment="Looks good",
            ).exists()
        )

    def test_add_review_comment_api_forbids_regular_user(self):
        """Non-moderator users cannot comment on others' review items."""
        url = reverse(
            "object_management:api_add_review_comment",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )
        self.client.force_login(self.regular_user)

        response = self.client.post(url, data={"comment": "No access"})

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type_id=self.content_type_id,
                object_id=self.review_collection.id,
                action=ReviewAction.ACTION_COMMENT,
                user=self.regular_user,
            ).exists()
        )

    def test_review_context_api_success(self):
        """Context endpoint returns object and review-history payload."""
        url = reverse(
            "object_management:api_review_context",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )
        self.client.force_login(self.moderator)

        ReviewAction.objects.create(
            content_type_id=self.content_type_id,
            object_id=self.review_collection.id,
            action=ReviewAction.ACTION_COMMENT,
            comment="Existing comment",
            user=self.moderator,
        )

        response = self.client.get(url, data={"include_history": True})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("context", payload)
        self.assertEqual(
            payload["context"]["object"]["object_id"], self.review_collection.id
        )
        self.assertEqual(
            payload["context"]["review_history"][0]["comment"], "Existing comment"
        )

    def test_review_context_rejects_invalid_history_limit(self):
        """history_limit must be parseable as integer."""
        url = reverse(
            "object_management:api_review_context",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )
        self.client.force_login(self.moderator)

        response = self.client.get(url, data={"history_limit": "invalid"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "history_limit must be an integer.",
        )

    def test_review_context_forbids_regular_user(self):
        """Non-moderators cannot access context for others' review items."""
        url = reverse(
            "object_management:api_review_context",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )
        self.client.force_login(self.regular_user)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)
