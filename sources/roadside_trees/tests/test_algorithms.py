from django.contrib.gis.geos import GEOSGeometry, Point
from django.test import TestCase

from inventories.models import Scenario
from maps.models import Catchment, Region
from materials.models import Material, SampleSeries
from sources.roadside_trees.inventory.algorithms import InventoryAlgorithms
from sources.roadside_trees.models import HamburgRoadsideTrees

CATCHMENT_WKT = "MULTIPOLYGON(((9.9 53.4, 10.2 53.4, 10.2 53.7, 9.9 53.7, 9.9 53.4)))"


def aggregated_value(result, name):
    return next(
        entry["value"] for entry in result["aggregated_values"] if entry["name"] == name
    )


class HamburgRoadsideTreeProductionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name="Hamburg")
        cls.region.geom = GEOSGeometry(CATCHMENT_WKT, srid=4326)
        cls.region.save(update_fields=["borders"])
        cls.catchment = Catchment.objects.create(name="Hamburg", region=cls.region)
        cls.scenario = Scenario.objects.create(
            name="Hamburg scenario", region=cls.region, catchment=cls.catchment
        )
        cls.feedstock = SampleSeries.objects.create(
            name="Tree pruning residues",
            material=Material.objects.create(name="Woody biomass"),
        )

    def test_counts_and_aggregates_trees_in_catchment(self):
        HamburgRoadsideTrees.objects.create(geom=Point(10.0, 53.55, srid=4326))
        HamburgRoadsideTrees.objects.create(geom=Point(10.1, 53.55, srid=4326))
        HamburgRoadsideTrees.objects.create(geom=Point(11.0, 53.55, srid=4326))

        result = InventoryAlgorithms.hamburg_roadside_tree_production(
            scenario_id=self.scenario.id,
            feedstock_id=self.feedstock.material_id,
            sample_series_id=self.feedstock.id,
            catchment_id=self.catchment.id,
            point_yield={"value": 10.0, "standard_deviation": 1.0},
        )

        self.assertEqual(aggregated_value(result, "Count"), 2)
        self.assertAlmostEqual(
            aggregated_value(result, "Total production"), 0.02, places=6
        )
        self.assertEqual(len(result["features"]), 2)
