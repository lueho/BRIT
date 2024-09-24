from django.core.management.base import BaseCommand
from django.urls import URLResolver, URLPattern
from django.urls import get_resolver
import os


class Command(BaseCommand):
    help = 'Generates a list of all URL patterns in the project'

    def handle(self, *args, **options):
        resolver = get_resolver()
        patterns = self.get_patterns(resolver)

        # Paths to exclude from the sitemap
        exclude_paths = [
            '^admin/',
            '^users/',
            '^media/',
            '^static/',
            '^__debug__/',
        ]

        output_file = os.path.join('brit', 'sitemap_items.py')
        with open(output_file, 'w') as f:
            f.write("SITEMAP_ITEMS = [\n")
            for pattern in patterns:
                if not any(pattern.startswith(excluded) for excluded in exclude_paths):
                    if '<' not in pattern:  # Exclude URL patterns with parameters
                        f.write(f"    '{pattern}',\n")
            f.write("]\n")

        self.stdout.write(self.style.SUCCESS(f'Successfully generated sitemap items in {output_file}'))

    def get_patterns(self, resolver, prefix=''):
        patterns = []
        for url_pattern in resolver.url_patterns:
            if isinstance(url_pattern, URLResolver):
                patterns += self.get_patterns(url_pattern, prefix + url_pattern.pattern.regex.pattern)
            elif isinstance(url_pattern, URLPattern):
                patterns.append(prefix + str(url_pattern.pattern))
        return patterns