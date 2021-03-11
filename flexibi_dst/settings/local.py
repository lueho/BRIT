from .settings import *

BASE_DIR = BASE_DIR

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
