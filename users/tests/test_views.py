import contextlib
import datetime
import io
import smtplib
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.contrib.sites.models import Site
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from registration.models import RegistrationProfile

from users.models import UserProfile
from users.views import RegistrationView

SEND_EMAIL = "registration.models.RegistrationProfile.send_activation_email"


@patch("turnstile.fields.ENABLE", False)
class RegistrationEmailDeliveryTests(TestCase):
    def registration_data(self, email="newbie@example.org"):
        return {
            "username": "newbie",
            "email": email,
            "password1": "not-a-weak-password-4711",
            "password2": "not-a-weak-password-4711",
        }

    def test_successful_registration_creates_inactive_user_and_sends_email(self):
        with patch(SEND_EMAIL) as send_email:
            response = self.client.post(
                reverse("registration_register"), self.registration_data()
            )
        self.assertRedirects(response, reverse("registration_complete"))
        user = User.objects.get(username="newbie")
        self.assertFalse(user.is_active)
        self.assertTrue(RegistrationProfile.objects.filter(user=user).exists())
        send_email.assert_called_once()

    def test_tuple_success_url_redirects_with_unpacked_arguments(self):
        class TupleSuccessRegistrationView(RegistrationView):
            def get_success_url(self, user=None):
                return ("registration_activate", (), {"activation_key": "abc"})

        request = RequestFactory().post(
            reverse("registration_register"), self.registration_data()
        )
        request.user = AnonymousUser()
        with patch(SEND_EMAIL):
            response = TupleSuccessRegistrationView.as_view()(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("registration_activate", kwargs={"activation_key": "abc"}),
        )

    def test_recipient_refused_shows_email_error_and_rolls_back_user(self):
        refused = smtplib.SMTPRecipientsRefused(
            {"newbie@example.org": (550, b"5.1.1 no such user")}
        )
        with (
            patch(SEND_EMAIL, side_effect=refused),
            self.assertLogs("users.views", level="WARNING") as logs,
        ):
            response = self.client.post(
                reverse("registration_register"), self.registration_data()
            )
        self.assertIn("Registration email refused", logs.output[0])
        self.assertIn("newbie@example.org", logs.output[0])
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertFalse(User.objects.filter(username="newbie").exists())
        self.assertFalse(RegistrationProfile.objects.exists())

    def test_transient_smtp_failure_shows_generic_error_and_rolls_back_user(self):
        with (
            patch(SEND_EMAIL, side_effect=smtplib.SMTPServerDisconnected("lost")),
            self.assertLogs("users.views", level="WARNING") as logs,
        ):
            response = self.client.post(
                reverse("registration_register"), self.registration_data()
            )
        self.assertIn("Registration email could not be sent", logs.output[0])
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertFalse(User.objects.filter(username="newbie").exists())
        self.assertFalse(RegistrationProfile.objects.exists())


@patch("turnstile.fields.ENABLE", False)
class ResendActivationEmailDeliveryTests(TestCase):
    def setUp(self):
        self.user = RegistrationProfile.objects.create_inactive_user(
            site=Site.objects.get_current(),
            send_email=False,
            username="pending",
            email="pending@example.org",
            password="irrelevant",
        )
        self.profile = RegistrationProfile.objects.get(user=self.user)

    def test_resend_smtp_failure_shows_error_and_keeps_activation_key(self):
        original_key = self.profile.activation_key
        with (
            patch(
                SEND_EMAIL,
                side_effect=smtplib.SMTPRecipientsRefused(
                    {"pending@example.org": (550, b"5.1.1 no such user")}
                ),
            ),
            self.assertLogs("users.views", level="WARNING") as logs,
        ):
            response = self.client.post(
                reverse("registration_resend_activation"),
                {"email": "pending@example.org"},
            )
        self.assertIn("Activation resend failed", logs.output[0])
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.activation_key, original_key)

    def test_resend_success_rotates_key_and_shows_confirmation(self):
        original_key = self.profile.activation_key
        with patch(SEND_EMAIL) as send_email:
            response = self.client.post(
                reverse("registration_resend_activation"),
                {"email": "pending@example.org"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "registration/resend_activation_complete.html"
        )
        send_email.assert_called_once()
        self.profile.refresh_from_db()
        self.assertNotEqual(self.profile.activation_key, original_key)


class CleanupExpiredRegistrationsTaskTests(TestCase):
    def test_task_deletes_unactivated_users_past_activation_window(self):
        user = RegistrationProfile.objects.create_inactive_user(
            site=Site.objects.get_current(),
            send_email=False,
            username="stale",
            email="stale@example.org",
            password="irrelevant",
        )
        User.objects.filter(pk=user.pk).update(
            date_joined=user.date_joined - datetime.timedelta(days=30)
        )
        from users.tasks import cleanup_expired_registrations

        with (
            self.assertLogs("registration.models", level="WARNING") as logs,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            cleanup_expired_registrations()
        self.assertTrue(
            any("Deleting expired Registration profile" in line for line in logs.output)
        )
        self.assertFalse(User.objects.filter(username="stale").exists())
        self.assertTrue(User.objects.filter(username="admin").exists())


class ReviewNotificationPreferenceViewTests(TestCase):
    """Access and scope checks for the global opt-out preference."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="pref-user", email="pref@example.com"
        )

    def test_profile_page_defaults_enabled_without_creating_profile(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("user_profile"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["review_notifications_enabled"])
        self.assertFalse(UserProfile.objects.filter(user=self.user).exists())

    def test_post_only_changes_own_profile_even_with_forged_user_id(self):
        other = User.objects.create_user(
            username="other-pref", email="other-pref@example.com"
        )
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("review_notification_preference"), data={"user": other.pk}
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(UserProfile.objects.get(user=self.user).review_notifications)
        self.assertFalse(UserProfile.objects.filter(user=other).exists())

    def test_get_on_preference_endpoint_returns_405_without_mutation(self):
        self.client.force_login(self.user)
        with self.assertLogs("django.request", level="WARNING") as logs:
            response = self.client.get(reverse("review_notification_preference"))

        self.assertEqual(response.status_code, 405)
        output = "\n".join(logs.output)
        self.assertIn("Method Not Allowed", output)
        self.assertIn(reverse("review_notification_preference"), output)
        self.assertFalse(UserProfile.objects.filter(user=self.user).exists())

    def test_anonymous_post_redirects_to_login_without_profile(self):
        response = self.client.post(reverse("review_notification_preference"))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/users/login/"))
        self.assertFalse(UserProfile.objects.exists())

    def test_disabled_state_rendered_and_reenabled(self):
        self.client.force_login(self.user)
        self.client.post(reverse("review_notification_preference"))

        response = self.client.get(reverse("user_profile"))
        self.assertFalse(response.context["review_notifications_enabled"])

        self.client.post(reverse("review_notification_preference"))
        self.assertTrue(UserProfile.objects.get(user=self.user).review_notifications)

    def test_preference_post_requires_csrf_token(self):
        middleware = list(settings.MIDDLEWARE)
        csrf = "django.middleware.csrf.CsrfViewMiddleware"
        if csrf not in middleware:
            middleware.append(csrf)
        with override_settings(MIDDLEWARE=middleware):
            client = Client(enforce_csrf_checks=True)
            client.force_login(self.user)
            with self.assertLogs("django.security.csrf", level="WARNING") as logs:
                response = client.post(reverse("review_notification_preference"))

        self.assertEqual(response.status_code, 403)
        output = "\n".join(logs.output)
        self.assertIn("CSRF", output)
        self.assertIn(reverse("review_notification_preference"), output)
        self.assertFalse(UserProfile.objects.filter(user=self.user).exists())
