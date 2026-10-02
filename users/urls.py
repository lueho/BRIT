from django.urls import include, path

from .views import (
    ModalLoginRequiredMessage,
    RegistrationView,
    ResendActivationView,
    UserAutocompleteView,
    UserDeleteView,
    UserProfileView,
)

urlpatterns = [
    # Shadow the package's register/resend views with versions that handle
    # SMTP delivery failures as form errors instead of crashing.
    path("register/", RegistrationView.as_view(), name="registration_register"),
    path(
        "activate/resend/",
        ResendActivationView.as_view(),
        name="registration_resend_activation",
    ),
    path("", include("registration.backends.default.urls")),
    path("profile/", UserProfileView.as_view(), name="user_profile"),
    path(
        "loginrequired/",
        ModalLoginRequiredMessage.as_view(),
        name="loginrequiredmessage",
    ),
    path("<int:pk>/delete/", UserDeleteView.as_view(), name="user_delete"),
    path("autocomplete/", UserAutocompleteView.as_view(), name="user-autocomplete"),
]
