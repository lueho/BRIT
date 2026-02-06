from celery import chord
from django.utils import timezone

from brit.celery import app

from .filters import SourceFilter
from .models import Source
from .utils import check_url


@app.task
def task_check_url(url):
    return check_url(url)


@app.task(name="check_source_url")
def check_source_url(pk):
    try:
        source = Source.objects.get(pk=pk)
    except Source.DoesNotExist:
        return None
    source.url_valid = check_url(source.url)
    source.url_checked = timezone.localdate()
    source.save()


@app.task()
def check_source_urls_callback(results):
    return f"Checked {len(results)} sources."


@app.task()
def check_source_urls(params):
    qs = SourceFilter(params, queryset=Source.objects.all()).qs
    signatures = []
    for _i, flyer in enumerate(qs):
        signatures.append(check_source_url.s(flyer.pk))
    callback = check_source_urls_callback.s()
    task_chord = chord(signatures)(callback)
    return task_chord
