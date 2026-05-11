from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.forms import EmailField
from turnstile.fields import TurnstileField


class UserRegistrationForm(UserCreationForm):
    email = EmailField(max_length=200)
    turnstile = TurnstileField()

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class CustomAuthenticationForm(AuthenticationForm):
    class Meta:
        model = User
        fields = ["username", "password"]
