import os
import re
import subprocess
import sys
from pathlib import Path

from django.conf import settings
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
assert "django.template.context_processors.csp" in h.TEMPLATES[0]["OPTIONS"]["context_processors"]
middleware = ContentSecurityPolicyMiddleware(lambda request: HttpResponse("ok"))
request = RequestFactory().get("/")
middleware.process_request(request)
nonce = str(request._csp_nonce)
response = middleware.process_response(request, HttpResponse("ok"))
expected = (
    "default-src 'self'; "
    "style-src 'self' https://brit-test-assets.s3.amazonaws.com "
    "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
    "https://fonts.googleapis.com; "
    "script-src 'self' https://brit-test-assets.s3.amazonaws.com "
    "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
    "https://www.googletagmanager.com https://static.cloudflareinsights.com "
    f"'nonce-{nonce}'; "
    "connect-src 'self' https://*.google-analytics.com "
    "https://analytics.google.com https://stats.g.doubleclick.net; "
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

    def test_csp_context_processor_is_only_enabled_in_production(self):
        self.assertNotIn(
            "django.template.context_processors.csp",
            settings.TEMPLATES[0]["OPTIONS"]["context_processors"],
        )

    def test_first_party_inline_scripts_use_the_csp_nonce(self):
        script_tags = re.compile(r"<script(?P<attributes>[^>]*)>", re.IGNORECASE)
        template_paths = Path(settings.BASE_DIR).glob("**/templates/**/*.html")

        for template_path in template_paths:
            for script_tag in script_tags.finditer(template_path.read_text()):
                attributes = script_tag.group("attributes")
                if not re.search(r"\bsrc\s*=", attributes, re.IGNORECASE):
                    with self.subTest(template_path=template_path):
                        self.assertIn('nonce="{{ csp_nonce }}"', attributes)
