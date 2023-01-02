from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = 'home.html'


class ContributorsView(TemplateView):
    template_name = 'contributors.html'


class PrivacyPolicyView(TemplateView):
    template_name = 'privacy_policy.html'
