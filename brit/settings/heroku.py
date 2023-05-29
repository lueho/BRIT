import dj_database_url
import django_heroku

from .settings import *

SITE_ID = 2

DEBUG = False

ALLOWED_HOSTS = ALLOWED_HOSTS.append('bri-tool.herokuapp.com')

SECURE_SSL_REDIRECTS = True

DATABASES['default'] = dj_database_url.config(default=os.environ.get('DATABASE_URL'), conn_max_age=500,
                                              ssl_require=True)
DATABASES['default']['ENGINE'] = 'django.contrib.gis.db.backends.postgis'

DEBUG_PROPAGATE_EXCEPTIONS = True
CRISPY_FAIL_SILENTLY = True

django_heroku.settings(locals(), databases=False)
