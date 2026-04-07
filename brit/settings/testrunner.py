from urllib.parse import urlparse, urlunparse

from .settings import *

SITE_ID = 1

DEBUG = False

TESTING = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

INTERNAL_IPS = ["127.0.0.1"]

DATABASES["default"] = {
    "ENGINE": "django.contrib.gis.db.backends.postgis",
    "NAME": "test_brit_db",
    "USER": os.environ.get("POSTGRES_USER", "postgres"),
    "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
    "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
    "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    "TEST": {
        "NAME": "test_brit_test_db",
    },
}

_test_redis_url = os.environ.get("TEST_REDIS_URL")
if _test_redis_url:
    CELERY_BROKER_URL = _test_redis_url
    CELERY_RESULT_BACKEND = _test_redis_url
else:
    _parsed_redis_url = urlparse(os.environ.get("REDIS_URL", "rediss://redis:6379/0"))
    _test_redis_url = urlunparse(_parsed_redis_url._replace(path="/15"))
    CELERY_BROKER_URL = _test_redis_url
    CELERY_RESULT_BACKEND = _test_redis_url

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

AUTO_ENQUEUE_URL_CHECKS = False

# Whitenoise is not suitable for serving static files during tests.
# Fall back to Django's standard setting
STORAGES["staticfiles"] = {
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
}

COOKIE_CONSENT_ENABLED = False

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "maps.middleware.CacheMonitoringMiddleware",
    "django_tomselect.middleware.TomSelectMiddleware",
]

SILENCED_SYSTEM_CHECKS = ["debug_toolbar.W001"]

# Use console email backend for tests to avoid external dependencies
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Use DB-backed sessions for parallel test safety
SESSION_ENGINE = "django.contrib.sessions.backends.db"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s"
        },
        "simple": {"format": "%(levelname)s %(message)s"},
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        "django_tomselect": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": True,
        },
    },
}

CRISPY_FAIL_SILENTLY = False

TEST_RUNNER = "utils.tests.testrunner.SerialAwareTestRunner"

# Use canonical soilcom IDs in tests to avoid repeated dynamic lookup failures
# in signal handlers before initial data is fully populated.
SOILCOM_SPECIFIC_WASTE_PROPERTY_ID = 1
SOILCOM_TOTAL_WASTE_PROPERTY_ID = 9
SOILCOM_SPECIFIC_WASTE_UNIT_ID = 2
SOILCOM_TOTAL_WASTE_UNIT_ID = 8
SOILCOM_POPULATION_ATTRIBUTE_ID = 3
