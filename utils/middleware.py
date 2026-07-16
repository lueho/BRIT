import re

from django.http import HttpResponseRedirect

from .models import Redirect

SHORT_CODE_PATH = re.compile(r"/(?P<short_code>[^/]{1,50})/?\Z")


class DynamicRedirectFallbackMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            response.status_code != 404
            or request.method not in {"GET", "HEAD"}
            or request.resolver_match is not None
        ):
            return response

        match = SHORT_CODE_PATH.fullmatch(request.path_info)
        if match is None:
            return response

        full_path = (
            Redirect.objects.filter(short_code=match["short_code"])
            .values_list("full_path", flat=True)
            .first()
        )
        if full_path is None:
            return response

        return HttpResponseRedirect(
            f"{request.scheme}://{request.get_host()}{full_path}"
        )
