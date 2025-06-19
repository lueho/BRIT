from .local import *

# Whitenoise is not suitable for serving static files during tests.
# Fall back to Django's standard setting
STORAGES["staticfiles"] = {
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
}

COOKIE_CONSENT_ENABLED = False

APPS_REMOVED_FOR_TESTING = ("debug_toolbar",)
INSTALLED_APPS = [app for app in INSTALLED_APPS if app not in APPS_REMOVED_FOR_TESTING]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "maps.middleware.CacheMonitoringMiddleware",
]

SILENCED_SYSTEM_CHECKS = ["debug_toolbar.W001"]

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
