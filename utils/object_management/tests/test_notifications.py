"""Tests for owner e-mail notifications on review actions."""

import smtplib

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from sources.waste_collection.models import Collection
from utils.object_management.models import ReviewAction, UserCreatedObject
from utils.object_management.tasks import send_review_action_owner_notification


class ReviewOwnerNotificationTests(TestCase):
    """The owner of an object is notified about review actions by other users."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="owner", email="owner@example.com"
        )
        cls.moderator = User.objects.create_user(
            username="moderator", email="moderator@example.com"
        )
        content_type = ContentType.objects.get_for_model(Collection)
        permission, _ = Permission.objects.get_or_create(
            codename="can_moderate_collection",
            content_type=content_type,
            defaults={"name": "Can moderate collections"},
        )
        cls.moderator.user_permissions.add(permission)
        cls.collection = Collection.objects.create(
            name="Notified Collection",
            owner=cls.owner,
            publication_status=UserCreatedObject.STATUS_REVIEW,
        )
        cls.content_type_id = content_type.id

    def _action_url(self, name, obj=None):
        return reverse(
            f"object_management:{name}",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": (obj or self.collection).id,
            },
        )

    def _post(self, *args, **kwargs):
        """POST and execute on_commit callbacks (notification enqueue)."""
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(*args, **kwargs)

    def test_approve_notifies_owner(self):
        self.client.force_login(self.moderator)
        response = self._post(self._action_url("approve_item"))
        self.assertEqual(response.status_code, 302)

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [self.owner.email])
        self.collection.refresh_from_db()
        self.assertIn(self.collection.name, message.subject + message.body)

    def test_reject_notifies_owner(self):
        self.client.force_login(self.moderator)
        response = self._post(self._action_url("reject_item"))
        self.assertEqual(response.status_code, 302)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.owner.email])

    def test_comment_notifies_owner_and_includes_comment(self):
        self.client.force_login(self.moderator)
        response = self._post(
            self._action_url("add_review_comment"),
            data={"message": "Please add a source."},
        )
        self.assertEqual(response.status_code, 302)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.owner.email])
        self.assertIn("Please add a source.", mail.outbox[0].body)

    def test_notification_contains_link_to_review_detail(self):
        self.client.force_login(self.moderator)
        self._post(self._action_url("approve_item"))

        self.assertEqual(len(mail.outbox), 1)
        review_url = reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.collection.id,
            },
        )
        self.assertIn(review_url, mail.outbox[0].body)

    def test_owners_own_actions_do_not_notify(self):
        private_collection = Collection.objects.create(
            name="Own Action Collection",
            owner=self.owner,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )
        self.client.force_login(self.owner)
        response = self._post(self._action_url("submit_for_review", private_collection))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_no_notification_without_owner_email(self):
        emailless_owner = User.objects.create_user(username="emailless")
        collection = Collection.objects.create(
            name="Emailless Collection",
            owner=emailless_owner,
            publication_status=UserCreatedObject.STATUS_REVIEW,
        )
        self.client.force_login(self.moderator)
        response = self._post(self._action_url("approve_item", collection))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_missing_object_does_not_break_or_notify(self):
        orphaned_id = self.collection.id
        self.collection.delete()
        with self.captureOnCommitCallbacks(execute=True):
            ReviewAction.objects.create(
                content_type_id=self.content_type_id,
                object_id=orphaned_id,
                user=self.moderator,
                action=ReviewAction.ACTION_COMMENT,
                comment="orphaned",
            )
        self.assertEqual(len(mail.outbox), 0)

    def test_ownership_transfer_before_delivery_skips_former_owner(self):
        new_owner = User.objects.create_user(
            username="newowner", email="newowner@example.com"
        )
        self.client.force_login(self.moderator)
        with self.captureOnCommitCallbacks() as callbacks:
            response = self.client.post(
                self._action_url("add_review_comment"),
                data={"message": "Please add a source."},
            )
        self.assertEqual(response.status_code, 302)

        self.collection.transfer_ownership(new_owner)
        for callback in callbacks:
            callback()

        self.assertEqual(len(mail.outbox), 0)

    def test_ownership_transfer_still_notifies_former_owner_with_review_access(self):
        new_owner = User.objects.create_user(
            username="newowner", email="newowner@example.com"
        )
        self.owner.is_staff = True
        self.owner.save(update_fields=["is_staff"])
        self.client.force_login(self.moderator)
        with self.captureOnCommitCallbacks() as callbacks:
            response = self.client.post(self._action_url("reject_item"))
        self.assertEqual(response.status_code, 302)

        self.collection.transfer_ownership(new_owner)
        for callback in callbacks:
            callback()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.owner.email])
        self.assertIn(f"Hello {self.owner.username}", mail.outbox[0].body)

    def test_notification_task_retries_transient_mail_errors(self):
        task = send_review_action_owner_notification
        self.assertIn(smtplib.SMTPException, task.autoretry_for)
        self.assertIn(OSError, task.autoretry_for)
        self.assertGreater(task.max_retries, 0)

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_notification_links_use_https_when_ssl_redirect_enabled(self):
        self.client.force_login(self.moderator)
        self._post(self._action_url("approve_item"))

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("https://", mail.outbox[0].body)
        self.assertNotIn("http://", mail.outbox[0].body)

    @override_settings(SITE_ID=999, CANONICAL_HOST="brit.example.org")
    def test_missing_site_row_falls_back_to_canonical_host(self):
        self.client.force_login(self.moderator)
        self._post(self._action_url("approve_item"))

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("http://brit.example.org", mail.outbox[0].body)
