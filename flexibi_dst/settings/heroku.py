import django_heroku

from .settings import *

DEBUG = False
ALLOWED_HOSTS = ALLOWED_HOSTS.append('flexibi-dst.herokuapp.com')
DEBUG_PROPAGATE_EXCEPTIONS = True
django_heroku.settings(locals())
