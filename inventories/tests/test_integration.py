from django.apps import apps
from django.contrib.auth.models import User
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.db import connection
from django.test import TestCase, override_settings

from case_studies.flexibi_hamburg.models import HamburgGreenAreas, HamburgRoadsideTrees
from case_studies.flexibi_nantes.models import (
    Culture,
    Greenhouse,
    GreenhouseGrowthCycle,
    GrowthShare,
    GrowthTimeStepSet,
    NantesGreenhouses,
)
from distributions.models import TemporalDistribution, Timestep
from inventories.evaluations import ScenarioResult
from inventories.models import (
    InventoryAlgorithm,
    InventoryAlgorithmParameter,
    InventoryAlgorithmParameterValue,
    InventoryAmountShare,
    Scenario,
)
from inventories.tasks import run_inventory_algorithm
from layer_manager.models import Layer
from maps.models import Catchment, GeoDataset, Region
from materials.models import (
    Composition,
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    SampleSeries,
)


@override_settings(DEFAULT_OBJECT_OWNER_USERNAME="standard_user", ADMIN_USERNAME="admin")
class InventoryExecutionIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.default_owner = User.objects.create(username="standard_user")

    def setUp(self):
        average_distribution = TemporalDistribution.objects.filter(name="Average").first()
        if average_distribution is None:
            average_distribution = TemporalDistribution.objects.create(
                owner=self.default_owner,
                name="Average",
                publication_status="published",
            )
        elif average_distribution.owner_id != self.default_owner.id:
            average_distribution.owner = self.default_owner
            average_distribution.save(update_fields=["owner"])

        average_timestep = Timestep.objects.filter(
            distribution=average_distribution,
            name="Average",
        ).first()
        if average_timestep is None:
            Timestep.objects.create(
                owner=self.default_owner,
                distribution=average_distribution,
                name="Average",
            )
        elif average_timestep.owner_id != self.default_owner.id:
            average_timestep.owner = self.default_owner
            average_timestep.save(update_fields=["owner"])

        months_distribution = TemporalDistribution.objects.filter(
            name="Months of the year"
        ).first()
        if months_distribution is None:
            months_distribution = TemporalDistribution.objects.create(
                owner=self.default_owner,
                name="Months of the year",
                publication_status="published",
            )
        elif months_distribution.owner_id != self.default_owner.id:
            months_distribution.owner = self.default_owner
            months_distribution.save(update_fields=["owner"])

        for month in ("January", "February"):
            timestep = Timestep.objects.filter(
                distribution=months_distribution,
                name=month,
            ).first()
            if timestep is None:
                Timestep.objects.create(
                    owner=self.default_owner,
                    distribution=months_distribution,
                    name=month,
                )
            elif timestep.owner_id != self.default_owner.id:
                timestep.owner = self.default_owner
                timestep.save(update_fields=["owner"])

        if not MaterialComponentGroup.objects.filter(name="Total Material").exists():
            MaterialComponentGroup.objects.create(
                owner=self.default_owner,
                name="Total Material",
                publication_status="published",
            )

        for component_name in ("Fresh Matter (FM)", "Other"):
            component = MaterialComponent.objects.filter(name=component_name).first()
            if component is None:
                MaterialComponent.objects.create(
                    owner=self.default_owner,
                    name=component_name,
                    publication_status="published",
                )
            elif component.owner_id != self.default_owner.id:
                component.owner = self.default_owner
                component.save(update_fields=["owner"])

    @classmethod
    def tearDownClass(cls):
        for model_name in list(apps.all_models["layer_manager"]):
            if model_name.startswith("result_of_scenario_"):
                del apps.all_models["layer_manager"][model_name]
        super().tearDownClass()

    def tearDown(self):
        if connection.needs_rollback:
            super().tearDown()
            return

        for layer in list(Layer.objects.all()):
            if layer.table_name not in apps.all_models["layer_manager"]:
                layer.get_feature_collection()
            layer.delete()

        for model_name in list(apps.all_models["layer_manager"]):
            if model_name.startswith("result_of_scenario_"):
                del apps.all_models["layer_manager"][model_name]

        super().tearDown()

    def create_region_and_catchment(self, name, offset=0):
        region = Region.objects.create(
            owner=self.default_owner,
            name=f"{name} Region",
            country="DE",
            publication_status="published",
        )
        region.geom = MultiPolygon(
            Polygon(
                (
                    (offset, offset),
                    (offset, offset + 10),
                    (offset + 10, offset + 10),
                    (offset + 10, offset),
                    (offset, offset),
                ),
                srid=4326,
            ),
            srid=4326,
        )
        region.save()
        catchment = Catchment.objects.create(
            owner=self.default_owner,
            name=f"{name} Catchment",
            region=region,
            parent_region=region,
            publication_status="published",
        )
        scenario = Scenario.objects.create(
            owner=self.default_owner,
            name=f"{name} Scenario",
            region=region,
            catchment=catchment,
            publication_status="published",
        )
        return region, catchment, scenario

    def create_feedstock(self, name):
        material = Material.objects.create(
            owner=self.default_owner,
            name=name,
            publication_status="published",
        )
        return SampleSeries.objects.create(
            owner=self.default_owner,
            name=f"{name} Series",
            material=material,
            publication_status="published",
        )

    def create_geodataset(self, region, model_name, name):
        return GeoDataset.objects.create(
            owner=self.default_owner,
            name=name,
            model_name=model_name,
            region=region,
            publication_status="published",
        )

    def create_algorithm_with_values(
        self,
        *,
        name,
        source_module,
        function_name,
        geodataset,
        feedstock,
        parameter_specs,
    ):
        algorithm = InventoryAlgorithm.objects.create(
            name=name,
            source_module=source_module,
            function_name=function_name,
            geodataset=geodataset,
        )
        algorithm.feedstocks.add(feedstock.material)

        custom_values = {}
        for spec in parameter_specs:
            parameter = InventoryAlgorithmParameter.objects.create(
                descriptive_name=spec["descriptive_name"],
                short_name=spec["short_name"],
                unit=spec.get("unit"),
                is_required=True,
            )
            parameter.inventory_algorithm.add(algorithm)
            value = InventoryAlgorithmParameterValue.objects.create(
                name=spec.get("value_name", spec["descriptive_name"]),
                parameter=parameter,
                value=spec["value"],
                standard_deviation=spec.get("standard_deviation", 0.0),
                default=True,
            )
            custom_values[parameter] = [value]

        return algorithm, custom_values

    def configure_and_run_single_inventory(self, scenario, feedstock, algorithm, values):
        scenario.add_inventory_algorithm(feedstock, algorithm, values)
        config = scenario.configuration_as_dict()
        self.assertIn(feedstock.id, config)
        self.assertEqual(len(config[feedstock.id]), 1)

        module_function, kwargs = next(iter(config[feedstock.id].items()))
        self.assertTrue(run_inventory_algorithm.run(module_function, **kwargs))

        return Layer.objects.get(scenario=scenario, feedstock=feedstock, algorithm=algorithm)

    def build_hamburg_feedstock_profile(self, feedstock, scenario):
        seasonal_distribution = TemporalDistribution.objects.create(
            owner=self.default_owner,
            name="Summer/Winter",
            publication_status="published",
        )
        summer = Timestep.objects.create(
            owner=self.default_owner,
            name="Summer",
            distribution=seasonal_distribution,
        )
        winter = Timestep.objects.create(
            owner=self.default_owner,
            name="Winter",
            distribution=seasonal_distribution,
        )
        macro_components = MaterialComponentGroup.objects.create(
            owner=self.default_owner,
            name="Macro Components",
            publication_status="published",
        )
        biomass = MaterialComponent.objects.create(
            owner=self.default_owner,
            name="Biomass",
            publication_status="published",
        )

        feedstock.add_temporal_distribution(seasonal_distribution)
        summer_values = {summer.id: 0.6, winter.id: 0.4}
        for sample in feedstock.samples.filter(timestep__distribution=seasonal_distribution):
            composition = Composition.objects.create(
                owner=self.default_owner,
                group=macro_components,
                sample=sample,
            )
            composition.add_component(
                biomass,
                average=summer_values[sample.timestep.id],
                standard_deviation=0.0,
            )

        InventoryAmountShare.objects.create(
            owner=self.default_owner,
            scenario=scenario,
            feedstock=feedstock,
            timestep=summer,
            average=0.75,
            standard_deviation=0.0,
        )
        InventoryAmountShare.objects.create(
            owner=self.default_owner,
            scenario=scenario,
            feedstock=feedstock,
            timestep=winter,
            average=0.25,
            standard_deviation=0.0,
        )

        return seasonal_distribution

    def build_hamburg_average_macro_component_profile(self, feedstock, scenario):
        seasonal_distribution = TemporalDistribution.objects.create(
            owner=self.default_owner,
            name="Summer/Winter",
            publication_status="published",
        )
        summer = Timestep.objects.create(
            owner=self.default_owner,
            name="Summer",
            distribution=seasonal_distribution,
        )
        winter = Timestep.objects.create(
            owner=self.default_owner,
            name="Winter",
            distribution=seasonal_distribution,
        )
        average_distribution = TemporalDistribution.objects.get(name="Average")
        average_timestep = Timestep.objects.get(
            distribution=average_distribution,
            name="Average",
        )
        macro_components = MaterialComponentGroup.objects.create(
            owner=self.default_owner,
            name="Macro Components",
            publication_status="published",
        )
        wood_chips = MaterialComponent.objects.create(
            owner=self.default_owner,
            name="Wood Chips",
            publication_status="published",
        )
        leaves = MaterialComponent.objects.create(
            owner=self.default_owner,
            name="Leaves",
            publication_status="published",
        )

        average_sample = feedstock.samples.get(timestep=average_timestep)
        composition = Composition.objects.create(
            owner=self.default_owner,
            group=macro_components,
            sample=average_sample,
        )
        composition.add_component(
            wood_chips,
            average=0.75,
            standard_deviation=0.0,
        )
        composition.add_component(
            leaves,
            average=0.25,
            standard_deviation=0.0,
        )

        InventoryAmountShare.objects.create(
            owner=self.default_owner,
            scenario=scenario,
            feedstock=feedstock,
            timestep=summer,
            average=0.6,
            standard_deviation=0.0,
        )
        InventoryAmountShare.objects.create(
            owner=self.default_owner,
            scenario=scenario,
            feedstock=feedstock,
            timestep=winter,
            average=0.4,
            standard_deviation=0.0,
        )

        return seasonal_distribution

    def test_hamburg_roadside_tree_inventory_example_runs_end_to_end(self):
        region, _catchment, scenario = self.create_region_and_catchment("Hamburg Trees")
        feedstock = self.create_feedstock("Roadside Tree Residues")
        self.build_hamburg_feedstock_profile(feedstock, scenario)

        geodataset = self.create_geodataset(
            region,
            "HamburgRoadsideTrees",
            "Hamburg Roadside Trees",
        )
        algorithm, values = self.create_algorithm_with_values(
            name="Hamburg roadside tree production",
            source_module="flexibi_hamburg",
            function_name="hamburg_roadside_tree_production",
            geodataset=geodataset,
            feedstock=feedstock,
            parameter_specs=[
                {
                    "descriptive_name": "Point yield",
                    "short_name": "point_yield",
                    "unit": "kg/a",
                    "value": 12.0,
                    "standard_deviation": 2.0,
                }
            ],
        )

        HamburgRoadsideTrees.objects.create(geom=Point(1, 1, srid=4326), baumid=1)
        HamburgRoadsideTrees.objects.create(geom=Point(2, 2, srid=4326), baumid=2)

        layer = self.configure_and_run_single_inventory(scenario, feedstock, algorithm, values)
        feature_collection = layer.get_feature_collection()
        charts = ScenarioResult(scenario).get_charts()

        self.assertEqual(feature_collection.objects.count(), 2)
        self.assertTrue(
            layer.layeraggregatedvalue_set.filter(name="Total production", unit="Mg/a").exists()
        )
        self.assertTrue(
            layer.layeraggregateddistribution_set.filter(
                name="Seasonal production per component"
            ).exists()
        )
        self.assertIn("productionPerFeedstockBarChart", charts)
        self.assertIn("seasonalFeedstockBarChart", charts)
        self.assertTrue(charts["seasonalFeedstockBarChart"]["data"])

    def test_hamburg_roadside_tree_inventory_uses_average_macro_components_for_seasonal_chart(self):
        region, _catchment, scenario = self.create_region_and_catchment(
            "Hamburg Trees Average Composition",
            offset=5,
        )
        feedstock = self.create_feedstock("Roadside Tree Residues Average Composition")
        self.build_hamburg_average_macro_component_profile(feedstock, scenario)

        geodataset = self.create_geodataset(
            region,
            "HamburgRoadsideTrees",
            "Hamburg Roadside Trees Average Composition",
        )
        algorithm, values = self.create_algorithm_with_values(
            name="Hamburg roadside tree production average composition",
            source_module="flexibi_hamburg",
            function_name="hamburg_roadside_tree_production",
            geodataset=geodataset,
            feedstock=feedstock,
            parameter_specs=[
                {
                    "descriptive_name": "Point yield",
                    "short_name": "point_yield",
                    "unit": "kg/a",
                    "value": 10.0,
                    "standard_deviation": 1.0,
                }
            ],
        )

        HamburgRoadsideTrees.objects.create(geom=Point(6, 6, srid=4326), baumid=6)
        HamburgRoadsideTrees.objects.create(geom=Point(7, 7, srid=4326), baumid=7)

        layer = self.configure_and_run_single_inventory(scenario, feedstock, algorithm, values)
        seasonal_distribution = layer.layeraggregateddistribution_set.get(
            name="Seasonal production per component"
        )
        charts = ScenarioResult(scenario).get_charts()

        self.assertTrue(seasonal_distribution.serialized)
        self.assertIn("seasonalFeedstockBarChart", charts)
        self.assertTrue(charts["seasonalFeedstockBarChart"]["data"])

    def test_hamburg_roadside_tree_inventory_tolerates_duplicate_group_and_distribution_names(self):
        region, _catchment, scenario = self.create_region_and_catchment(
            "Hamburg Trees Duplicate Defaults",
            offset=10,
        )
        feedstock = self.create_feedstock("Roadside Tree Residues Duplicate Defaults")
        self.build_hamburg_feedstock_profile(feedstock, scenario)

        duplicate_owner = User.objects.create(username="duplicate_defaults_owner")
        MaterialComponentGroup.objects.create(
            owner=duplicate_owner,
            name="Macro Components",
            publication_status="published",
        )
        duplicate_distribution = TemporalDistribution.objects.create(
            owner=duplicate_owner,
            name="Summer/Winter",
            publication_status="published",
        )
        Timestep.objects.create(
            owner=duplicate_owner,
            name="Summer",
            distribution=duplicate_distribution,
        )
        Timestep.objects.create(
            owner=duplicate_owner,
            name="Winter",
            distribution=duplicate_distribution,
        )

        geodataset = self.create_geodataset(
            region,
            "HamburgRoadsideTrees",
            "Hamburg Roadside Trees Duplicate Defaults",
        )
        algorithm, values = self.create_algorithm_with_values(
            name="Hamburg roadside tree production duplicate defaults",
            source_module="flexibi_hamburg",
            function_name="hamburg_roadside_tree_production",
            geodataset=geodataset,
            feedstock=feedstock,
            parameter_specs=[
                {
                    "descriptive_name": "Point yield",
                    "short_name": "point_yield",
                    "unit": "kg/a",
                    "value": 12.0,
                    "standard_deviation": 2.0,
                }
            ],
        )

        HamburgRoadsideTrees.objects.create(geom=Point(11, 11, srid=4326), baumid=11)
        HamburgRoadsideTrees.objects.create(geom=Point(12, 12, srid=4326), baumid=12)

        layer = self.configure_and_run_single_inventory(scenario, feedstock, algorithm, values)
        charts = ScenarioResult(scenario).get_charts()

        self.assertTrue(
            layer.layeraggregateddistribution_set.filter(
                name="Seasonal production per component"
            ).exists()
        )
        self.assertIn("seasonalFeedstockBarChart", charts)
        self.assertTrue(charts["seasonalFeedstockBarChart"]["data"])

    def test_hamburg_park_inventory_example_runs_without_result_errors(self):
        region, _catchment, scenario = self.create_region_and_catchment(
            "Hamburg Parks",
            offset=20,
        )
        feedstock = self.create_feedstock("Park Residues")

        geodataset = self.create_geodataset(
            region,
            "HamburgGreenAreas",
            "Hamburg Green Areas",
        )
        algorithm, values = self.create_algorithm_with_values(
            name="Hamburg park production",
            source_module="flexibi_hamburg",
            function_name="hamburg_park_production",
            geodataset=geodataset,
            feedstock=feedstock,
            parameter_specs=[
                {
                    "descriptive_name": "Area yield",
                    "short_name": "area_yield",
                    "unit": "kg/m²",
                    "value": 1.5,
                    "standard_deviation": 0.0,
                }
            ],
        )

        HamburgGreenAreas.objects.create(
            geom=MultiPolygon(
                Polygon(
                    ((21, 21), (21, 24), (24, 24), (24, 21), (21, 21)),
                    srid=4326,
                ),
                srid=4326,
            ),
            anlagenname="Test Park",
            belegenheit="Central",
            gruenart="Park",
            nutzcode=1,
        )

        layer = self.configure_and_run_single_inventory(scenario, feedstock, algorithm, values)
        feature_collection = layer.get_feature_collection()
        charts = ScenarioResult(scenario).get_charts()

        self.assertEqual(feature_collection.objects.count(), 1)
        self.assertTrue(layer.layeraggregatedvalue_set.filter(name="Total area").exists())
        self.assertIn("productionPerFeedstockBarChart", charts)
        self.assertIn("seasonalFeedstockBarChart", charts)

    def test_nantes_greenhouse_inventory_example_runs_end_to_end(self):
        region, _catchment, scenario = self.create_region_and_catchment(
            "Nantes Greenhouses",
            offset=40,
        )
        feedstock = self.create_feedstock("Tomato Residues")
        months = TemporalDistribution.objects.get(name="Months of the year")
        january = Timestep.objects.get(distribution=months, name="January")
        february = Timestep.objects.get(distribution=months, name="February")
        biomass = MaterialComponent.objects.create(
            owner=self.default_owner,
            name="Greenhouse Biomass",
            publication_status="published",
        )

        culture = Culture.objects.create(
            owner=self.default_owner,
            name="Tomato",
            residue=feedstock,
            publication_status="published",
        )
        greenhouse = Greenhouse.objects.create(
            owner=self.default_owner,
            name="Heated tomato greenhouse",
            heated=True,
            lighted=False,
            high_wire=True,
            above_ground=False,
            publication_status="published",
        )
        growth_cycle = GreenhouseGrowthCycle.objects.create(
            owner=self.default_owner,
            cycle_number=1,
            culture=culture,
            greenhouse=greenhouse,
        )
        january_set = GrowthTimeStepSet.objects.create(
            owner=self.default_owner,
            timestep=january,
            growth_cycle=growth_cycle,
        )
        february_set = GrowthTimeStepSet.objects.create(
            owner=self.default_owner,
            timestep=february,
            growth_cycle=growth_cycle,
        )
        GrowthShare.objects.create(
            owner=self.default_owner,
            component=biomass,
            timestepset=january_set,
            average=1.2,
            standard_deviation=0.0,
        )
        GrowthShare.objects.create(
            owner=self.default_owner,
            component=biomass,
            timestepset=february_set,
            average=0.8,
            standard_deviation=0.0,
        )

        NantesGreenhouses.objects.create(
            geom=Point(41, 41, srid=4326),
            culture_1="Tomato",
            surface_ha=2.5,
            heated=True,
            lighted=False,
            high_wire=True,
            above_ground=False,
        )

        geodataset = self.create_geodataset(
            region,
            "NantesGreenhouses",
            "Nantes Greenhouses",
        )
        algorithm, values = self.create_algorithm_with_values(
            name="Nantes greenhouse production",
            source_module="flexibi_nantes",
            function_name="nantes_greenhouse_production",
            geodataset=geodataset,
            feedstock=feedstock,
            parameter_specs=[
                {
                    "descriptive_name": "Heated",
                    "short_name": "heated",
                    "value": 1,
                    "standard_deviation": 0.0,
                },
                {
                    "descriptive_name": "Lit",
                    "short_name": "lit",
                    "value": 0,
                    "standard_deviation": 0.0,
                },
                {
                    "descriptive_name": "High wire",
                    "short_name": "high_wire",
                    "value": 1,
                    "standard_deviation": 0.0,
                },
                {
                    "descriptive_name": "Above ground",
                    "short_name": "above_ground",
                    "value": 0,
                    "standard_deviation": 0.0,
                },
            ],
        )

        layer = self.configure_and_run_single_inventory(scenario, feedstock, algorithm, values)
        feature_collection = layer.get_feature_collection()
        charts = ScenarioResult(scenario).get_charts()

        self.assertEqual(feature_collection.objects.count(), 1)
        self.assertTrue(
            layer.layeraggregatedvalue_set.filter(
                name="Number of considered greenhouses",
                value=1,
            ).exists()
        )
        self.assertTrue(
            layer.layeraggregateddistribution_set.filter(
                name="Seasonal production per component"
            ).exists()
        )
        self.assertIn("productionPerFeedstockBarChart", charts)
        self.assertIn("seasonalFeedstockBarChart", charts)
        self.assertTrue(charts["seasonalFeedstockBarChart"]["data"])
