import logging

import redis
from django.conf import settings
from django.core.cache import caches
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Monitor Redis cache usage for GeoJSON data using SCAN"

    def handle(self, *args, **options):
        cache_alias = getattr(settings, "GEOJSON_CACHE", "default")
        try:
            geojson_cache = caches[cache_alias]
            # Attempt to get the low-level client. This depends on django-redis version/config.
            # May need adjustment based on actual setup.
            if hasattr(geojson_cache, "client") and hasattr(
                geojson_cache.client, "get_client"
            ):
                # Typically for DefaultClient
                redis_client = geojson_cache.client.get_client(write=False)
            # Add checks here for other client types if necessary (e.g., ShardedClient)
            else:
                # Fallback: try parsing connection details if possible (less reliable)
                # Or instruct user on how to expose the client if needed.
                raise CommandError(
                    f"Cannot automatically retrieve Redis client from cache backend '{cache_alias}'. "
                    "Ensure it's a standard django-redis setup or adjust command."
                )

            if not isinstance(redis_client, redis.Redis):
                raise CommandError(
                    "Retrieved client is not a recognized 'redis-py' client."
                )

        except Exception as e:
            raise CommandError(
                f"Error accessing Redis client for cache '{cache_alias}': {e}"
            ) from e

        self.stdout.write(
            f"Monitoring GeoJSON cache usage in Redis DB {redis_client.connection_pool.connection_kwargs.get('db', '?')}..."
        )
        self.stdout.write("-" * 50)

        try:
            # Get general cache statistics
            info = redis_client.info()
            self.stdout.write(f"Redis version: {info.get('redis_version', 'N/A')}")
            self.stdout.write(
                f"Connected clients: {info.get('connected_clients', 'N/A')}"
            )
            self.stdout.write(f"Used memory: {info.get('used_memory_human', 'N/A')}")
            db_keys = info.get(
                f"db{redis_client.connection_pool.connection_kwargs.get('db', 0)}", {}
            ).get("keys", "N/A")
            self.stdout.write(f"Total keys in DB: {db_keys}")

            # Use SCAN to find GeoJSON specific keys safely
            geojson_key_count = 0
            key_sizes = []
            # Match keys containing 'geojson' anywhere - adjust pattern if needed
            # scan_iter is efficient as it yields keys one by one
            # Use a reasonable count for iteration chunk size
            for key in redis_client.scan_iter(match="*geojson*", count=1000):
                key_str = key.decode("utf-8")  # Decode bytes key
                geojson_key_count += 1
                try:
                    # MEMORY USAGE can also be slow for huge keys, use cautiously
                    size = redis_client.memory_usage(key)
                    if size is not None:
                        key_sizes.append((key_str, size))
                except redis.RedisError as mem_err:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Could not get memory usage for key '{key_str}': {mem_err}"
                        )
                    )

            self.stdout.write(f"GeoJSON keys found (via SCAN): {geojson_key_count}")

            if key_sizes:
                self.stdout.write(
                    "\nTop 10 largest GeoJSON cache entries (by approximate memory usage):"
                )
                # Sort by size (largest first) and show top 10
                key_sizes.sort(key=lambda x: x[1], reverse=True)
                for key, size in key_sizes[:10]:
                    self.stdout.write(
                        f"  {key}: {size / 1024:.2f} KB"
                    )  # Convert bytes to KB

            self.stdout.write("-" * 50)
            self.stdout.write(self.style.SUCCESS("Cache monitoring check complete."))

        except redis.RedisError as e:
            raise CommandError(f"Redis error during monitoring: {e}") from e
        except Exception as e:
            logger.exception("An unexpected error occurred during cache monitoring.")
            raise CommandError(f"An unexpected error occurred: {e}") from e
