from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = 'home.html'


class AboutView(TemplateView):
    template_name = 'about.html'


class LearningView(TemplateView):
    template_name = 'learning.html'


class PrivacyPolicyView(TemplateView):
    template_name = 'privacy_policy.html'
