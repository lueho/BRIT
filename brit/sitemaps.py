from django.contrib.sitemaps import Sitemap

from .sitemap_registry import get_sitemap_items


class DynamicViewSitemap(Sitemap):
    priority = 0.5
    changefreq = "daily"

    def items(self):
        return [item for item in get_sitemap_items() if item != "/"]  # Exclude root URL

    def location(self, item):
        return item


class HomepageSitemap(Sitemap):
    priority = 1.0
    changefreq = "daily"

    def items(self):
        return ["/"]

    def location(self, item):
        return item
