from .local import *

# Whitenoise is not suitable for serving static files during tests.
# Fall back to Django's standard setting
STORAGES["staticfiles"] = {
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
}

COOKIE_CONSENT_ENABLED = False

MIDDLEWARE = [
    mw
    for mw in MIDDLEWARE
    if mw
    in (
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
        "maps.middleware.CacheMonitoringMiddleware",
    )
]

SILENCED_SYSTEM_CHECKS = ["debug_toolbar.W001"]

# Use DB-backed sessions for parallel test safety
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# # Change logging level to DEBUG for django-tomselect
# LOGGING = {
#     "version": 1,
#     "disable_existing_loggers": False,
#     "formatters": {
#         "verbose": {
#             "format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s"
#         },
#         "simple": {"format": "%(levelname)s %(message)s"},
#     },
#     "handlers": {
#         "console": {
#             "level": "DEBUG",
#             "class": "logging.StreamHandler",
#             "formatter": "simple",
#         },
#     },
#     "loggers": {
#         "django_tomselect": {
#             "handlers": ["console"],
#             "level": "DEBUG",
#         },
#     },
# }
