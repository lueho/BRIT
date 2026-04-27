from django.contrib.gis.geos import Point
from django.urls import reverse

from maps.models import (
    GeoDataset,
    GeoDatasetRuntimeConfiguration,
    MapConfiguration,
    MapLayerConfiguration,
    MapLayerStyle,
    Region,
)
from utils.tests.testcases import ViewWithPermissionsTestCase

from ..models import NantesGreenhouses


class NantesGreenhousesMapViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ["view_geodataset"]
    url_name = "NantesGreenhouses"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        style = MapLayerStyle.objects.create(name="default")
        layer = MapLayerConfiguration.objects.create(
            name="default", layer_type="features", style=style
        )
        map_config = MapConfiguration.objects.create(name="default")
        map_config.layers.add(layer)
        GeoDataset.objects.create(
            name="Nantes Greenhouses",
            description="Greenhouses in Nantes",
            model_name="NantesGreenhouses",
            region=Region.objects.create(name="Nantes", country="France"),
            map_configuration=map_config,
        )
        NantesGreenhouses.objects.create(geom=Point(0, 0, srid=4326))

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse(self.url_name))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_via_maps_nantes_prefix(self):
        response = self.client.get("/maps/nantes/greenhouses/map/")
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_via_case_studies_nantes_prefix(self):
        response = self.client.get("/case_studies/nantes/greenhouses/map/")
        self.assertEqual(response.status_code, 200)

    def test_dataset_map_route_uses_greenhouses_plugin_runtime_compatibility(self):
        dataset = GeoDataset.objects.create(
            name="Nantes Greenhouses Runtime Dataset",
            owner=self.owner,
            publication_status="published",
            region=Region.objects.create(name="Nantes Runtime", country="France"),
        )
        GeoDatasetRuntimeConfiguration.objects.create(
            dataset=dataset,
            backend_type="django_model",
            runtime_model_name="NantesGreenhouses",
        )

        response = self.client.get(reverse("geodataset-map", kwargs={"pk": dataset.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, dataset.name)
        self.assertContains(response, reverse("api-nantes-greenhouses-geojson"))
