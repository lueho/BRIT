import dj_database_url

from .settings import *

SITE_ID = 2

DEBUG = False

SECRET_KEY = os.environ.get('SECRET_KEY')
ALLOWED_HOSTS = [host for host in os.environ.get('ALLOWED_HOSTS', '').split(',')]

# Security settings
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Add middleware for emails with logs about unhandled exceptions
# This middleware is added only in production because it triggers too many logging events during testing in development.
MIDDLEWARE.append('brit.middleware.ExceptionLoggingMiddleware')

# Database configuration
DATABASES['default'] = dj_database_url.config(conn_max_age=600, ssl_require=True)
DATABASES['default']['ENGINE'] = 'django.contrib.gis.db.backends.postgis'

STATICFILES_LOCATION = "static"
STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/{STATICFILES_LOCATION}/"

MEDIAFILES_LOCATION = "media"
MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/{MEDIAFILES_LOCATION}/"

STORAGES = {
    'default': {
        'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
        'OPTIONS': {
            'bucket_name': AWS_STORAGE_BUCKET_NAME,
            'custom_domain': AWS_S3_CUSTOM_DOMAIN,
            'location': MEDIAFILES_LOCATION,
        },
    },
    'staticfiles': {
        'BACKEND': "brit.storages.StaticStorage",
        'OPTIONS': {
            'bucket_name': AWS_STORAGE_BUCKET_NAME,
            'custom_domain': AWS_S3_CUSTOM_DOMAIN,
            'location': STATICFILES_LOCATION,
        },
    },
}

# Logging settings
# In production all logs of unhandled exceptions are mailed to the admins.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': True,
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'mail_admins'],
            'level': 'WARNING',
            'propagate': False,
        },
        'brit': {
            'handlers': ['console', 'mail_admins'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

DEBUG_PROPAGATE_EXCEPTIONS = True
CRISPY_FAIL_SILENTLY = True
