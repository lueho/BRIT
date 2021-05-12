from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User


class CustomAuthenticationForm(AuthenticationForm):
    class Meta:
        model = User
        fields = ['username', 'password']
