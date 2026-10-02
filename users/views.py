import logging
import smtplib

from django.contrib.auth.mixins import AccessMixin, LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib.sites.shortcuts import get_current_site
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import DeleteView, TemplateView
from django_tomselect.autocompletes import AutocompleteModelView
from registration.backends.default.views import (
    RegistrationView as BaseRegistrationView,
)
from registration.backends.default.views import (
    ResendActivationView as BaseResendActivationView,
)

from utils.modal import BSModalLoginView

from .forms import CustomAuthenticationForm

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
        return redirect(self.get_success_url(new_user))


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


class UserDeleteView(LoginRequiredMixin, DeleteView):
    model = User
    template_name = "modal_user_delete.html"
    success_message = "Successfully deleted."
    success_url = reverse_lazy("home")


class UserProfileView(LoginRequiredMixin, TemplateView):
    model = User
    template_name = "user_profile.html"


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
