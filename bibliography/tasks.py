from datetime import timedelta

from celery import chord
from django.db.models import Q
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


@app.task(name="check_stale_source_urls")
def check_stale_source_urls(stale_days=30):
    """Re-check source URLs that were never checked or are stale (#391).

    Covers the gap the post-save signal leaves: imported or old rows with
    ``url_checked`` unset, and previously-validated URLs that may have rotted.
    """
    stale_before = timezone.localdate() - timedelta(days=stale_days)
    rows = (
        Source.objects.exclude(url__isnull=True)
        .exclude(url="")
        .filter(Q(url_checked__isnull=True) | Q(url_checked__lt=stale_before))
        .values_list("pk", "type")
    )
    # Waste flyers need their own task, which also recovers broken URLs from
    # Wayback snapshots. Dispatch it by name: bibliography must not import
    # from sources.
    signatures = [
        app.signature("check_wasteflyer_url", args=(pk,))
        if source_type == "waste_flyer"
        else check_source_url.s(pk)
        for pk, source_type in rows
    ]
    callback = check_source_urls_callback.s()
    return chord(signatures)(callback)
