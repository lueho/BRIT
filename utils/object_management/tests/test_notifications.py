"""Tests for review-action e-mail notifications to owners and commenters."""

import smtplib
from unittest import mock

from celery.exceptions import Retry
from django.conf import settings
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.db.models.signals import post_save
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from factory.django import mute_signals

from sources.waste_collection.models import Collection
from users.models import UserProfile
from utils.object_management.models import (
    ReviewAction,
    ReviewNotificationMute,
    UserCreatedObject,
)
from utils.object_management.tasks import (
    send_review_action_notification_to_user,
    send_review_action_notifications,
)


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

    def test_broker_fallback_uses_committed_owner_after_transfer(self):
        new_owner = User.objects.create_user(
            username="newowner", email="newowner@example.com"
        )
        with (
            mock.patch.object(
                send_review_action_notifications,
                "delay",
                side_effect=ConnectionError("broker down"),
            ),
            self.assertLogs("utils.object_management.signals", level="WARNING") as logs,
            self.captureOnCommitCallbacks(execute=True),
        ):
            ReviewAction.objects.create(
                content_type_id=self.content_type_id,
                object_id=self.collection.id,
                user=self.moderator,
                action=ReviewAction.ACTION_COMMENT,
                comment="Please add a source.",
            )
            self.collection.transfer_ownership(new_owner)

        self.assertTrue(
            any("Could not queue notifications" in line for line in logs.output)
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_notification_task_retries_transient_mail_errors(self):
        task = send_review_action_notification_to_user
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
        with self.assertLogs(
            "utils.object_management.notifications", level="WARNING"
        ) as logs:
            self._post(self._action_url("approve_item"))

        self.assertTrue(any("No Site row" in line for line in logs.output))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("http://brit.example.org", mail.outbox[0].body)


class ReviewNotificationTestBase(TestCase):
    """Shared fixtures for review notification tests."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="owner", email="owner@example.com"
        )
        cls.moderator = User.objects.create_user(
            username="moderator", email="moderator@example.com"
        )
        cls.commenter = User.objects.create_user(
            username="commenter", email="commenter@example.com"
        )
        content_type = ContentType.objects.get_for_model(Collection)
        cls.moderation_permission, _ = Permission.objects.get_or_create(
            codename="can_moderate_collection",
            content_type=content_type,
            defaults={"name": "Can moderate collections"},
        )
        cls.moderator.user_permissions.add(cls.moderation_permission)
        cls.commenter.user_permissions.add(cls.moderation_permission)
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

    def _mute_url(self, obj=None):
        return self._action_url("review_notification_mute", obj)

    def _post(self, *args, **kwargs):
        """POST and execute on_commit callbacks (notification enqueue)."""
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(*args, **kwargs)

    def _add_comment(self, user, text, obj=None):
        """Record a past comment without triggering a notification."""
        with mute_signals(post_save):
            ReviewAction.objects.create(
                content_type_id=self.content_type_id,
                object_id=(obj or self.collection).id,
                user=user,
                action=ReviewAction.ACTION_COMMENT,
                comment=text,
            )

    @staticmethod
    def _recipients():
        return {message.to[0] for message in mail.outbox}


class ReviewParticipantNotificationTests(ReviewNotificationTestBase):
    """Users who commented on an object are notified about later actions."""

    def test_new_comment_notifies_owner_and_past_commenter(self):
        self._add_comment(self.commenter, "Earlier feedback.")
        self.client.force_login(self.moderator)
        response = self._post(
            self._action_url("add_review_comment"),
            data={"message": "Thanks for the update."},
        )
        self.assertEqual(response.status_code, 302)

        self.assertEqual(self._recipients(), {self.owner.email, self.commenter.email})
        commenter_mail = next(m for m in mail.outbox if m.to == [self.commenter.email])
        self.assertIn("Thanks for the update.", commenter_mail.body)

    def test_status_change_notifies_past_commenter(self):
        self._add_comment(self.commenter, "Earlier feedback.")
        self.client.force_login(self.moderator)
        response = self._post(self._action_url("approve_item"))
        self.assertEqual(response.status_code, 302)

        self.assertEqual(self._recipients(), {self.owner.email, self.commenter.email})

    def test_actor_is_not_notified(self):
        self._add_comment(self.commenter, "Earlier feedback.")
        self.client.force_login(self.owner)
        response = self._post(
            self._action_url("add_review_comment"),
            data={"message": "Updated, thanks."},
        )
        self.assertEqual(response.status_code, 302)

        self.assertEqual(self._recipients(), {self.commenter.email})

    def test_owner_commenter_receives_single_notification(self):
        self._add_comment(self.owner, "Note to self.")
        self.client.force_login(self.moderator)
        self._post(
            self._action_url("add_review_comment"),
            data={"message": "Looks fine."},
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.owner.email])

    def test_commenter_without_email_is_skipped(self):
        emailless = User.objects.create_user(username="emailless")
        emailless.user_permissions.add(
            Permission.objects.get(codename="can_moderate_collection")
        )
        self._add_comment(emailless, "No address.")
        self.client.force_login(self.moderator)
        self._post(self._action_url("add_review_comment"), data={"message": "Ping."})

        self.assertEqual(self._recipients(), {self.owner.email})

    def test_commenter_without_review_access_is_skipped(self):
        staffer = User.objects.create_user(
            username="staffer", email="staffer@example.com", is_staff=True
        )
        self._add_comment(staffer, "Staff feedback.")
        staffer.is_staff = False
        staffer.save(update_fields=["is_staff"])
        self.client.force_login(self.moderator)
        self._post(self._action_url("add_review_comment"), data={"message": "Ping."})

        self.assertEqual(self._recipients(), {self.owner.email})

    def test_commenter_on_other_object_is_not_notified(self):
        other = Collection.objects.create(
            name="Other Collection",
            owner=self.owner,
            publication_status=UserCreatedObject.STATUS_REVIEW,
        )
        self._add_comment(self.commenter, "Other item.", obj=other)
        self.client.force_login(self.moderator)
        self._post(self._action_url("add_review_comment"), data={"message": "Ping."})

        self.assertEqual(self._recipients(), {self.owner.email})

    def _create_action(self, user, action=ReviewAction.ACTION_COMMENT, text=""):
        with mute_signals(post_save):
            return ReviewAction.objects.create(
                content_type_id=self.content_type_id,
                object_id=self.collection.id,
                user=user,
                action=action,
                comment=text,
            )

    def test_deleted_captured_owner_does_not_fall_back_to_current_owner(self):
        self._add_comment(self.commenter, "Earlier feedback.")
        action = self._create_action(self.moderator, text="Please add a source.")
        missing_owner_id = User.objects.order_by("-pk").first().pk + 1000

        with self.assertLogs("utils.object_management.tasks", level="WARNING") as logs:
            send_review_action_notifications.delay(action.pk, missing_owner_id)

        self.assertTrue(any("no longer exists" in line for line in logs.output))
        self.assertEqual(self._recipients(), {self.commenter.email})

    def test_later_commenter_is_not_notified_about_earlier_action(self):
        action = self._create_action(self.moderator, text="First feedback.")
        self._add_comment(self.commenter, "Joined later.")

        send_review_action_notifications.delay(action.pk, self.owner.pk)

        self.assertEqual(self._recipients(), {self.owner.email})

    def test_mail_retry_does_not_resend_to_delivered_recipients(self):
        self._add_comment(self.commenter, "Earlier feedback.")
        action = self._create_action(self.moderator, text="Ping.")
        with mock.patch.object(
            send_review_action_notification_to_user, "delay"
        ) as deliver:
            queued = send_review_action_notifications.delay(
                action.pk, self.owner.pk
            ).get()

        self.assertEqual(queued, 2)
        self.assertEqual(len(mail.outbox), 0)
        deliveries = [call.args for call in deliver.call_args_list]
        self.assertCountEqual(
            deliveries,
            [(action.pk, self.owner.pk), (action.pk, self.commenter.pk)],
        )
        self.assertFalse(getattr(send_review_action_notifications, "autoretry_for", ()))

        real_send_mail = mail.send_mail

        def flaky_send_mail(subject, body, from_email, recipient_list, **kwargs):
            if recipient_list == [self.commenter.email] and not failed:
                failed.append(True)
                raise smtplib.SMTPException("temporary failure")
            return real_send_mail(subject, body, from_email, recipient_list, **kwargs)

        failed = []
        with mock.patch(
            "utils.object_management.notifications.send_mail",
            side_effect=flaky_send_mail,
        ):
            for args in deliveries:
                try:
                    send_review_action_notification_to_user.apply(args=args).get()
                except Retry:
                    retry_args = args
            send_review_action_notification_to_user.apply(args=retry_args).get()

        self.assertTrue(failed)
        self.assertEqual(
            sorted(message.to[0] for message in mail.outbox),
            sorted([self.owner.email, self.commenter.email]),
        )


class ReviewNotificationOptOutTests(ReviewNotificationTestBase):
    """Muted objects and disabled preferences suppress review e-mails."""

    def _mute(self, user, obj=None):
        obj = obj or self.collection
        return ReviewNotificationMute.objects.create(
            user=user,
            content_type_id=self.content_type_id,
            object_id=obj.id,
        )

    def _review_detail_url(self, obj=None):
        return self._action_url("review_item_detail", obj)

    def test_muted_commenter_is_skipped(self):
        self._add_comment(self.commenter, "Earlier feedback.")
        self._mute(self.commenter)
        self.client.force_login(self.moderator)
        self._post(self._action_url("add_review_comment"), data={"message": "Ping."})

        self.assertEqual(self._recipients(), {self.owner.email})

    def test_muted_owner_is_skipped(self):
        self._add_comment(self.commenter, "Earlier feedback.")
        self._mute(self.owner)
        self.client.force_login(self.moderator)
        self._post(self._action_url("add_review_comment"), data={"message": "Ping."})

        self.assertEqual(self._recipients(), {self.commenter.email})

    def test_global_optout_suppresses_commenter(self):
        UserProfile.objects.create(user=self.commenter, review_notifications=False)
        self._add_comment(self.commenter, "Earlier feedback.")
        self.client.force_login(self.moderator)
        self._post(self._action_url("add_review_comment"), data={"message": "Ping."})

        self.assertEqual(self._recipients(), {self.owner.email})

    def test_global_optout_suppresses_owner(self):
        UserProfile.objects.create(user=self.owner, review_notifications=False)
        self._add_comment(self.commenter, "Earlier feedback.")
        self.client.force_login(self.moderator)
        self._post(self._action_url("add_review_comment"), data={"message": "Ping."})

        self.assertEqual(self._recipients(), {self.commenter.email})

    def test_mute_view_toggles_notifications_for_item(self):
        self.client.force_login(self.commenter)
        response = self.client.post(self._mute_url())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ReviewNotificationMute.objects.filter(user=self.commenter).exists()
        )

        self._add_comment(self.commenter, "Earlier feedback.")
        self.client.force_login(self.moderator)
        self._post(self._action_url("add_review_comment"), data={"message": "Ping."})
        self.assertEqual(self._recipients(), {self.owner.email})

        self.client.force_login(self.commenter)
        self.client.post(self._mute_url())
        self.assertFalse(
            ReviewNotificationMute.objects.filter(user=self.commenter).exists()
        )

    def test_mute_view_get_shows_current_state(self):
        self.client.force_login(self.commenter)
        response = self.client.get(self._mute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Disable")

        self._mute(self.commenter)
        response = self.client.get(self._mute_url())
        self.assertContains(response, "Enable")

    def test_mute_view_get_is_read_only(self):
        self.client.force_login(self.commenter)
        actions_before = ReviewAction.objects.count()

        response = self.client.get(self._mute_url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ReviewAction.objects.count(), actions_before)
        self.assertFalse(ReviewNotificationMute.objects.exists())

    def test_mute_view_post_ignores_external_next(self):
        self.client.force_login(self.commenter)
        response = self.client.post(
            self._mute_url(), data={"next": "https://attacker.example/"}
        )
        self.assertRedirects(
            response,
            self.collection.get_absolute_url(),
            fetch_redirect_response=False,
        )

    def test_mute_view_post_ignores_scheme_relative_next(self):
        self.client.force_login(self.commenter)
        response = self.client.post(
            self._mute_url(), data={"next": "//attacker.example/"}
        )
        self.assertRedirects(
            response,
            self.collection.get_absolute_url(),
            fetch_redirect_response=False,
        )

    def test_mute_view_post_honors_review_detail_next(self):
        self.client.force_login(self.commenter)
        response = self.client.post(
            self._mute_url(), data={"next": self._review_detail_url()}
        )
        self.assertRedirects(
            response, self._review_detail_url(), fetch_redirect_response=False
        )

    def test_mute_view_secure_request_rejects_http_next(self):
        self.client.force_login(self.commenter)
        response = self.client.post(
            self._mute_url(), data={"next": "http://testserver/home/"}, secure=True
        )
        self.assertRedirects(
            response,
            self.collection.get_absolute_url(),
            fetch_redirect_response=False,
        )

    def test_mute_view_secure_request_accepts_https_same_host(self):
        self.client.force_login(self.commenter)
        response = self.client.post(
            self._mute_url(), data={"next": "https://testserver/home/"}, secure=True
        )
        self.assertEqual(response["Location"], "https://testserver/home/")

    def test_owner_without_change_permission_can_mute_own_subscription(self):
        self.client.force_login(self.owner)
        response = self.client.post(self._mute_url())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ReviewNotificationMute.objects.filter(user=self.owner).exists())

    def test_staff_can_mute_own_subscription(self):
        staff = User.objects.create_user(
            username="staffer", email="staffer@example.com", is_staff=True
        )
        self.client.force_login(staff)
        response = self.client.post(self._mute_url())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ReviewNotificationMute.objects.filter(user=staff).exists())

    def test_moderator_can_mute_own_subscription(self):
        self.client.force_login(self.moderator)
        response = self.client.post(self._mute_url())
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ReviewNotificationMute.objects.filter(user=self.moderator).exists()
        )

    def test_posted_user_id_cannot_mute_another_user(self):
        outsider = User.objects.create_user(
            username="victim", email="victim@example.com"
        )
        self.client.force_login(self.commenter)
        response = self.client.post(self._mute_url(), data={"user": outsider.pk})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ReviewNotificationMute.objects.filter(user=self.commenter).exists()
        )
        self.assertFalse(ReviewNotificationMute.objects.filter(user=outsider).exists())

    def test_mute_view_denies_user_without_review_access(self):
        outsider = User.objects.create_user(
            username="outsider", email="outsider@example.com"
        )
        self.client.force_login(outsider)
        with self.assertLogs("django.request", level="WARNING") as logs:
            get_response = self.client.get(self._mute_url())
            post_response = self.client.post(self._mute_url())
        self.assertEqual(get_response.status_code, 403)
        self.assertEqual(post_response.status_code, 403)
        output = "\n".join(logs.output)
        self.assertIn("Forbidden", output)
        self.assertIn(self._mute_url(), output)
        self.assertGreaterEqual(len(logs.output), 2)
        self.assertFalse(ReviewNotificationMute.objects.filter(user=outsider).exists())

    def test_mute_view_post_requires_csrf_token(self):
        middleware = list(settings.MIDDLEWARE)
        csrf = "django.middleware.csrf.CsrfViewMiddleware"
        if csrf not in middleware:
            middleware.append(csrf)
        actions_before = ReviewAction.objects.count()
        with override_settings(MIDDLEWARE=middleware):
            client = Client(enforce_csrf_checks=True)
            client.force_login(self.owner)
            with self.assertLogs("django.security.csrf", level="WARNING") as logs:
                response = client.post(self._mute_url())

        self.assertEqual(response.status_code, 403)
        output = "\n".join(logs.output)
        self.assertIn("CSRF", output)
        self.assertIn(self._mute_url(), output)
        self.assertFalse(ReviewNotificationMute.objects.exists())
        self.assertEqual(ReviewAction.objects.count(), actions_before)

    def test_mute_view_requires_login(self):
        response = self.client.post(self._mute_url())
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ReviewNotificationMute.objects.exists())

    def test_profile_preference_view_toggles(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("review_notification_preference"))
        self.assertEqual(response.status_code, 302)
        profile = UserProfile.objects.get(user=self.owner)
        self.assertFalse(profile.review_notifications)

        self.client.post(reverse("review_notification_preference"))
        profile.refresh_from_db()
        self.assertTrue(profile.review_notifications)

    def test_email_contains_mute_and_profile_links(self):
        self.client.force_login(self.moderator)
        self._post(self._action_url("add_review_comment"), data={"message": "Ping."})

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self._mute_url(), mail.outbox[0].body)
        self.assertIn(reverse("user_profile"), mail.outbox[0].body)

    def _create_action(self, user, action=ReviewAction.ACTION_COMMENT, text=""):
        with mute_signals(post_save):
            return ReviewAction.objects.create(
                content_type_id=self.content_type_id,
                object_id=self.collection.id,
                user=user,
                action=action,
                comment=text,
            )

    def _queued_deliveries(self, action):
        with mock.patch.object(
            send_review_action_notification_to_user, "delay"
        ) as deliver:
            send_review_action_notifications.delay(action.pk, self.owner.pk).get()
        return {call.args[1]: call.args for call in deliver.call_args_list}

    def test_queued_delivery_skips_globally_disabled_recipient(self):
        self._add_comment(self.commenter, "Earlier feedback.")
        action = self._create_action(self.moderator, text="Ping.")
        deliveries = self._queued_deliveries(action)
        self.assertEqual(set(deliveries), {self.owner.pk, self.commenter.pk})

        UserProfile.objects.create(user=self.commenter, review_notifications=False)
        results = {
            recipient_id: send_review_action_notification_to_user.apply(args=args).get()
            for recipient_id, args in deliveries.items()
        }
        self.assertFalse(results[self.commenter.pk])
        self.assertTrue(results[self.owner.pk])
        self.assertEqual(self._recipients(), {self.owner.email})

    def test_queued_delivery_skips_per_object_muted_recipient(self):
        self._add_comment(self.commenter, "Earlier feedback.")
        action = self._create_action(self.moderator, text="Ping.")
        deliveries = self._queued_deliveries(action)
        self.assertEqual(set(deliveries), {self.owner.pk, self.commenter.pk})

        self._mute(self.owner)
        self.assertFalse(
            send_review_action_notification_to_user.apply(
                args=deliveries[self.owner.pk]
            ).get()
        )
        self.assertTrue(
            send_review_action_notification_to_user.apply(
                args=deliveries[self.commenter.pk]
            ).get()
        )
        self.assertEqual(self._recipients(), {self.commenter.email})

    def test_muted_other_object_does_not_suppress_delivery(self):
        other = Collection.objects.create(
            name="Other Collection",
            owner=self.owner,
            publication_status=UserCreatedObject.STATUS_REVIEW,
        )
        self._mute(self.commenter, obj=other)
        self._add_comment(self.commenter, "Earlier feedback.")
        action = self._create_action(self.moderator, text="Ping.")

        result = send_review_action_notification_to_user.apply(
            args=(action.pk, self.commenter.pk)
        ).get()

        self.assertTrue(result)
        self.assertIn(self.commenter.email, self._recipients())
