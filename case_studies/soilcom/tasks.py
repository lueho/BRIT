from celery import chord
from django.db.models.signals import post_save
from django.http.request import QueryDict, MultiValueDict
from django.utils import timezone
from factory.django import mute_signals

import utils.file_export.storages
from bibliography.utils import check_url
from brit.celery import app
from .filters import CollectionFilterSet
from .filters import WasteFlyerFilter
from .models import Collection
from .models import WasteFlyer
from .renderers import CollectionXLSXRenderer, CollectionCSVRenderer
from .serializers import CollectionFlatSerializer


@app.task(bind=True)
def export_collections_to_file(self, file_format, query_params):
    qdict = QueryDict('', mutable=True)
    qdict.update(MultiValueDict(query_params))

    qs = CollectionFilterSet(qdict, Collection.objects.all()).qs
    data = CollectionFlatSerializer(qs, many=True).data

    file_name = f'collections_{self.request.id}.{file_format}'
    if file_format == 'xlsx':
        return utils.file_export.storages.write_file_for_download(file_name, data, CollectionXLSXRenderer)
    else:
        return utils.file_export.storages.write_file_for_download(file_name, data, CollectionCSVRenderer)


@app.task(name='check_wasteflyer_url', trail=True)
def check_wasteflyer_url(pk):
    flyer = WasteFlyer.objects.get(pk=pk)
    flyer.url_valid = check_url(flyer.url)
    flyer.url_checked = timezone.now()
    with mute_signals(post_save):
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
