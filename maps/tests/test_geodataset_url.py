from django.test import TestCase
from django.urls import reverse
from maps.models import GeoDataset, Region

class GeoDatasetGetAbsoluteUrlTest(TestCase):
    def setUp(self):
        # Create a region, required ForeignKey for GeoDataset
        self.region = Region.objects.create(name="Test Region", country="Testland")

    def test_get_absolute_url_returns_pk_based_url(self):
        dataset = GeoDataset.objects.create(
            name="Test Dataset",
            region=self.region,
            model_name="HamburgRoadsideTrees",
            table_name="test_table",
            geometry_field="geom",
            display_fields="name",
            filter_fields="name"
        )
        url = dataset.get_absolute_url()
        expected_url = reverse("geodataset-map", args=[dataset.pk])
        self.assertEqual(url, expected_url)
        # Optionally, check that the view returns a 200
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
