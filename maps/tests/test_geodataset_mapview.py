from importlib import reload

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.urls import clear_url_caches, reverse

import maps.urls
from maps.models import GeoDataset, Region


class GeoDatasetMapViewTest(TestCase):
    def setUp(self):
        self.region = Region.objects.create(name="Test Region", country="Testland")
        # Create test table
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_mapview_table (
                    id serial PRIMARY KEY,
                    geom text,
                    name varchar(100),
                    species varchar(50)
                )
            """)
            cursor.execute(
                "INSERT INTO test_mapview_table (geom, name, species) VALUES ('POINT(1 1)', 'Tree2', 'Pine')"
            )
        self.dataset = GeoDataset.objects.create(
            name="Test MapView Dataset",
            region=self.region,
            table_name="test_mapview_table",
            geometry_field="geom",
            display_fields="name",
            filter_fields="species",
        )

    def tearDown(self):
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS test_mapview_table")

    @override_settings(ENABLE_GENERIC_DATASET=True)
    def test_generic_map_view_filters_and_lists(self):
        clear_url_caches()
        reload(maps.urls)
        url = reverse("geodataset-map", args=[self.dataset.pk])
        response = self.client.get(url, {"species": "Pine"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pine")
        self.assertContains(response, 'name="species"')

    @override_settings(ENABLE_GENERIC_DATASET=False)
    def test_legacy_map_view_errors_for_pk_only_dataset(self):
        clear_url_caches()
        reload(maps.urls)
        url = reverse("geodataset-map", args=[self.dataset.pk])
        with self.assertRaises(ImproperlyConfigured):
            self.client.get(url)
