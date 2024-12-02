from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.generic import TemplateView


@method_decorator(xframe_options_exempt, name='dispatch')
class HomeView(TemplateView):
    template_name = 'home.html'


class AboutView(TemplateView):
    template_name = 'about.html'


class LearningView(TemplateView):
    template_name = 'learning.html'


class PrivacyPolicyView(TemplateView):
    template_name = 'privacy_policy.html'


from django.core.cache import cache
from django.views import View
import time


class CacheTestView(View):
    def get(self, request):
        cache_key = 'cache_test'
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


from django.http import HttpResponse


def set_session(request):
    request.session['test_key'] = 'test_value'
    return HttpResponse("Session value set")


def get_session(request):
    value = request.session.get('test_key', 'Not found')
    return HttpResponse(f"Session value: {value}")
