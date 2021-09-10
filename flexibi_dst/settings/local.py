from .settings import *

SITE_ID = 1

DEBUG = True

DATABASES['default'] = {
    'ENGINE': 'django.contrib.gis.db.backends.postgis',
    'NAME': os.environ.get('POSTGRES_DB'),
    'USER': os.environ.get('POSTGRES_USER'),
    'PASSWORD': os.environ.get('POSTGRES_PASSWORD'),
    'HOST': os.environ.get('POSTGRES_HOST'),
    'PORT': os.environ.get('POSTGRES_PORT'),
}

STATIC_ROOT = os.path.join(BASE_DIR, 'static_root')

CRISPY_FAIL_SILENTLY = False
