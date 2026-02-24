from celery import chord
from django.utils import timezone

from bibliography.utils import check_url, find_wayback_snapshot_for_year
from brit.celery import app

from .filters import WasteFlyerFilter
from .models import WasteFlyer, WasteStream


@app.task(name="check_wasteflyer_url", trail=True)
def check_wasteflyer_url(pk):
    flyer = WasteFlyer.objects.filter(pk=pk).first()
    if flyer is None:
        return False

    url_valid = check_url(flyer.url)

    if flyer.url and "web.archive.org" in flyer.url:
        flyer.url_valid = url_valid
        flyer.url_checked = timezone.localdate()
        flyer.save()
        return True

    collection_year = (
        flyer.collections.exclude(valid_from__isnull=True)
        .order_by("-valid_from")
        .values_list("valid_from__year", flat=True)
        .first()
    )
    if collection_year:
        wayback_url = find_wayback_snapshot_for_year(flyer.url, collection_year)
        if wayback_url:
            flyer.url = wayback_url
            url_valid = True

    flyer.url_valid = url_valid
    flyer.url_checked = timezone.localdate()
    flyer.save()
    return True


@app.task(name="callback")
def check_wasteflyer_urls_callback(results):
    return f"Checked {len(results)} flyers."


@app.task(bind=True, trail=True, name="scheduler")
def check_wasteflyer_urls(self, params):
    self.myname = "scheduler"
    qs = WasteFlyerFilter(params, queryset=WasteFlyer.objects.all()).qs
    signatures = []
    for flyer in qs:
        signatures.append(check_wasteflyer_url.s(flyer.pk))
    callback = check_wasteflyer_urls_callback.s()
    task_chord = chord(signatures)(callback)
    return task_chord


@app.task(name="cleanup_orphaned_waste_flyers", trail=True)
def cleanup_orphaned_waste_flyers():
    """Delete WasteFlyers that are no longer referenced by any collections or properties."""

    return WasteFlyer.objects.filter(
        collections__isnull=True,
        collection__isnull=True,
        collectionpropertyvalue__isnull=True,
        aggregatedcollectionpropertyvalue__isnull=True,
    ).delete()


@app.task(name="cleanup_orphaned_waste_streams", trail=True)
def cleanup_orphaned_waste_streams():
    """Delete WasteStreams that are no longer referenced by any collections."""

    return WasteStream.objects.filter(collections__isnull=True).delete()
