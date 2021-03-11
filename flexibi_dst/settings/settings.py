import os
from pathlib import Path

import dj_database_url
import environ

env = environ.Env()
environ.Env.read_env()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY')
DEBUG = True
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS').split(',')

AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
AWS_URL = os.environ.get('AWS_URL')
AWS_DEFAULT_ACL = None
AWS_S3_REGION_NAME = 'eu-central-1'
AWS_S3_SIGNATURE_VERSION = 's3v4'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'storages',
    'fontawesome-free',
    'django.contrib.gis',
    'extra_views',
    'django_tables2',
    'rest_framework',
    'rest_framework_gis',
    'leaflet',
    'users.apps.UsersConfig',
    'bioresource_explorer.apps.BioresourceExplorerConfig',
    'flexibi_dst',
    'library',
    'material_manager',
    'scenario_builder',
    'scenario_evaluator',
    'layer_manager',
    'case_studies',
    'case_studies.flexibi_nantes',
    'case_studies.flexibi_hamburg',
    'crispy_forms',
    'bootstrap_modal_forms',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'flexibi_dst.urls'

TEMPLATE_DIRS = [
    os.path.join(BASE_DIR, 'templates'),
    os.path.join(BASE_DIR, 'users', 'templates'),
    os.path.join(BASE_DIR, 'scenario_builder', 'templates'),
    os.path.join(BASE_DIR, 'scenario_evaluator', 'templates'),
    os.path.join(BASE_DIR, 'bioresource_explorer', 'templates'),
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': TEMPLATE_DIRS,
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

DJANGO_TABLES2_TEMPLATE = "django_tables2/bootstrap4.html"

WSGI_APPLICATION = 'flexibi_dst.wsgi.application'

# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'flexibi_dst',
        'USER': 'flexibi_dst',
        'PASSWORD': 'flexibi',
        'HOST': 'db',
        'PORT': '5432',
    }
}

DATABASE_URL = os.environ.get('HEROKU_POSTGRESQL_COPPER_URL')
db_from_env = dj_database_url.config(default=DATABASE_URL, conn_max_age=500, ssl_require=True)
DATABASES['default'].update(db_from_env)
DATABASES['default']['ENGINE'] = 'django.contrib.gis.db.backends.postgis'

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

CRISPY_TEMPLATE_PACK = 'bootstrap4'
CRISPY_FAIL_SILENTLY = not DEBUG

LOGIN_REDIRECT_URL = 'home'
LOGIN_URL = 'login'

CELERY_BROKER_URL = os.environ.get("REDIS_URL")
CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL")

IMPORTED_CASE_STUDIES = [
    'flexibi_nantes',
]

# ADMINS = [('Phillipp Lüssenhop', 'phillipp.luessenhop@tuhh.de')]
# EMAIL_HOST = os.environ.get('EMAIL_HOST')
# EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
# EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
# EMAIL_PORT = 465
# EMAIL_USE_SSL = True
# DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL')
#
# LOGGING = {
#     'version': 1,
#     'disable_existing_loggers': True,
#     'formatters': {
#         'verbose': {
#             'format': '%(levelname)s [%(asctime)s] %(module)s %(message)s'
#         },
#     },
#     'handlers': {
#         # 'console': {
#         #     'level': 'DEBUG',
#         #     'class': 'logging.StreamHandler',
#         #     'formatter': 'simple'
#         # },
#         'file': {
#             'class': 'logging.handlers.RotatingFileHandler',
#             'formatter': 'verbose',
#             'filename': os.path.join(BASE_DIR, 'logs', 'main.log'),
#             'maxBytes': 1024000,
#             'backupCount': 3,
#         },
#         'mail_admins': {
#             'level': 'ERROR',
#             'class': 'django.utils.log.AdminEmailHandler'
#         }
#     },
#     'loggers': {
#         'django': {
#             'handlers': ['file', 'mail_admins'],
#             'propagate': True,
#             'level': 'WARNING',
#         },
#     }
# }

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.0/howto/static-files/

# STATIC_URL = '/static/'
# STATIC_URL = os.path.join(BASE_DIR, 'static/')
# STATIC_ROOT = os.path.join(BASE_DIR, 'static_root')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
# STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

STATIC_URL = AWS_URL + '/static/'
STATICFILES_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
MEDIA_URL = AWS_URL + '/media/'
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
