import os
import sys

from .settings import *

SITE_ID = 1

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "host.docker.internal"]

# Only install debug toolbar if not running tests
TESTING = 'test' in sys.argv

if not TESTING:
    INSTALLED_APPS.append("debug_toolbar")
    DEBUG_TOOLBAR_CONFIG = {
        "SHOW_TOOLBAR_CALLBACK": lambda request: True,
    }
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")

INTERNAL_IPS = ALLOWED_HOSTS

DATABASES["default"] = {
    "ENGINE": "django.contrib.gis.db.backends.postgis",
    "NAME": os.environ.get("POSTGRES_DB"),
    "USER": os.environ.get("POSTGRES_USER"),
    "PASSWORD": os.environ.get("POSTGRES_PASSWORD"),
    "HOST": os.environ.get("POSTGRES_HOST"),
    "PORT": os.environ.get("POSTGRES_PORT"),
}

CRISPY_FAIL_SILENTLY = False

# Development logging: emit our app logs to console
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        # Django core
        "django": {"handlers": ["console"], "level": "INFO"},
        # Our packages
        "utils.object_management": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
