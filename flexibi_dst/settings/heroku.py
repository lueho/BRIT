import dj_database_url
import django_heroku

from .settings import *

DEBUG = False

ALLOWED_HOSTS = ALLOWED_HOSTS.append('flexibi-dst.herokuapp.com')

DATABASE_URL = os.environ.get('HEROKU_POSTGRESQL_COPPER_URL')
DATABASES['default'] = dj_database_url.config(default=DATABASE_URL, conn_max_age=500, ssl_require=True)
DATABASES['default']['ENGINE'] = 'django.contrib.gis.db.backends.postgis'

DEBUG_PROPAGATE_EXCEPTIONS = True

django_heroku.settings(locals())
