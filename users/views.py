import logging
import smtplib

from django.contrib import messages
from django.contrib.auth.mixins import (
    AccessMixin,
    LoginRequiredMixin,
    UserPassesTestMixin,
)
from django.contrib.auth.models import User
from django.contrib.sites.shortcuts import get_current_site
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import DeleteView, TemplateView, View
from django_tomselect.autocompletes import AutocompleteModelView
from registration.backends.default.views import (
    RegistrationView as BaseRegistrationView,
)
from registration.backends.default.views import (
    ResendActivationView as BaseResendActivationView,
)

from utils.modal import BSModalLoginView
from utils.object_management.policy import is_admin

from .forms import CustomAuthenticationForm
from .models import UserProfile

logger = logging.getLogger(__name__)

MAIL_DELIVERY_ERROR = _(
    "The activation email could not be sent right now. "
    "Please try again in a few minutes."
)


class RegistrationView(BaseRegistrationView):
    """Registers the user and sends the activation email atomically.

    The upstream backend schedules the email via ``transaction.on_commit``,
    so a refused recipient crashes the request after the user row is already
    committed. Sending inside our own atomic block instead rolls the account
    back and reports delivery problems as form errors.
    """

    SEND_ACTIVATION_EMAIL = False

    def form_valid(self, form):
        try:
            with transaction.atomic():
                new_user = self.register(form)
                new_user.registrationprofile.send_activation_email(
                    get_current_site(self.request), self.request
                )
        except smtplib.SMTPRecipientsRefused as exc:
            logger.warning(
                "Registration email refused for %s: %s",
                form.cleaned_data.get("email"),
                exc.recipients,
            )
            if all(500 <= code < 600 for code, _ in exc.recipients.values()):
                form.add_error(
                    "email",
                    _(
                        "We could not send email to this address. "
                        "Please double-check it for typos."
                    ),
                )
            else:
                form.add_error(None, MAIL_DELIVERY_ERROR)
            return self.form_invalid(form)
        except (smtplib.SMTPException, OSError) as exc:
            logger.warning("Registration email could not be sent: %s", exc)
            form.add_error(None, MAIL_DELIVERY_ERROR)
            return self.form_invalid(form)

        if hasattr(self.request, "session"):
            self.request.session["registration_email"] = form.cleaned_data["email"]
        success_url = self.get_success_url(new_user)
        try:
            to, args, kwargs = success_url
        except ValueError:
            return redirect(success_url)
        return redirect(to, *args, **kwargs)


class ResendActivationView(BaseResendActivationView):
    """Resends the activation email; delivery failures surface as form errors.

    The transaction keeps the previously emailed activation key valid when
    the resend fails.
    """

    def form_valid(self, form):
        try:
            with transaction.atomic():
                return super().form_valid(form)
        except (smtplib.SMTPException, OSError) as exc:
            logger.warning(
                "Activation resend failed for %s: %s",
                form.cleaned_data.get("email"),
                exc,
            )
            form.add_error(None, MAIL_DELIVERY_ERROR)
            return self.form_invalid(form)


class UserDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Delete a user account.

    Accounts are administrative records: only the account holder or an
    object administrator (``object_management.administer_objects`` /
    superuser per ``policy.is_admin``) may delete one. Previously any
    authenticated user could delete any account by pk.
    """

    model = User
    template_name = "modal_user_delete.html"
    success_message = "Successfully deleted."
    success_url = reverse_lazy("home")

    def test_func(self):
        user = self.request.user
        return user.pk == self.kwargs.get("pk") or is_admin(user)


class UserProfileView(LoginRequiredMixin, TemplateView):
    model = User
    template_name = "user_profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = getattr(self.request.user, "profile", None)
        context["review_notifications_enabled"] = (
            profile.review_notifications if profile is not None else True
        )
        return context


class ReviewNotificationPreferenceView(LoginRequiredMixin, View):
    """Toggle all review-workflow notification e-mails for the current user."""

    def post(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.review_notifications = not profile.review_notifications
        profile.save(update_fields=["review_notifications"])
        if profile.review_notifications:
            messages.success(request, "Review e-mail notifications enabled.")
        else:
            messages.success(request, "Review e-mail notifications disabled.")
        return redirect("user_profile")


class ModalLoginView(BSModalLoginView):
    authentication_form = CustomAuthenticationForm
    template_name = "modal_form.html"
    success_message = "Success: You were successfully logged in."
    extra_context = {"success_url": reverse_lazy("login")}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {"form_title": "User Authentication", "submit_button_text": "Login"}
        )
        return context


class ModalLoginRequiredMixin(AccessMixin):
    """Verify that the current user is authenticated."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseRedirect(reverse("loginrequiredmessage"))
        else:
            return super().dispatch(request, *args, **kwargs)


class ModalLoginRequiredMessage(TemplateView):
    template_name = "modal_message.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "modal_title": "Authentication required",
                "modal_message": "You are not allowed to access this. Please log in as the authorized user.",
            }
        )
        return context


class UserAutocompleteView(AutocompleteModelView):
    """Autocomplete view for User model, used in review dashboard filters."""

    model = User
    search_lookups = [
        "username__icontains",
        "first_name__icontains",
        "last_name__icontains",
    ]
    value_fields = ["id", "username"]
    ordering = ["username"]
    page_size = 15

    def hook_queryset(self, queryset):
        """Filter to only active users."""
        return queryset.filter(is_active=True)
