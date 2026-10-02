"""Tests for the collapsed-identity cleanup in the feedstock→Material
migrations (inventories 0009 / layer_manager 0004).

The functions are exercised directly with the real app registry: the state
they expect (feedstock already repointed to the material, the old series
preserved in ``sample_series``) is built straight in the test database.
"""

import importlib

from django.apps import apps
from django.db import connection
from django.test import TestCase

from inventories.models import (
    GeoDataset,
    InventoryAlgorithm,
    InventoryAlgorithmParameter,
    InventoryAlgorithmParameterValue,
    Scenario,
    ScenarioInventoryConfiguration,
)
from layer_manager.models import Layer
from maps.models import Region
from materials.models import Material, SampleSeries

config_dedup = importlib.import_module(
    "inventories.migrations.0009_feedstock_material"
).deduplicate_collapsed_configurations
layer_dedup = importlib.import_module(
    "layer_manager.migrations.0004_layer_feedstock_material"
).deduplicate_collapsed_layers


class _SchemaEditorShim:
    """Minimal stand-in for the ``schema_editor`` argument.

    The real Postgres schema editor toggles constraint deferral on
    enter/exit, which corrupts the enclosing TestCase transaction — all the
    dedup functions need is ``execute()``.
    """

    def execute(self, sql):
        with connection.cursor() as cursor:
            cursor.execute(sql)


class MigrationDedupTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name="Dedup Region")
        cls.scenario = Scenario.objects.create(name="Dedup Scenario", region=cls.region)
        cls.geodataset = GeoDataset.objects.create(
            name="Dedup Dataset", region=cls.region
        )
        cls.algorithm = InventoryAlgorithm.objects.create(
            name="Dedup Algorithm", geodataset=cls.geodataset
        )
        cls.material = Material.objects.create(name="Dedup Material")
        cls.series_a = SampleSeries.objects.create(material=cls.material, name="A")
        cls.series_b = SampleSeries.objects.create(material=cls.material, name="B")
        cls.parameter = InventoryAlgorithmParameter.objects.create(
            descriptive_name="Yield", short_name="yield"
        )
        cls.parameter.inventory_algorithm.add(cls.algorithm)

    def _config(self, series, value_number, parameter=None, feedstock=None):
        value = InventoryAlgorithmParameterValue.objects.create(
            name=f"v{value_number}", parameter=self.parameter, value=value_number
        )
        return ScenarioInventoryConfiguration.objects.create(
            scenario=self.scenario,
            feedstock=feedstock or self.material,
            sample_series=series,
            geodataset=self.geodataset,
            inventory_algorithm=self.algorithm,
            inventory_parameter=parameter or self.parameter,
            inventory_value=value,
        )

    def _run_config_dedup(self):
        config_dedup(apps, _SchemaEditorShim())

    def test_duplicate_parameter_rows_collapse_to_lowest_series(self):
        winner = self._config(self.series_a, 1.0)
        self._config(self.series_b, 2.0)

        self._run_config_dedup()

        remaining = ScenarioInventoryConfiguration.objects.filter(
            scenario=self.scenario, inventory_algorithm=self.algorithm
        )
        self.assertEqual([winner.id], [row.id for row in remaining])
        self.assertEqual(remaining.get().sample_series, self.series_a)
        self.scenario.is_valid_configuration()

    def test_layer_temporal_profile_decides_the_canonical_series(self):
        self._config(self.series_a, 1.0)
        loser_value = self._config(self.series_b, 2.0)
        # A surviving result layer carries series B's provenance — its
        # configuration row must win so plan and layer agree.
        Layer.objects.create(
            name="Result",
            geom_type="Polygon",
            table_name="dedup_canonical_layer",
            scenario=self.scenario,
            feedstock=self.material,
            sample_series=self.series_b,
            algorithm=self.algorithm,
        )

        self._run_config_dedup()

        remaining = ScenarioInventoryConfiguration.objects.get(
            scenario=self.scenario, inventory_algorithm=self.algorithm
        )
        self.assertEqual(remaining.id, loser_value.id)
        self.assertEqual(remaining.sample_series, self.series_b)

    def test_distinct_parameters_all_survive_under_one_series(self):
        other_parameter = InventoryAlgorithmParameter.objects.create(
            descriptive_name="Share", short_name="share"
        )
        other_parameter.inventory_algorithm.add(self.algorithm)
        self._config(self.series_a, 1.0)
        self._config(self.series_a, 3.0, parameter=other_parameter)
        self._config(self.series_b, 2.0)

        self._run_config_dedup()

        rows = ScenarioInventoryConfiguration.objects.filter(
            scenario=self.scenario, inventory_algorithm=self.algorithm
        )
        self.assertEqual(2, rows.count())
        self.assertEqual({self.series_a.id}, {row.sample_series_id for row in rows})
        self.scenario.is_valid_configuration()

    def test_untouched_groups_stay_unchanged(self):
        self._config(self.series_a, 1.0)
        other_material = Material.objects.create(name="Other Material")
        other_series = SampleSeries.objects.create(material=other_material, name="C")
        self._config(other_series, 5.0, feedstock=other_material)

        self._run_config_dedup()

        self.assertEqual(
            2,
            ScenarioInventoryConfiguration.objects.filter(
                scenario=self.scenario
            ).count(),
        )


class LayerMigrationDedupTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name="Layer Region")
        cls.scenario = Scenario.objects.create(name="Layer Scenario", region=cls.region)
        cls.geodataset = GeoDataset.objects.create(
            name="Layer Dataset", region=cls.region
        )
        cls.algorithm = InventoryAlgorithm.objects.create(
            name="Layer Algorithm", geodataset=cls.geodataset
        )
        cls.material = Material.objects.create(name="Layer Material")
        cls.series = SampleSeries.objects.create(material=cls.material, name="S")

    def _layer(self, table_name, sample_series=None):
        return Layer._base_manager.create(
            name="Result",
            geom_type="Polygon",
            table_name=table_name,
            scenario=self.scenario,
            feedstock=self.material,
            sample_series=sample_series,
            algorithm=self.algorithm,
        )

    def test_collapsed_layers_keep_temporal_profile_and_drop_table(self):
        self._layer("dedup_loser_table")
        keeper = self._layer("dedup_keeper_table", sample_series=self.series)
        with connection.cursor() as cursor:
            cursor.execute('CREATE TABLE "dedup_loser_table" (id integer)')

        layer_dedup(apps, _SchemaEditorShim())

        self.assertQuerySetEqual(
            Layer._base_manager.filter(scenario=self.scenario), [keeper]
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('dedup_loser_table')")
            self.assertIsNone(cursor.fetchone()[0])

    def test_single_layer_is_untouched(self):
        layer = self._layer("dedup_single_table")

        layer_dedup(apps, _SchemaEditorShim())

        self.assertTrue(Layer._base_manager.filter(id=layer.id).exists())
