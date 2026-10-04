import datetime
import smtplib
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.sites.models import Site
from django.test import RequestFactory, TestCase
from django.urls import reverse
from registration.models import RegistrationProfile

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
        with patch(SEND_EMAIL, side_effect=refused):
            response = self.client.post(
                reverse("registration_register"), self.registration_data()
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.context["form"].errors)
        self.assertFalse(User.objects.filter(username="newbie").exists())
        self.assertFalse(RegistrationProfile.objects.exists())

    def test_transient_smtp_failure_shows_generic_error_and_rolls_back_user(self):
        with patch(SEND_EMAIL, side_effect=smtplib.SMTPServerDisconnected("lost")):
            response = self.client.post(
                reverse("registration_register"), self.registration_data()
            )
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
        with patch(
            SEND_EMAIL,
            side_effect=smtplib.SMTPRecipientsRefused(
                {"pending@example.org": (550, b"5.1.1 no such user")}
            ),
        ):
            response = self.client.post(
                reverse("registration_resend_activation"),
                {"email": "pending@example.org"},
            )
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

        cleanup_expired_registrations()
        self.assertFalse(User.objects.filter(username="stale").exists())
        self.assertTrue(User.objects.filter(username="admin").exists())
