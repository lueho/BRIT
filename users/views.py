from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.views.generic import CreateView


class UserRegistrationView(CreateView):
    model = User
    form_class = UserCreationForm
    template_name = 'users/register.html'
