from django.test import TestCase
from django.apps import apps
from django.db import connection
from maps.models import GeoDataset

class GeoDatasetMetadataTestCase(TestCase):
    def setUp(self):
        self.required_fields = [
            'table_name',
            'geometry_field',
            'display_fields',
            'filter_fields',
        ]

    def test_metadata_fields_exist(self):
        """
        Test that the new metadata fields exist on the GeoDataset model.
        """
        for field in self.required_fields:
            with self.subTest(field=field):
                self.assertTrue(
                    hasattr(GeoDataset, field),
                    f"GeoDataset is missing field: {field}"
                )

    def test_metadata_fields_in_db(self):
        """
        Test that the new metadata fields are present in the database schema.
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'maps_geodataset';
            """)
            columns = [row[0] for row in cursor.fetchall()]
        for field in self.required_fields:
            with self.subTest(field=field):
                self.assertIn(field, columns, f"DB table is missing column: {field}")

    def test_admin_can_set_metadata(self):
        """
        Test that metadata fields can be set and saved on a GeoDataset instance.
        """
        region_model = apps.get_model('maps', 'Region')
        region = region_model.objects.create(country='DE')
        dataset = GeoDataset.objects.create(
            region=region,
            table_name='my_test_table',
            geometry_field='geom',
            display_fields='name',
            filter_fields='type,year',
        )
        dataset.refresh_from_db()
        self.assertEqual(dataset.table_name, 'my_test_table')
        self.assertEqual(dataset.geometry_field, 'geom')
        self.assertEqual(dataset.display_fields, 'name')
        self.assertEqual(dataset.filter_fields, 'type,year')
