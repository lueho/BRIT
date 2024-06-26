import os
import ssl
from pathlib import Path

from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', default=get_random_secret_key())

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.sites',
    'registration',
    'dal',
    'dal_select2',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'crispy_bootstrap4',
    'fontawesomefree',
    'django.contrib.gis',
    'extra_views',
    'rest_framework',
    'rest_framework.authtoken',
    'rest_framework_gis',
    'leaflet',
    'cookie_consent',
    'ambient_toolbox',
    'users.apps.UsersConfig',
    'utils.apps.UtilsConfig',
    'maps.apps.MapsConfig',
    'brit.apps.BRITConfig',
    'distributions.apps.DistributionsConfig',
    'bibliography.apps.BibliographyConfig',
    'materials.apps.MaterialsConfig',
    'inventories.apps.InventoriesConfig',
    'sources.apps.SourcesConfig',
    'layer_manager.apps.LayerManagerConfig',
    'case_studies.flexibi_nantes.apps.CaseStudyNantesConfig',
    'case_studies.flexibi_hamburg.apps.FlexibiHamburgConfig',
    'case_studies.soilcom.apps.SoilcomConfig',
    'case_studies.closecycle.apps.ClosecycleConfig',
    'interfaces.simucf.apps.SimucfConfig',
    'utils.file_export.apps.FileExportConfig',
    'utils.properties.apps.PropertiesConfig',
    'django.forms',
    'django_filters',
    'crispy_forms',
    'bootstrap_modal_forms',
    'debug_toolbar'
]

MIDDLEWARE = [
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'ambient_toolbox.middleware.current_user.CurrentUserMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'brit.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'users', 'templates'),
            os.path.join(BASE_DIR, 'brit', 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'brit.context_processors.google_analytics'
            ],
        },
    },
]

TEMPLATE_CONTEXT_PROCESSORS = [
    'django.template.context_processors.request'
]

WSGI_APPLICATION = 'brit.wsgi.application'

DATABASES = {}

# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

STATIC_URL = '/static/'

MEDIA_URL = '/media/'
# DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
AWS_DEFAULT_REGION = os.environ.get('AWS_DEFAULT_REGION')
AWS_S3_SIGNATURE_VERSION = 's3v4'

# Settings for django-registration-redux
ACCOUNT_ACTIVATION_DAYS = 2
REGISTRATION_AUTO_LOGIN = True
REGISTRATION_DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL')

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_FILTER_BACKENDS': ('django_filters.rest_framework.DjangoFilterBackend',)
}

LEAFLET_CONFIG = {
    'DEFAULT_CENTER': (50.08178260774763, 14.432086500224534),
    'DEFAULT_ZOOM': 5,
    'RESET_VIEW': False,
    'NO_GLOBALS': False,
    'MIN_ZOOM': 4,
    'MAX_ZOOM': 15,
    'PLUGINS': {
        'draw': {
            'css': 'lib/leaflet-draw/leaflet.draw.min.css',
            'js': 'lib/leaflet-draw/leaflet.draw.min.js',
            'auto-include': True
        },
        'forms': {'auto-include': True},
        'spin': {
            'js': ['lib/spin/spin.min.js', 'lib/leaflet-spin/leaflet.spin.min.js'],
            'auto-include': True
        }
    }
}

LOGIN_REDIRECT_URL = 'home'
LOGIN_URL = '/users/login/'

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

CELERY_BROKER_URL = os.environ.get("REDIS_URL")
CELERY_BROKER_USE_SSL = {
    'ssl_cert_reqs': ssl.CERT_NONE
}
CELERY_REDIS_BACKEND_USE_SSL = {
    'ssl_cert_reqs': ssl.CERT_NONE
}
CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL")

CRISPY_TEMPLATE_PACK = 'bootstrap4'

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST')
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
EMAIL_PORT = os.environ.get('EMAIL_PORT')
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL')

ADMINS = [(os.environ.get('ADMIN_NAME'), os.environ.get('ADMIN_EMAIL'))]

GOOGLE_ANALYTICS_KEY = os.environ.get("GOOGLE_ANALYTICS_KEY")

COOKIE_CONSENT_NAME = "cookie_consent"
