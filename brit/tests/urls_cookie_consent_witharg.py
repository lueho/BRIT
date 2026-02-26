from django.http import HttpResponse
from django.urls import path


def _dummy_view(request, *args, **kwargs):
    return HttpResponse("ok")


urlpatterns = [
    path("accept/<str:varname>/", _dummy_view, name="cookie_consent_accept"),
    path("decline/<str:varname>/", _dummy_view, name="cookie_consent_decline"),
]
