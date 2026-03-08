from types import SimpleNamespace
import sys

from celery import chord
from django.contrib.auth import get_user_model
from django.utils import timezone

from bibliography.utils import check_url, find_wayback_snapshot_for_year
from brit.celery import app

from sources.waste_collection.filters import WasteFlyerFilter
from sources.waste_collection.models import WasteFlyer


def _compat_symbol(name, default):
    legacy_module = sys.modules.get("case_studies.soilcom.tasks")
    if legacy_module is not None and hasattr(legacy_module, name):
        return getattr(legacy_module, name)
    return default


@app.task(name="check_wasteflyer_url", trail=True)
def check_wasteflyer_url(pk):
    flyer = WasteFlyer.objects.filter(pk=pk).first()
    if flyer is None:
        return False

    compat_check_url = _compat_symbol("check_url", check_url)
    compat_find_wayback_snapshot_for_year = _compat_symbol(
        "find_wayback_snapshot_for_year",
        find_wayback_snapshot_for_year,
    )

    url_valid = compat_check_url(flyer.url)

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
        wayback_url = compat_find_wayback_snapshot_for_year(flyer.url, collection_year)
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
def check_wasteflyer_urls(self, params, user_id=None):
    self.myname = "scheduler"
    user = None
    if user_id:
        user = get_user_model().objects.filter(pk=user_id).first()
    request = SimpleNamespace(user=user)

    qs = WasteFlyerFilter(params, queryset=WasteFlyer.objects.all(), request=request).qs
    signatures = []
    for flyer in qs:
        signatures.append(check_wasteflyer_url.s(flyer.pk))
    callback = check_wasteflyer_urls_callback.s()
    compat_chord = _compat_symbol("chord", chord)
    task_chord = compat_chord(signatures)(callback)
    return task_chord.task_id


@app.task(name="cleanup_orphaned_waste_flyers", trail=True)
def cleanup_orphaned_waste_flyers():
    """Delete WasteFlyers that are no longer referenced by any collections or properties."""

    return WasteFlyer.objects.filter(
        collections__isnull=True,
        collection__isnull=True,
        collectionpropertyvalue__isnull=True,
        aggregatedcollectionpropertyvalue__isnull=True,
    ).delete()


__all__ = [
    "check_wasteflyer_url",
    "check_wasteflyer_urls",
    "check_wasteflyer_urls_callback",
    "cleanup_orphaned_waste_flyers",
]
