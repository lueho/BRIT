import os
import re

from django.core.management.base import BaseCommand
from django.urls import URLPattern, URLResolver, get_resolver


class Command(BaseCommand):
    help = "Generates a list of all URL patterns in the project"

    def handle(self, *args, **options):
        resolver = get_resolver()
        patterns = self.get_patterns(resolver)

        exclude_paths = ["admin/", "users/", "media/", "static/", "__debug__/"]

        output_file = os.path.join("brit", "sitemap_items.py")
        with open(output_file, "w") as f:
            f.write("SITEMAP_ITEMS = [\n")
            for pattern in patterns:
                if not any(pattern.startswith(excluded) for excluded in exclude_paths):
                    if "<" not in pattern:
                        # Clean up the URL
                        clean_pattern = self.clean_url(pattern)
                        if clean_pattern:
                            f.write(f"    '{clean_pattern}',\n")
            f.write("]\n")

        self.stdout.write(
            self.style.SUCCESS(f"Successfully generated sitemap items in {output_file}")
        )

    def get_patterns(self, resolver, prefix=""):
        patterns = []
        for url_pattern in resolver.url_patterns:
            if isinstance(url_pattern, URLResolver):
                patterns += self.get_patterns(
                    url_pattern, prefix + str(url_pattern.pattern)
                )
            elif isinstance(url_pattern, URLPattern):
                patterns.append(prefix + str(url_pattern.pattern))
        return patterns

    def clean_url(self, url):
        # Remove regex characters and clean up the URL
        url = re.sub(r"\^", "", url)  # Remove ^ from anywhere in the URL
        url = re.sub(r"\$$", "", url)  # Remove ending $ if it exists
        url = re.sub(r"\(.+?\)", "", url)  # Remove regex groups
        url = re.sub(r"[{}]", "", url)  # Remove curly braces
        url = re.sub(r"/+", "/", url)  # Replace multiple slashes with a single slash
        url = "/" + url.lstrip("/")  # Ensure the URL starts with a single /
        url = url.rstrip("/") + "/"  # Ensure the URL ends with a single /
        return url if url != "/" else ""  # Return empty string for root URL
