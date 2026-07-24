import os
import subprocess
import sys

from django.test import SimpleTestCase


class ProductionContentSecurityPolicyTests(SimpleTestCase):
    def test_report_only_policy_is_added_to_responses(self):
        environment = os.environ.copy()
        environment["DJANGO_SETTINGS_MODULE"] = "brit.settings.heroku"
        environment["SECRET_KEY"] = "test-secret-key"
        environment["AWS_STORAGE_BUCKET_NAME"] = "brit-test-assets"
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import django
django.setup()
import brit.settings.heroku as h
from django.http import HttpResponse
from django.middleware.csp import ContentSecurityPolicyMiddleware
from django.test import RequestFactory

middleware_path = "django.middleware.csp.ContentSecurityPolicyMiddleware"
assert middleware_path in h.MIDDLEWARE
middleware = ContentSecurityPolicyMiddleware(lambda request: HttpResponse("ok"))
response = middleware(RequestFactory().get("/"))
expected = (
    "default-src 'self'; "
    "style-src 'self' https://brit-test-assets.s3.amazonaws.com "
    "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
    "https://fonts.googleapis.com; "
    "script-src 'self' https://brit-test-assets.s3.amazonaws.com "
    "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
    "https://www.googletagmanager.com; "
    "font-src 'self' https://brit-test-assets.s3.amazonaws.com "
    "https://cdnjs.cloudflare.com https://fonts.gstatic.com; "
    "img-src 'self' https://brit-test-assets.s3.amazonaws.com data:; "
    "base-uri 'self'; "
    "frame-ancestors 'self'; "
    "object-src 'none'"
)
assert response.headers["Content-Security-Policy-Report-Only"] == expected
assert "Content-Security-Policy" not in response.headers
""",
            ],
            capture_output=True,
            check=False,
            env=environment,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
