from case_studies.soilcom.models import Collection, CollectionSystem, WasteCategory, WasteStream
from maps.models import Catchment
from materials.models import Material
from django.db.models import Count

d2d = CollectionSystem.objects.get(name='Door to door')
rc = CollectionSystem.objects.get(name='Recycling centre')
fw = WasteCategory.objects.get(name='Food waste')
bw = WasteCategory.objects.get(name='Biowaste')
gw = WasteCategory.objects.get(name='Green waste')
rw = WasteCategory.objects.get(name='Residual waste')

fw_all = Material.objects.filter(
    name__in=['Food waste: Non-processed animal-based', 'Food waste: Processed animal-based',
              'Food waste: Non-processed plant-based', 'Food waste: Processed plant-based'])
gw_all = Material.objects.filter(name__in=['Garden waste: Soft materials', 'Garden waste: Hard materials'])
gw_soft = Material.objects.filter(name__in=['Garden waste: Soft materials',])
Material.objects.get_or_create(name='Soil')
soil = Material.objects.filter(name__in=['Soil',])

ws_fw = WasteStream.objects.get_or_create(category=fw, allowed_materials=fw_all, forbidden_materials=Material.objects.none())[0]
ws_gw_all = WasteStream.objects.get_or_create(category=gw, allowed_materials=gw_all, forbidden_materials=Material.objects.none())[0]
ws_gw_soft = WasteStream.objects.get_or_create(category=gw, allowed_materials=gw_soft, forbidden_materials=soil)[0]
interreg = Catchment.objects.get(name__icontains='INTERREG')
uk_catchments = Catchment.objects.filter(region__borders__geom__within=interreg.region.borders.geom, region__country='UK').annotate(num_collections=Count('collections')).filter(num_collections__gt=0)

for catchment in uk_catchments:
    print(catchment)
    fwd2d = Collection.objects.filter(catchment=catchment, waste_stream__category=fw)
    if not fwd2d.exists():
        fwd2d = Collection.objects.create(catchment=catchment, collector=catchment.collector_set.first(),
                                          waste_stream=ws_fw, collection_system=d2d)
        print(fwd2d)

    gwd2d = Collection.objects.filter(catchment=catchment, waste_stream__category=gw, collection_system=d2d)
    if not gwd2d.exists():
        gwd2d = Collection.objects.create(catchment=catchment, collector=catchment.collector_set.first(),
                                          waste_stream=ws_gw_soft, collection_system=d2d, description='Paid subscription based service.')
        print(gwd2d)

    gwrc = Collection.objects.filter(catchment=catchment, waste_stream__category=gw, collection_system=rc)
    if not gwrc.exists():
        gwrc = Collection.objects.create(catchment=catchment, collector=catchment.collector_set.first(),
                                         waste_stream=ws_gw_all, collection_system=rc)
        print(gwrc)

    print('\n\n')



