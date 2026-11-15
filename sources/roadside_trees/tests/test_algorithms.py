from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Point, Polygon
from django.test import TestCase

from distributions.models import TemporalDistribution, Timestep
from inventories.models import InventoryAmountShare, Scenario
from maps.models import Catchment, Region
from materials.models import (
    ComponentMeasurement,
    Composition,
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    SampleSeries,
)
from sources.roadside_trees.inventory.algorithms import InventoryAlgorithms
from sources.roadside_trees.models import HamburgRoadsideTrees
from sources.urban_green_spaces.models import HamburgGreenAreas

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


class HamburgSeasonalComponentDistributionTestCase(TestCase):
    """Pins the seasonal production per component of the roadside tree method."""

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
        cls.seasons = TemporalDistribution.objects.create(name="Summer/Winter")
        cls.summer = Timestep.objects.create(name="Summer", distribution=cls.seasons)
        cls.winter = Timestep.objects.create(name="Winter", distribution=cls.seasons)
        cls.group = MaterialComponentGroup.objects.create(name="Macro Components")
        for timestep, share in ((cls.summer, 0.75), (cls.winter, 0.25)):
            InventoryAmountShare.objects.create(
                scenario=cls.scenario,
                feedstock=cls.feedstock,
                timestep=timestep,
                average=share,
            )
        # Two trees at 10 kg each: 0.02 Mg/a in total.
        HamburgRoadsideTrees.objects.create(geom=Point(10.0, 53.55, srid=4326))
        HamburgRoadsideTrees.objects.create(geom=Point(10.1, 53.55, srid=4326))

    def _measure(self, sample, component, average):
        Composition.objects.get_or_create(group=self.group, sample=sample)
        ComponentMeasurement.objects.create(
            sample=sample, group=self.group, component=component, average=average
        )

    def _shares(self):
        result = InventoryAlgorithms.hamburg_roadside_tree_production(
            scenario_id=self.scenario.id,
            feedstock_id=self.feedstock.material_id,
            sample_series_id=self.feedstock.id,
            catchment_id=self.catchment.id,
            point_yield={"value": 10.0, "standard_deviation": 1.0},
        )
        (distribution,) = result["aggregated_distributions"]
        self.assertEqual(distribution["name"], "Seasonal production per component")
        self.assertEqual(distribution["distribution"], self.seasons.id)
        return {
            (entry["timestep"], share["component"]): share["average"]
            for entry in distribution["sets"]
            for share in entry["shares"]
        }

    def test_seasonal_compositions_are_weighted_with_seasonal_amount_shares(self):
        biomass = MaterialComponent.objects.create(name="Biomass")
        self.feedstock.add_temporal_distribution(self.seasons)
        fractions = {self.summer.id: 0.6, self.winter.id: 0.4}
        for sample in self.feedstock.samples.filter(
            timestep__distribution=self.seasons
        ):
            self._measure(sample, biomass, fractions[sample.timestep_id])

        shares = self._shares()

        self.assertEqual(len(shares), 2)
        # composition fraction x seasonal amount share x total production
        self.assertAlmostEqual(shares[(self.summer.id, biomass.id)], 0.009)
        self.assertAlmostEqual(shares[(self.winter.id, biomass.id)], 0.002)

    def test_average_composition_is_spread_over_seasonal_amount_shares(self):
        wood = MaterialComponent.objects.create(name="Wood Chips")
        leaves = MaterialComponent.objects.create(name="Leaves")
        average = self.feedstock.samples.get(timestep__distribution__name="Average")
        self._measure(average, wood, 0.75)
        self._measure(average, leaves, 0.25)

        shares = self._shares()

        self.assertEqual(len(shares), 4)
        self.assertAlmostEqual(shares[(self.summer.id, wood.id)], 0.01125)
        self.assertAlmostEqual(shares[(self.summer.id, leaves.id)], 0.00375)
        self.assertAlmostEqual(shares[(self.winter.id, wood.id)], 0.00375)
        self.assertAlmostEqual(shares[(self.winter.id, leaves.id)], 0.00125)


class HamburgParkProductionTestCase(TestCase):
    """Pins totals and units of the park area method."""

    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name="Hamburg")
        cls.region.geom = GEOSGeometry(CATCHMENT_WKT, srid=4326)
        cls.region.save(update_fields=["borders"])
        cls.catchment = Catchment.objects.create(name="Hamburg", region=cls.region)
        # The western half of this park lies outside the catchment.
        cls.park = HamburgGreenAreas.objects.create(
            anlagenname="Border park",
            geom=MultiPolygon(
                Polygon(
                    (
                        (9.89, 53.5),
                        (9.91, 53.5),
                        (9.91, 53.51),
                        (9.89, 53.51),
                        (9.89, 53.5),
                    ),
                    srid=4326,
                )
            ),
        )
        HamburgGreenAreas.objects.create(
            anlagenname="Remote park",
            geom=MultiPolygon(
                Polygon(
                    (
                        (11, 53.5),
                        (11.01, 53.5),
                        (11.01, 53.51),
                        (11, 53.51),
                        (11, 53.5),
                    ),
                    srid=4326,
                )
            ),
        )

    def test_area_is_clipped_to_catchment_and_multiplied_with_yield(self):
        result = InventoryAlgorithms.hamburg_park_production(
            catchment_id=self.catchment.id,
            area_yield={"value": 0.5, "standard_deviation": 0.1},
        )

        entries = {entry["name"]: entry for entry in result["aggregated_values"]}
        park_area = self.park.geom.transform(6933, clone=True).area
        area = entries["Total area"]["value"]
        self.assertEqual(entries["Total area"]["unit"], "m²")
        self.assertAlmostEqual(area / park_area, 0.5, places=2)
        self.assertEqual(entries["Total production"]["unit"], "kg")
        self.assertAlmostEqual(entries["Total production"]["value"], area * 0.5)
        (feature,) = result["features"]
        self.assertEqual(sorted(feature), ["area", "geom", "yield_average"])
        self.assertAlmostEqual(feature["area"], area)
        self.assertAlmostEqual(feature["yield_average"], area * 0.5)
