import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from bibliography.models import Source
from inventories.models import (
    InventoryAlgorithm,
    InventoryAlgorithmParameter,
    InventoryAlgorithmParameterValue,
    Scenario,
    ScenarioInventoryConfiguration,
)
from maps.models import (
    Catchment,
    GeoDataset,
    GeoDatasetRuntimeConfiguration,
    Region,
)
from materials.models import Material, SampleSeries
from sources.sotasen.management.commands import (
    setup_sotasen_demo_inventory as command_module,
)

User = get_user_model()

COMMAND = "setup_sotasen_demo_inventory"


class SetupSotasenDemoInventoryTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="demo_owner")
        cls.region = Region.objects.create(
            name="Töreboda", country="SE", publication_status="published"
        )
        cls.catchment = Catchment.objects.create(
            name="Töreboda (1473)",
            region=cls.region,
            publication_status="published",
        )
        cls.material = Material.objects.create(
            name="Clover grass", publication_status="published"
        )
        cls.source = Source.objects.create(
            title="Biorefinery Modules (Swedish showcase)",
            citation_key="Thomas 2025",
            type="report",
            year=2025,
            publication_status="published",
        )
        cls.geodataset = GeoDataset.objects.create(
            name="Sötåsen Agricultural Land Use",
            region=cls.region,
            publication_status="published",
        )
        GeoDatasetRuntimeConfiguration.objects.create(
            dataset=cls.geodataset,
            backend_type="local_relation",
            schema_name="raw_data",
            relation_name="sotasen_land_use",
            geometry_column="geom",
            primary_key_column="fid",
            label_field="land_use",
        )

    def run_command(self, *args, **kwargs):
        out = io.StringIO()
        patches = {
            "GEODATASET_ID": self.geodataset.id,
            "MATERIAL_ID": self.material.id,
            "SOURCE_ID": self.source.id,
            "REGION_ID": self.region.id,
            "CATCHMENT_ID": self.catchment.id,
        }
        with patch.multiple(command_module, **patches):
            call_command(
                COMMAND, *args, owner=self.owner.username, stdout=out, **kwargs
            )
        return out.getvalue()

    def test_owner_is_required(self):
        with self.assertRaises(CommandError):
            call_command(COMMAND)

    def test_unknown_owner_fails(self):
        with self.assertRaises(CommandError):
            call_command(COMMAND, owner="no_such_user")

    def test_creates_private_objects_owned_by_owner(self):
        self.run_command()

        self.assertFalse(SampleSeries.objects.exists())

        scenario = Scenario.objects.get(
            name="Sötåsen grass-to-protein demo (Thomas 2025)"
        )
        self.assertEqual(scenario.owner, self.owner)
        self.assertEqual(scenario.region_id, self.region.id)
        self.assertEqual(scenario.catchment_id, self.catchment.id)
        self.assertEqual(scenario.publication_status, "private")
        self.assertIsNone(scenario.submitted_at)

    def test_scenario_description_mentions_study_scope_and_measurements(self):
        self.run_command()
        scenario = Scenario.objects.get(
            name="Sötåsen grass-to-protein demo (Thomas 2025)"
        )
        self.assertIn("3.16 t DM", scenario.description)
        self.assertIn("0.35 ha", scenario.description)
        self.assertIn("8.1 +/- 3.8 kg", scenario.description)
        self.assertIn("4-20%", scenario.description)
        self.assertIn("biogas", scenario.description)
        self.assertIn("biochar", scenario.description)
        self.assertIn("outside the study scope", scenario.description)

    def test_creates_algorithm_linked_to_references(self):
        self.run_command()

        algorithm = InventoryAlgorithm.objects.get(
            source_module="sources.sotasen.inventory.algorithms",
            function_name="sotasen_grass_to_protein",
        )
        self.assertEqual(algorithm.geodataset_id, self.geodataset.id)
        self.assertEqual(algorithm.source_id, self.source.id)
        self.assertEqual(list(algorithm.feedstocks.all()), [self.material])

    def test_creates_required_parameters_and_values(self):
        self.run_command()

        algorithm = InventoryAlgorithm.objects.get(
            function_name="sotasen_grass_to_protein"
        )
        parameters = {
            p.short_name: p
            for p in InventoryAlgorithmParameter.objects.filter(
                inventory_algorithm=algorithm
            )
        }
        self.assertEqual(
            set(parameters),
            {
                "dry_matter_yield",
                "crude_protein_fraction",
                "protein_recovery_fraction",
            },
        )
        for parameter in parameters.values():
            self.assertTrue(parameter.is_required)

        recovery_values = {
            v.value: v
            for v in InventoryAlgorithmParameterValue.objects.filter(
                parameter=parameters["protein_recovery_fraction"]
            )
        }
        self.assertEqual(set(recovery_values), {0.04, 0.12, 0.20, 0.42})
        self.assertTrue(recovery_values[0.12].default)
        self.assertFalse(recovery_values[0.42].default)

        self.assertTrue(
            InventoryAlgorithmParameterValue.objects.get(
                parameter=parameters["dry_matter_yield"]
            ).default
        )
        self.assertEqual(
            InventoryAlgorithmParameterValue.objects.get(
                parameter=parameters["crude_protein_fraction"]
            ).value,
            0.20,
        )

    def test_value_names_do_not_embed_the_citation(self):
        """The UI appends ` (source)` to option labels, so names must not
        repeat the citation. Only study-reported values cite Thomas 2025;
        demo assumptions are marked as such."""
        self.run_command()

        values = InventoryAlgorithmParameterValue.objects.filter(
            parameter__inventory_algorithm__function_name="sotasen_grass_to_protein"
        )
        for value in values:
            self.assertNotIn("Thomas 2025", value.name)
        self.assertEqual(
            {
                v.value: v.source
                for v in values.filter(
                    parameter__short_name="protein_recovery_fraction"
                )
            },
            {
                0.04: "Thomas 2025",
                0.12: "Demo assumption",
                0.20: "Thomas 2025",
                0.42: "Thomas 2025",
            },
        )

    def test_rerun_does_not_demote_published_scenario(self):
        self.run_command()
        scenario = Scenario.objects.get(
            name="Sötåsen grass-to-protein demo (Thomas 2025)"
        )
        scenario.publication_status = "published"
        scenario.save()

        self.run_command()

        scenario.refresh_from_db()
        self.assertEqual(scenario.publication_status, "published")

    def test_scenario_configuration_uses_defaults(self):
        self.run_command()

        scenario = Scenario.objects.get(
            name="Sötåsen grass-to-protein demo (Thomas 2025)"
        )
        config = ScenarioInventoryConfiguration.objects.filter(
            scenario=scenario, feedstock=self.material
        )
        self.assertEqual(config.count(), 3)
        values = {
            entry.inventory_parameter.short_name: entry.inventory_value.value
            for entry in config
        }
        self.assertEqual(
            values,
            {
                "dry_matter_yield": 9.0,
                "crude_protein_fraction": 0.20,
                "protein_recovery_fraction": 0.12,
            },
        )
        scenario.is_valid_configuration()

    def test_idempotent_second_run(self):
        self.run_command()
        counts_before = {
            model: model.objects.count()
            for model in (
                SampleSeries,
                InventoryAlgorithm,
                InventoryAlgorithmParameter,
                InventoryAlgorithmParameterValue,
                Scenario,
                ScenarioInventoryConfiguration,
            )
        }

        out = self.run_command()

        self.assertIn("Updated", out)
        for model, count in counts_before.items():
            self.assertEqual(model.objects.count(), count, model.__name__)

        scenario = Scenario.objects.get(
            name="Sötåsen grass-to-protein demo (Thomas 2025)"
        )
        scenario.is_valid_configuration()

    def test_dry_run_leaves_database_unchanged(self):
        def snapshot():
            return {
                model: model.objects.count()
                for model in (
                    SampleSeries,
                    InventoryAlgorithm,
                    InventoryAlgorithmParameter,
                    InventoryAlgorithmParameterValue,
                    Scenario,
                    ScenarioInventoryConfiguration,
                )
            }

        before = snapshot()
        out = self.run_command(dry_run=True)

        self.assertEqual(snapshot(), before)
        self.assertIn("DRY RUN", out)
        self.assertIn("Created", out)
        self.assertFalse(
            Scenario.objects.filter(
                name="Sötåsen grass-to-protein demo (Thomas 2025)"
            ).exists()
        )

    def test_missing_reference_fails_without_writes(self):
        self.material.delete()
        with self.assertRaises(CommandError) as ctx:
            self.run_command()
        self.assertIn(str(self.material.id), str(ctx.exception))
        self.assertFalse(SampleSeries.objects.exists())
        self.assertFalse(
            Scenario.objects.filter(
                name="Sötåsen grass-to-protein demo (Thomas 2025)"
            ).exists()
        )

    def test_reference_with_wrong_name_fails(self):
        self.geodataset.name = "Unrelated dataset"
        self.geodataset.save()
        with self.assertRaises(CommandError) as ctx:
            self.run_command()
        self.assertIn("unexpected", str(ctx.exception).lower())

    def test_non_local_relation_dataset_fails(self):
        self.geodataset.runtime_configuration.backend_type = "legacy_model"
        self.geodataset.runtime_configuration.save()
        with self.assertRaises(CommandError) as ctx:
            self.run_command()
        self.assertIn("local_relation", str(ctx.exception))

    def test_catchment_outside_region_fails(self):
        other_region = Region.objects.create(name="Mariestad", country="SE")
        self.catchment.region = other_region
        self.catchment.save()
        with self.assertRaises(CommandError):
            self.run_command()
