import os
from pathlib import Path

from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', default=get_random_secret_key())

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.sites',
    'registration',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'cloudinary_storage',
    'cloudinary',
    'fontawesomefree',
    'django.contrib.gis',
    'extra_views',
    'django_tables2',
    'rest_framework',
    'rest_framework_gis',
    'leaflet',
    'cookie_consent',
    'users.apps.UsersConfig',
    'maps.apps.MapsConfig',
    'flexibi_dst.apps.FlexibiDstConfig',
    'distributions.apps.DistributionsConfig',
    'bibliography.apps.BibliographyConfig',
    'material_manager.apps.MaterialManagerConfig',
    'scenario_builder.apps.ScenarioBuilderConfig',
    'scenario_evaluator.apps.ScenarioEvaluationConfig',
    'layer_manager.apps.LayerManagerConfig',
    'case_studies.flexibi_nantes.apps.CaseStudyNantesConfig',
    'case_studies.flexibi_hamburg.apps.FlexibiHamburgConfig',
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
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'flexibi_dst.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'users', 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

TEMPLATE_CONTEXT_PROCESSORS = [
    'django.template.context_processors.request'
]

WSGI_APPLICATION = 'flexibi_dst.wsgi.application'

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
STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'static'),
)

MEDIA_URL = '/media/'
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# Settings for django-registration-redux
ACCOUNT_ACTIVATION_DAYS = 2
REGISTRATION_AUTO_LOGIN = True
REGISTRATION_DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL')

LEAFLET_CONFIG = {
    'DEFAULT_CENTER': (48.917908, 6.921543),
    'DEFAULT_ZOOM': 5,
    'RESET_VIEW': False,
    'NO_GLOBALS': False,
    'MIN_ZOOM': 5,
    'MAX_ZOOM': 18,
    'PLUGINS': {'draw': {'css': 'draw/leaflet.draw.css',
                         'js': 'draw/leaflet.draw.js',
                         'auto-include': True
                         },
                'forms': {'auto-include': True},

                }
}

LOGIN_REDIRECT_URL = 'home'
LOGIN_URL = 'users/login'

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

CELERY_BROKER_URL = os.environ.get("REDIS_URL")
CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL")

CRISPY_TEMPLATE_PACK = 'bootstrap4'
DJANGO_TABLES2_TEMPLATE = "django_tables2/bootstrap4.html"

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST')
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
EMAIL_PORT = os.environ.get('EMAIL_PORT')
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL')
