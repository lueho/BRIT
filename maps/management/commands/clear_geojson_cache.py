from django.conf import settings
from django.core.cache import caches
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Clear the GeoJSON cache using a key pattern."

    def add_arguments(self, parser):
        parser.add_argument(
            '--pattern',
            dest='pattern',
            required=True,
            help='Cache key pattern to clear (e.g., "*region_geojson*")'
        )

    def handle(self, *args, **options):
        pattern = options['pattern']
        geojson_cache = caches[settings.GEOJSON_CACHE]

        if hasattr(geojson_cache, 'delete_pattern'):
            geojson_cache.delete_pattern(pattern)
        else:
            try:
                client = geojson_cache.client.get_client()
                keys = client.keys(pattern)
                if keys:
                    client.delete(*keys)
            except Exception as e:
                self.stderr.write(f"Error clearing cache with pattern {pattern}: {e}")
                return

        self.stdout.write(f"Cache cleared with pattern: {pattern}")
