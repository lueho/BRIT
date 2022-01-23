import psycopg2
from django.core.management.base import BaseCommand, CommandError

from case_studies.soilcom.models import Collection, Collector, CollectionSystem, WasteCategory, WasteStream, WasteFlyer
from maps.models import LauRegion, Catchment
from materials.models import Material


class Command(BaseCommand):

    def handle(self, *args, **options):

        connection = psycopg2.connect(user="brit_admin", password="V88a&ToxyMyI", host="db", port="5432",
                                      database="brit_db")
        cursor = connection.cursor()
        fields = (
            'lau_id', 'lau_name', 'collector', 'collector_url', 'sys', 'npab', 'pab', 'nppb', 'ppb', 'sgw', 'hgw',
            'anybags',
            'biobags', 'flyer_url')
        query = f"SELECT {', '.join(fields)} FROM collections"
        cursor.execute(query)
        records = cursor.fetchall()

        for r in records:

            try:

                # Select collection system
                if r[4] == 'dd':
                    collection_system = CollectionSystem.objects.get(name='Door to door')
                elif r[4] == 'hwrc':
                    collection_system = CollectionSystem.objects.get(name='Recycling centre')

                # Select Waste category
                fw = False
                gw = False
                npab = r[5]
                if npab == '1':
                    fw = True
                pab = r[6]
                if pab == '1':
                    fw = True
                nppb = r[7]
                if nppb == '1':
                    fw = True
                ppb = r[8]
                if ppb == '1':
                    fw = True
                sgw = r[9]
                if sgw == '1':
                    gw = True
                hgw = r[10]
                if sgw == '1':
                    gw = True

                if fw and gw:
                    category = WasteCategory.objects.get(name='Biowaste')
                elif fw:
                    category = WasteCategory.objects.get(name='Food waste')
                elif gw:
                    category = WasteCategory.objects.get(name='Green waste')

                # Create waste stream
                waste_stream = WasteStream.objects.create(
                    owner_id=1,
                    name=f'{r[1]} ({r[2]}) {collection_system}',
                    category=category
                )

                # Add allowed materials to waste stream
                ab = r[11]
                bb = r[12]
                if npab == '1':
                    am = Material.objects.get(name='Food waste: Non-processed animal-based')
                    waste_stream.allowed_materials.add(am)
                if pab == '1':
                    am = Material.objects.get(name='Food waste: Processed animal-based')
                    waste_stream.allowed_materials.add(am)
                if nppb == '1':
                    am = Material.objects.get(name='Food waste: Non-processed plant-based')
                    waste_stream.allowed_materials.add(am)
                if ppb == '1':
                    am = Material.objects.get(name='Food waste: Processed plant-based waste')
                    waste_stream.allowed_materials.add(am)
                if sgw == '1':
                    am = Material.objects.get(name='Garden waste: Soft materials')
                    waste_stream.allowed_materials.add(am)
                if hgw == '1':
                    am = Material.objects.get(name='Garden waste: Hard materials')
                    waste_stream.allowed_materials.add(am)
                if ab == '1':
                    am = Material.objects.get(name='Plastic bags')
                    waste_stream.allowed_materials.add(am)
                    am = Material.objects.get(name='Paper bags')
                    waste_stream.allowed_materials.add(am)
                    am = Material.objects.get(name='Biodegradable plastic bags')
                    waste_stream.allowed_materials.add(am)
                if bb == '1':
                    am = Material.objects.get(name='Biodegradable plastic bags')
                    waste_stream.allowed_materials.add(am)

                # Add collector
                collector = Collector.objects.create(
                    owner_id=1,
                    name=r[2],
                    website=r[3]
                )

                # Add catchment
                lau = LauRegion.objects.get(lau_id=r[0])
                catchment = Catchment.objects.create(
                    owner_id=1,
                    name=f'{lau.lau_name} ({lau.lau_id})',
                    region=lau.region_ptr,
                    parent_region=lau.nuts_parent.region_ptr,
                    type='administrative'
                )

                # Add Flyer
                flyer = WasteFlyer.objects.create(
                    owner_id=1,
                    type='waste_flyer',
                    title=f'Waste flyer {catchment.region.name} ({catchment.region.lauregion.lau_id}) {collection_system.name})',
                    abbreviation=f'WasteFlyer{catchment.region.lauregion.lau_id}',
                    url=r[13]
                )

                # Create Collection
                collection = Collection.objects.create(
                    owner_id=1,
                    name=f'{catchment.region.name} ({catchment.region.lauregion.lau_id}) {collection_system.name})',
                    collector=collector,
                    catchment=catchment,
                    collection_system=collection_system,
                    waste_stream=waste_stream,
                    flyer=flyer
                )

            except Exception as e:
                raise CommandError(f'Exception for {r[1]}: {r[4]} ==> {e}')

        cursor.close()
        connection.close()
