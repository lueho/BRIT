from django.contrib.gis.geos import GEOSGeometry, Point
from django.test import TestCase

from distributions.models import TemporalDistribution, Timestep
from inventories.models import Scenario
from maps.models import Catchment, Region
from materials.models import Material, MaterialComponent, SampleSeries
from sources.greenhouses.inventory.algorithms import InventoryAlgorithms
from sources.greenhouses.models import (
    Culture,
    Greenhouse,
    GreenhouseGrowthCycle,
    GrowthShare,
    GrowthTimeStepSet,
    NantesGreenhouses,
)

CATCHMENT_WKT = "MULTIPOLYGON(((-2 47, -1 47, -1 48, -2 48, -2 47)))"


def aggregated_value(result, name):
    return next(
        entry["value"] for entry in result["aggregated_values"] if entry["name"] == name
    )


class NantesGreenhouseProductionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name="Nantes")
        cls.region.geom = GEOSGeometry(CATCHMENT_WKT, srid=4326)
        cls.region.save(update_fields=["borders"])
        cls.catchment = Catchment.objects.create(name="Nantes", region=cls.region)
        cls.scenario = Scenario.objects.create(
            name="Nantes scenario", region=cls.region, catchment=cls.catchment
        )
        distribution = TemporalDistribution.objects.get(name="Months of the year")
        cls.timestep = Timestep.objects.create(name="Jan", distribution=distribution)
        cls.feedstock = SampleSeries.objects.create(
            name="Tomato residues",
            material=Material.objects.create(name="Greenhouse residues"),
        )
        cls.culture = Culture.objects.create(name="Tomato", residue=cls.feedstock)
        cls.greenhouse_type = Greenhouse.objects.create(
            name="Tomato greenhouse",
            heated=True,
            lighted=False,
            high_wire=False,
            above_ground=True,
        )
        cycle = GreenhouseGrowthCycle.objects.create(
            greenhouse=cls.greenhouse_type, culture=cls.culture, cycle_number=1
        )
        timestepset = GrowthTimeStepSet.objects.create(
            timestep=cls.timestep, growth_cycle=cycle
        )
        GrowthShare.objects.create(
            component=MaterialComponent.objects.create(name="Dry matter"),
            timestepset=timestepset,
            average=0.5,
        )

    def _greenhouse(self, surface_ha):
        return NantesGreenhouses.objects.create(
            geom=Point(-1.5, 47.5, srid=4326),
            surface_ha=surface_ha,
            culture_1="Tomato",
            heated=True,
            lighted=False,
            high_wire=False,
            above_ground=True,
        )

    def _run(self):
        return InventoryAlgorithms.nantes_greenhouse_production(
            scenario_id=self.scenario.id,
            feedstock_id=self.feedstock.material_id,
            sample_series_id=self.feedstock.id,
            heated={"value": 2},
            lit={"value": 2},
            high_wire={"value": 2},
            above_ground={"value": 2},
        )

    def test_group_with_null_surface_counts_as_zero_area(self):
        """surface_ha is nullable; Sum over all-NULL rows returns None and must
        not crash the aggregation."""
        self._greenhouse(surface_ha=None)

        result = self._run()

        self.assertEqual(
            aggregated_value(result, "Number of considered greenhouses"), 1
        )
        self.assertEqual(aggregated_value(result, "Total growth area"), 0)
        self.assertEqual(aggregated_value(result, "Total production"), 0)

    def test_group_surface_and_production_are_aggregated(self):
        self._greenhouse(surface_ha=2.0)
        self._greenhouse(surface_ha=3.0)

        result = self._run()

        self.assertEqual(
            aggregated_value(result, "Number of considered greenhouses"), 2
        )
        self.assertEqual(aggregated_value(result, "Total growth area"), 5.0)
        self.assertEqual(aggregated_value(result, "Total production"), 2.5)

    def test_no_matching_greenhouses_returns_empty_result(self):
        result = self._run()

        self.assertEqual(
            aggregated_value(result, "Number of considered greenhouses"), 0
        )
        self.assertEqual(aggregated_value(result, "Total growth area"), 0)
        self.assertEqual(aggregated_value(result, "Total production"), 0)
