from django.http import HttpResponse
from django.urls import path


def _dummy_view(request, *args, **kwargs):
    return HttpResponse("ok")


urlpatterns = [
    path("accept/", _dummy_view, name="cookie_consent_accept"),
    path("decline/", _dummy_view, name="cookie_consent_decline"),
]
