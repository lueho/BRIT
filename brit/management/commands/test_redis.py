from django.core.management.base import BaseCommand
import redis
import os


class Command(BaseCommand):
    help = 'Test Redis connection'

    def handle(self, *args, **options):
        redis_url = os.environ.get('REDIS_URL')
        self.stdout.write(f"Attempting to connect to Redis at {redis_url}")

        try:
            r = redis.from_url(redis_url, ssl_cert_reqs=None)
            r.ping()
            self.stdout.write(self.style.SUCCESS('Successfully connected to Redis'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to connect to Redis: {str(e)}'))