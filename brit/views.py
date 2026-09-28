import time
from pathlib import Path

from django.core.cache import cache
from django.http import FileResponse, HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.generic import TemplateView

from utils.views import BreadcrumbContextMixin


@method_decorator(xframe_options_exempt, name="dispatch")
class HomeView(TemplateView):
    template_name = "home.html"


class AboutView(BreadcrumbContextMixin, TemplateView):
    template_name = "about.html"
    breadcrumb_page_title = "About"


class LearningView(BreadcrumbContextMixin, TemplateView):
    template_name = "learning.html"
    breadcrumb_page_title = "Learning"


class RAnalysisView(BreadcrumbContextMixin, TemplateView):
    template_name = "r_analysis.html"
    breadcrumb_page_title = "R Analysis"


def download_r_analysis_client(request):
    client = Path(__file__).resolve().parent / "static/rscripts/BRIT_Datenanalyse.R"
    return FileResponse(
        client.open("rb"),
        as_attachment=True,
        filename="BRIT_Datenanalyse.R",
        content_type="text/plain; charset=utf-8",
    )


class PrivacyPolicyView(BreadcrumbContextMixin, TemplateView):
    template_name = "privacy_policy.html"
    breadcrumb_page_title = "Privacy Policy"


class CacheTestView(View):
    def get(self, request):
        cache_key = "cache_test"
        cache_time = 30  # Cache for 30 seconds

        # Try to get the value from the cache
        cached_value = cache.get(cache_key)

        if cached_value is None:
            # If not in cache, perform a "heavy" operation
            time.sleep(2)  # Simulate a time-consuming operation
            cached_value = f"This value was calculated at {time.time()}"

            # Store the result in the cache
            cache.set(cache_key, cached_value, cache_time)

            return HttpResponse(f"Calculated value: {cached_value}")
        else:
            return HttpResponse(f"Cached value: {cached_value}")


def set_session(request):
    request.session["test_key"] = "test_value"
    return HttpResponse("Session value set")


def get_session(request):
    value = request.session.get("test_key", "Not found")
    return HttpResponse(f"Session value: {value}")


def health_check(request):
    """Returns a 200 OK response."""
    return HttpResponse(status=200)
