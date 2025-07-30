from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .sitemap_items import SITEMAP_ITEMS


class DynamicViewSitemap(Sitemap):
    priority = 0.5
    changefreq = 'daily'

    def items(self):
        return [item for item in SITEMAP_ITEMS if item != '/']  # Exclude root URL

    def location(self, item):
        return item

class HomepageSitemap(Sitemap):
    priority = 1.0
    changefreq = 'daily'

    def items(self):
        return ['/']

    def location(self, item):
        return item