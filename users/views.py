from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, TemplateView
from bootstrap_modal_forms.generic import BSModalLoginView
from .forms import CustomAuthenticationForm


class UserRegistrationView(CreateView):
    model = User
    form_class = UserCreationForm
    template_name = 'register.html'
    success_url = reverse_lazy('login')


class UserDeleteView(LoginRequiredMixin, DeleteView):
    model = User
    success_url = reverse_lazy('home')


class UserProfileView(LoginRequiredMixin, TemplateView):
    model = User
    template_name = 'user_profile.html'


class ModalLoginView(BSModalLoginView):
    authentication_form = CustomAuthenticationForm
    template_name = 'modal_form.html'
    success_message = 'Success: You were successfully logged in.'
    extra_context = dict(success_url=reverse_lazy('login'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'User Authentication',
            'submit_button_text': 'Login'
        })
        return context
