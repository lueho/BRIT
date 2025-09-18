from celery import chord
from django.utils import timezone

from bibliography.utils import check_url
from brit.celery import app

from .filters import WasteFlyerFilter
from .models import WasteFlyer



@app.task(name='check_wasteflyer_url', trail=True)
def check_wasteflyer_url(pk):
    flyer = WasteFlyer.objects.get(pk=pk)
    flyer.url_valid = check_url(flyer.url)
    flyer.url_checked = timezone.localdate()
    flyer.save()
    return True


@app.task(name='callback')
def check_wasteflyer_urls_callback(results):
    return f'Checked {len(results)} flyers.'


@app.task(bind=True, trail=True, name='scheduler')
def check_wasteflyer_urls(self, params):
    self.myname = 'scheduler'
    qs = WasteFlyerFilter(params, queryset=WasteFlyer.objects.all()).qs
    signatures = []
    for i, flyer in enumerate(qs):
        signatures.append(check_wasteflyer_url.s(flyer.pk))
    callback = check_wasteflyer_urls_callback.s()
    task_chord = chord(signatures)(callback)
    return task_chord
