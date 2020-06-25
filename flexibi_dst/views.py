from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.shortcuts import render
from django.views.generic import TemplateView


def home(request):
    return render(request, 'base.html', {})


class ScriptTestView(TemplateView):
    template_name = 'script_test.html'


class DstLoginView(LoginView):
    template_name = 'login.html'
    form_class = AuthenticationForm


class HomeView(TemplateView):
    template_name = 'home.html'
