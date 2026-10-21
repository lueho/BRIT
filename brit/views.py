import time
from pathlib import Path

from django.core.cache import cache
from django.http import FileResponse, HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.generic import TemplateView

from brit.featured import (
    BRIT_EU_ECN_FACTSHEETS,
    BRIT_EU_MAP_LINKS,
    ECN_BRIT_EU_URL,
    ECN_FACTSHEETS_URL,
    FEATURED_DESTINATIONS,
)
from utils.views import BreadcrumbContextMixin


@method_decorator(xframe_options_exempt, name="dispatch")
class HomeView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["featured_destinations"] = FEATURED_DESTINATIONS
        return context


class BritEUResultsView(BreadcrumbContextMixin, TemplateView):
    template_name = "brit_eu_results.html"
    breadcrumb_page_title = "BRIT-EU results"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["brit_eu_map_links"] = BRIT_EU_MAP_LINKS
        context["brit_eu_ecn_factsheets"] = BRIT_EU_ECN_FACTSHEETS
        context["ecn_brit_eu_url"] = ECN_BRIT_EU_URL
        context["ecn_factsheets_url"] = ECN_FACTSHEETS_URL
        context["brit_eu_feature"] = next(
            feature for feature in FEATURED_DESTINATIONS if feature["slug"] == "brit-eu"
        )
        return context


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


def health_check(request):
    """Returns a 200 OK response."""
    return HttpResponse(status=200)
