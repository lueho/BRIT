from .settings import *

SITE_ID = 1

DEBUG = True

DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': lambda request: DEBUG
}

INTERNAL_IPS = [
    '127.0.0.1',
]

DATABASES['default'] = {
    'ENGINE': 'django.contrib.gis.db.backends.postgis',
    'NAME': os.environ.get('POSTGRES_DB'),
    'USER': os.environ.get('POSTGRES_USER'),
    'PASSWORD': os.environ.get('POSTGRES_PASSWORD'),
    'HOST': os.environ.get('POSTGRES_HOST'),
    'PORT': os.environ.get('POSTGRES_PORT'),
}

STATIC_ROOT = os.path.join(BASE_DIR, 'static_root')
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY'),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET'),
}

CRISPY_FAIL_SILENTLY = False


# Override email backend for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Adjust logging for development
LOGGING['loggers']['django']['level'] = 'DEBUG'
LOGGING['loggers']['brit']['level'] = 'DEBUG'

# Remove 'mail_admins' handler from all loggers
for logger in LOGGING['loggers'].values():
    if 'mail_admins' in logger['handlers']:
        logger['handlers'].remove('mail_admins')

# Remove the 'mail_admins' handler entirely
LOGGING['handlers'].pop('mail_admins', None)
