from .local import *

# Whitenoise is not suitable for serving static files during tests.
# Fall back to Django's standard setting
STORAGES["staticfiles"] = {
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
}

COOKIE_CONSENT_ENABLED = False
