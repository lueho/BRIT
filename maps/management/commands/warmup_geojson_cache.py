from django.conf import settings
from django.core.cache import caches
from django.core.management.base import BaseCommand

from maps.models import NutsRegion
from maps.serializers import NutsRegionGeometrySerializer


class Command(BaseCommand):
    help = "Preload common GeoJSON data into the cache"

    def add_arguments(self, parser):
        parser.add_argument(
            "--nuts-levels",
            type=str,
            default="0,1,2",
            help="Comma-separated list of NUTS levels to cache",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limit the number of items to cache per type",
        )

    def handle(self, *args, **options):
        geojson_cache = caches[getattr(settings, "GEOJSON_CACHE", "default")]
        nuts_levels = [int(level) for level in options["nuts_levels"].split(",")]
        limit = options["limit"]

        self.stdout.write("Warming up GeoJSON cache...")

        # Cache NUTS regions by level
        for level in nuts_levels:
            self.stdout.write(f"Caching NUTS level {level} regions...")
            queryset = NutsRegion.objects.filter(levl_code=level)
            if limit:
                queryset = queryset[:limit]

            for region in queryset:
                cache_key = f"nuts_geojson:level:{level}:id:{region.id}"
                serializer = NutsRegionGeometrySerializer([region], many=True)
                geojson_cache.set(cache_key, serializer.data)

            # Also cache the collection
            cache_key = f"nuts_geojson:level:{level}"
            serializer = NutsRegionGeometrySerializer(queryset, many=True)
            geojson_cache.set(cache_key, serializer.data)

        self.stdout.write("Cache warmup complete!")
