from bootstrap_modal_forms.generic import BSModalLoginView
from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.urls import reverse_lazy
from django.views.generic import DeleteView, TemplateView

from .forms import CustomAuthenticationForm


class UserDeleteView(LoginRequiredMixin, DeleteView):
    model = User
    success_url = reverse_lazy('home')


class UserProfileView(LoginRequiredMixin, TemplateView):
    model = User
    template_name = 'user_profile.html'


class ModalLoginView(BSModalLoginView):
    authentication_form = CustomAuthenticationForm
    template_name = '../flexibi_dst/templates/modal_form.html'
    success_message = 'Success: You were successfully logged in.'
    extra_context = dict(success_url=reverse_lazy('login'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form_title': 'User Authentication',
            'submit_button_text': 'Login'
        })
        return context


class ModalLoginRequiredMixin(AccessMixin):
    """Verify that the current user is authenticated."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseRedirect(reverse('loginrequiredmessage'))
        else:
            return super().dispatch(request, *args, **kwargs)


class ModalLoginRequiredMessage(TemplateView):
    template_name = 'modal_message.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'modal_title': 'Authentication required',
            'modal_message': 'You are not allowed to access this. Please log in as the authorized user.'
        })
        return context
