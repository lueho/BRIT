from celery import chord
from django.contrib.auth import get_user_model
from django.utils import timezone

from brit.celery import app
from utils.object_management.permissions import filter_queryset_for_user
from utils.object_management.policy import decide

from .filters import SourceFilter
from .models import Source
from .utils import check_url


@app.task
def task_check_url(url):
    return check_url(url)


@app.task(name="check_source_url")
def check_source_url(pk, user_id=None):
    """Refresh only ``url_valid``/``url_checked`` health metadata for a source.

    When a ``user_id`` is supplied the acting identity's current
    ``check_url`` decision is re-evaluated before any write.
    """
    source = Source.objects.filter(pk=pk).first()
    if source is None:
        return None
    if user_id is not None:
        actor = get_user_model().objects.filter(pk=user_id).first()
        if actor is None or not decide(actor, "check_url", source).allowed:
            return None
    source.url_valid = check_url(source.url)
    source.url_checked = timezone.localdate()
    source.save(update_fields=["url_valid", "url_checked"])


@app.task()
def check_source_urls_callback(results):
    return f"Checked {len(results)} sources."


@app.task()
def check_source_urls(params, user_id=None):
    user = None
    if user_id:
        user = get_user_model().objects.filter(pk=user_id).first()
    qs = SourceFilter(params, queryset=Source.objects.all()).qs
    if user is not None:
        qs = filter_queryset_for_user(qs, user)
    signatures = [
        check_source_url.s(source.pk, user_id)
        for source in qs
        if user is None or decide(user, "check_url", source).allowed
    ]
    callback = check_source_urls_callback.s()
    task_chord = chord(signatures)(callback)
    return task_chord
