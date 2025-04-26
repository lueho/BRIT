from django.test import TestCase
from maps.models import GeoDataset, Region
from maps.dynamic_model import get_dynamic_model, get_dynamic_filterset
from django.db import connection

class DynamicModelTest(TestCase):
    def setUp(self):
        # Create a region and a simple table for testing
        self.region = Region.objects.create(name="Test Region", country="Testland")
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_dyn_table (
                    id serial PRIMARY KEY,
                    geom text,
                    name varchar(100),
                    species varchar(50)
                )
            """)
            cursor.execute("INSERT INTO test_dyn_table (geom, name, species) VALUES ('POINT(0 0)', 'Tree1', 'Oak')")

        self.dataset = GeoDataset.objects.create(
            name="Test Dynamic Dataset",
            region=self.region,
            table_name="test_dyn_table",
            geometry_field="geom",
            display_fields="name",
            filter_fields="species"
        )

    def tearDown(self):
        # Clean up the test table
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS test_dyn_table")

    def test_dynamic_model_fields_and_query(self):
        model = get_dynamic_model(self.dataset)
        # Check fields
        self.assertTrue(hasattr(model, 'name'))
        self.assertTrue(hasattr(model, 'species'))
        self.assertTrue(hasattr(model, 'geom'))
        # Query the table
        objs = model.objects.all()
        self.assertEqual(objs.count(), 1)
        self.assertEqual(objs[0].name, 'Tree1')
        self.assertEqual(objs[0].species, 'Oak')

    def test_dynamic_filterset_fields_and_filtering(self):
        filterset_class = get_dynamic_filterset(self.dataset)
        # Should only expose 'species' as a filter
        self.assertIn('species', filterset_class.get_fields())
        self.assertNotIn('name', filterset_class.get_fields())
        # Should filter correctly
        qs = get_dynamic_model(self.dataset).objects.all()
        f = filterset_class({'species': 'Oak'}, queryset=qs)
        self.assertEqual(f.qs.count(), 1)
        self.assertEqual(f.qs[0].species, 'Oak')
