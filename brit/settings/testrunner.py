import os
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .settings import *

# Keep all historical migrations and initialization helpers aligned on one owner.
DEFAULT_OBJECT_OWNER_USERNAME = "admin"
DEFAULT_OWNER_USERNAME = "admin"
if not os.environ.get("ADMIN_USERNAME"):
    os.environ["ADMIN_USERNAME"] = "admin"

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
    "ATOMIC_REQUESTS": False,
    "AUTOCOMMIT": True,
    "CONN_MAX_AGE": 0,
    "CONN_HEALTH_CHECKS": False,
    "OPTIONS": {},
    "TIME_ZONE": None,
    "TEST": {
        "NAME": "test_brit_test_db",
    },
}


def _test_redis_database_url(redis_url: str, database: int) -> str:
    parsed_redis_url = urlparse(redis_url)
    query = dict(parse_qsl(parsed_redis_url.query, keep_blank_values=True))
    if parsed_redis_url.scheme == "rediss":
        query.setdefault("ssl_cert_reqs", "none")
    return urlunparse(
        parsed_redis_url._replace(path=f"/{database}", query=urlencode(query))
    )


_test_redis_url = os.environ.get("TEST_REDIS_URL")
if not _test_redis_url:
    _test_redis_url = _test_redis_database_url(
        os.environ.get("REDIS_URL", "redis://redis:6379/0"), 15
    )

CELERY_BROKER_URL = _test_redis_url
CELERY_RESULT_BACKEND = _test_redis_url

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_USE_SSL = None
CELERY_REDIS_BACKEND_USE_SSL = None

_test_cache_redis_url = _test_redis_database_url(_test_redis_url, 14)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "brit-test-default",
    },
    "geojson": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": _test_cache_redis_url,
        "TIMEOUT": 86400,
        "KEY_PREFIX": "geojson",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            "IGNORE_EXCEPTIONS": False,
        },
    },
}

AUTO_ENQUEUE_URL_CHECKS = False

# Use local filesystem storage in tests to avoid S3 dependencies.
MEDIA_ROOT = Path("/tmp/brit-test-media")
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
STORAGES["default"] = {
    "BACKEND": "django.core.files.storage.FileSystemStorage",
    "OPTIONS": {"location": str(MEDIA_ROOT)},
}
STORAGES["staticfiles"] = {
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
}
MEDIA_URL = "/media/"
AWS_STORAGE_BUCKET_NAME = "tests"
AWS_S3_CUSTOM_DOMAIN = "tests.invalid"
FILE_EXPORT_USE_LOCAL_STORAGE = True

COOKIE_CONSENT_ENABLED = False

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "maps.middleware.CacheMonitoringMiddleware",
    "django_tomselect.middleware.TomSelectMiddleware",
]

SILENCED_SYSTEM_CHECKS = ["debug_toolbar.W001"]

# Use local email settings in tests and prevent admin-email logging.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
ADMINS = ["tests@example.com"]
MANAGERS = ["tests@example.com"]

# Use DB-backed sessions for parallel test safety
SESSION_ENGINE = "django.contrib.sessions.backends.db"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(levelname)s %(message)s"},
    },
    "handlers": {
        "console": {
            "level": "WARNING",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django_tomselect": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "sources.waste_collection.apps": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

CRISPY_FAIL_SILENTLY = False

TEST_RUNNER = "utils.tests.testrunner.SerialAwareTestRunner"

# Use canonical waste_collection IDs in tests to avoid repeated dynamic lookup failures
# in signal handlers before initial data is fully populated.
WASTE_COLLECTION_SPECIFIC_WASTE_PROPERTY_ID = 1
WASTE_COLLECTION_TOTAL_WASTE_PROPERTY_ID = 9
WASTE_COLLECTION_SPECIFIC_WASTE_UNIT_ID = 2
WASTE_COLLECTION_TOTAL_WASTE_UNIT_ID = 8
WASTE_COLLECTION_POPULATION_ATTRIBUTE_ID = 3
