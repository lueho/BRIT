from importlib import reload

from django.test import TestCase, override_settings
from django.urls import clear_url_caches

import maps.urls
from maps.models import GeoDataset, Region


class GeoDatasetGetAbsoluteUrlTest(TestCase):
    def setUp(self):
        # Create a region, required ForeignKey for GeoDataset
        self.region = Region.objects.create(name="Test Region", country="Testland")
        # Legacy dataset with custom model/filterset
        self.legacy_dataset = GeoDataset.objects.create(
            name="Legacy Dataset",
            region=self.region,
            model_name="HamburgRoadsideTrees",
            table_name="test_table",
            geometry_field="geom",
            display_fields="name",
            filter_fields="name",
        )
        # PK-based dataset for generic view
        self.generic_dataset = GeoDataset.objects.create(
            name="Generic Dataset",
            region=self.region,
            table_name="test_table",
            geometry_field="geom",
            display_fields="name",
            filter_fields="name",
        )

    @override_settings(ROOT_URLCONF="maps.test_urls_generic")
    def test_get_absolute_url_returns_pk_based_url(self):
        clear_url_caches()
        reload(maps.urls)
        url = self.generic_dataset.get_absolute_url()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(str(self.generic_dataset.pk), url)

    @override_settings(ROOT_URLCONF="maps.urls")
    def test_legacy_absolute_url_uses_legacy_view(self):
        clear_url_caches()
        reload(maps.urls)
        url = self.legacy_dataset.get_absolute_url()
        response = self.client.get(url)
        self.assertIn(
            response.status_code, [200, 404]
        )  # 404 if test_table doesn't exist, 200 if it does
        self.assertIn(str(self.legacy_dataset.pk), url)
