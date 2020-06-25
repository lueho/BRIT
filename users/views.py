from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, TemplateView


class UserRegistrationView(CreateView):
    model = User
    form_class = UserCreationForm
    template_name = 'users/register.html'
    success_url = reverse_lazy('login')


class UserDeleteView(LoginRequiredMixin, DeleteView):
    model = User
    success_url = reverse_lazy('home')


class UserProfileView(LoginRequiredMixin, TemplateView):
    model = User
    template_name = 'users/user_profile.html'
