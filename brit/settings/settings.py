import os
import ssl
from pathlib import Path

from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", default=get_random_secret_key())

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Use custom test runner that loads initial data
TEST_RUNNER = "utils.tests.testrunner.SerialAwareTestRunner"

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    "django.contrib.sites",
    "registration",
    "django_tomselect",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "crispy_forms",
    "bootstrap_modal_forms",
    "crispy_bootstrap5",
    "django.contrib.gis",
    "extra_views",
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_gis",
    "leaflet",
    "cookie_consent",
    "ambient_toolbox",
    "users.apps.UsersConfig",
    "utils.apps.UtilsConfig",
    "maps.apps.MapsConfig",
    "brit.apps.BRITConfig",
    "distributions.apps.DistributionsConfig",
    "bibliography.apps.BibliographyConfig",
    "materials.apps.MaterialsConfig",
    "processes",
    "inventories.apps.InventoriesConfig",
    "sources.apps.SourcesConfig",
    "layer_manager.apps.LayerManagerConfig",
    "case_studies.flexibi_nantes.apps.CaseStudyNantesConfig",
    "case_studies.flexibi_hamburg.apps.FlexibiHamburgConfig",
    "case_studies.soilcom.apps.SoilcomConfig",
    "case_studies.closecycle.apps.ClosecycleConfig",
    "interfaces.simucf.apps.SimucfConfig",
    "utils.file_export.apps.FileExportConfig",
    "utils.properties.apps.PropertiesConfig",
    "utils.object_management.apps.ObjectManagementConfig",
    "django.forms",
    "django_filters",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "ambient_toolbox.middleware.current_user.CurrentUserMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "maps.middleware.CacheMonitoringMiddleware",
    "django_tomselect.middleware.TomSelectMiddleware",
]

ROOT_URLCONF = "brit.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(BASE_DIR, "users", "templates"),
            os.path.join(BASE_DIR, "brit", "templates"),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "brit.context_processors.google_analytics",
                "django_tomselect.context_processors.tomselect",
            ],
        },
    },
]

WSGI_APPLICATION = "brit.wsgi.application"

# Database settings
DATABASES = {}  # Specified in local.py for development and heroku.py for production
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Admin
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")

# Default object owner
DEFAULT_OBJECT_OWNER_USERNAME = os.environ.get("DEFAULT_OBJECT_OWNER_USERNAME")

# Django registration settings
ACCOUNT_ACTIVATION_DAYS = 2
REGISTRATION_AUTO_LOGIN = True
REGISTRATION_DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL")

# Login settings
LOGIN_REDIRECT_URL = "home"
LOGIN_URL = "/users/login/"

# Redis and Caching
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            "IGNORE_EXCEPTIONS": True,
            "CONNECTION_POOL_KWARGS": {"ssl_cert_reqs": None},
        },
    },
    "geojson": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL"),
        "TIMEOUT": 86400,  # 24 hours
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            "IGNORE_EXCEPTIONS": True,
            "CONNECTION_POOL_KWARGS": {"ssl_cert_reqs": None},
            "KEY_PREFIX": "geojson",  # Differentiate keys for the geojson cache
        },
    },
}

# Use the geojson cache for all geojson-related operations
GEOJSON_CACHE = "geojson"


SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# AWS S3 settings
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME")
AWS_DEFAULT_REGION = os.environ.get("AWS_DEFAULT_REGION")
AWS_S3_SIGNATURE_VERSION = "s3v4"
AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
AWS_S3_USE_SSL = True
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=2592000"}


MEDIAFILES_LOCATION = "media"
MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/{MEDIAFILES_LOCATION}/"

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "custom_domain": AWS_S3_CUSTOM_DOMAIN,
            "location": MEDIAFILES_LOCATION,
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

STATIC_URL = "/static/"

# REST settings
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    # Throttle rates for rate limiting (applied per-view via throttle_classes)
    "DEFAULT_THROTTLE_RATES": {
        "anon": "10/minute",
        "user": "60/minute",
    },
}


# Email settings
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST")
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
EMAIL_PORT = os.environ.get("EMAIL_PORT")
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL")
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

ADMINS = [(os.environ.get("ADMIN_NAME"), os.environ.get("ADMIN_EMAIL"))]

# Additional packages settings
GOOGLE_ANALYTICS_KEY = os.environ.get("GOOGLE_ANALYTICS_KEY")

CRISPY_ALLOWED_TEMPLATE_PACKS = ("bootstrap5",)
CRISPY_TEMPLATE_PACK = "bootstrap5"

COOKIE_CONSENT_NAME = "cookie_consent"

CELERY_BROKER_URL = os.environ.get("REDIS_URL")
CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL")
CELERY_BROKER_USE_SSL = {"ssl_cert_reqs": ssl.CERT_NONE}
CELERY_REDIS_BACKEND_USE_SSL = {"ssl_cert_reqs": ssl.CERT_NONE}

GEO_BORDER_TOLERANCE = 0.005  # Tolerance for border detection in degrees for EPSG 4326

LEAFLET_CONFIG = {
    "DEFAULT_CENTER": (50.08178260774763, 14.432086500224534),
    "DEFAULT_ZOOM": 5,
    "RESET_VIEW": False,
    "NO_GLOBALS": False,
    "MIN_ZOOM": 4,
    "MAX_ZOOM": 22,
    "PLUGINS": {
        "draw": {
            "css": "lib/leaflet-draw/leaflet.draw.min.css",
            "js": "lib/leaflet-draw/leaflet.draw.min.js",
            "auto-include": True,
        },
        "forms": {"auto-include": True},
        "spin": {
            "js": ["lib/spin/spin.min.js", "lib/leaflet-spin/leaflet.spin.min.js"],
            "auto-include": True,
        },
    },
}

TOMSELECT = {
    "DEFAULT_CSS_FRAMEWORK": "bootstrap5",
    "DEFAULT_CONFIG": {
        "highlight": True,
        "placeholder": "------",
        "open_on_focus": True,
        "preload": "focus",
    },
    "PLUGINS": {
        "clear_button": {"title": "Clear Selection", "class_name": "clear-button"},
    },
    "ENABLE_LOGGING": False,
}

# Review Dashboard Configuration
# Priority models always shown in review dashboard filters if user has permissions
# (even if no items currently in review). This helps moderators quickly access
# the most commonly reviewed content types.
REVIEW_DASHBOARD_PRIORITY_MODELS = [
    "soilcom.Collection",
    "soilcom.CollectionPropertyValue",
    "soilcom.AggregatedCollectionPropertyValue",
]

# Number of items to display per page in review dashboard
REVIEW_DASHBOARD_PAGE_SIZE = 20
