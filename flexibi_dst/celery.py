import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "flexibi_dst.settings")
app = Celery("flexibi_dst")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
