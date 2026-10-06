"""Set up the Sötåsen grass-to-protein demo inventory.

Creates (or updates) the private objects needed to evaluate the Sötåsen
grass-to-protein demo scenario against production reference objects:

- an InventoryAlgorithm linked to GeoDataset 49 ("Sötåsen Agricultural Land
  Use", a local-relation dataset backed by ``raw_data.sotasen_land_use``),
  material 2341 ("Clover grass") and bibliography source 21912 (Thomas 2025);
- the three required algorithm parameters (dry matter yield, crude protein
  fraction, protein recovery fraction) with their selectable values and
  defaults;
- a private Scenario "Sötåsen grass-to-protein demo (Thomas 2025)" for region
  30994 (Töreboda) and catchment 31106 (Töreboda (1473)), configured with the
  material as feedstock and the default parameter values.

The command is atomic and idempotent. It never publishes objects or submits
them for review. It fails before writing anything if a referenced production
object is missing or does not match the expected name/type.

Usage::

    python manage.py setup_sotasen_demo_inventory --owner <username>
    python manage.py setup_sotasen_demo_inventory --owner <username> --dry-run
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from bibliography.models import Source
from inventories.models import (
    InventoryAlgorithm,
    InventoryAlgorithmParameter,
    InventoryAlgorithmParameterValue,
    Scenario,
    ScenarioInventoryConfiguration,
    ScenarioStatus,
)
from maps.models import Catchment, GeoDataset, Region
from materials.models import Material

User = get_user_model()

GEODATASET_ID = 49
GEODATASET_NAME = "Sötåsen Agricultural Land Use"
MATERIAL_ID = 2341
MATERIAL_NAME = "Clover grass"
SOURCE_ID = 21912
SOURCE_CITATION_KEY = "Thomas 2025"
REGION_ID = 30994
REGION_NAME = "Töreboda"
CATCHMENT_ID = 31106
CATCHMENT_NAME = "Töreboda (1473)"

ALGORITHM_NAME = "Sötåsen grass-to-protein"
ALGORITHM_MODULE = "sources.sotasen.inventory.algorithms"
ALGORITHM_FUNCTION = "sotasen_grass_to_protein"
SCENARIO_NAME = "Sötåsen grass-to-protein demo (Thomas 2025)"
DEMO_ASSUMPTION_SOURCE = "Demo assumption"

ALGORITHM_DESCRIPTION = (
    "Estimates annual grassland biomass and recovered protein production for "
    "the Sötåsen demonstration site from the 'Sötåsen Agricultural Land Use' "
    "dataset (land_use = 'Grassland'). The dry matter yield default "
    "(9.0 t DM/ha/a) and the crude protein fraction default (20% of DM) are "
    "demo assumptions, not measured values. Selectable protein recovery "
    "fractions: 4% and 20% are the endpoints of the recovery range observed "
    "in the project; 12% is a midpoint demo assumption, not a measured mean; "
    "42% is a literature benchmark reported in Thomas 2025, 'Biorefinery "
    "Modules (Swedish showcase)'."
)

SCENARIO_DESCRIPTION = (
    "Demo scenario evaluating a grass-to-protein pathway for clover grass "
    "grassland at the Sötåsen research farm (Töreboda, Sweden), after "
    "Thomas 2025, 'Biorefinery Modules (Swedish showcase)'. "
    "Reference measurements reported in the study (not used as algorithm "
    "inputs): 3.16 t DM were processed in 2022-2024, equivalent to about "
    "0.35 ha of grassland; across five batches the recovered crude protein "
    "was 8.1 +/- 3.8 kg and the reported recovery was 4-20%. Quantified "
    "biogas and biochar pathways were outside the study scope."
)

SELECTION = InventoryAlgorithmParameterValue.ValueType.SELECTION
NUMERIC = InventoryAlgorithmParameterValue.ValueType.NUMERIC

PARAMETERS = (
    {
        "short_name": "dry_matter_yield",
        "descriptive_name": "Dry matter yield",
        "unit": "t DM/ha/a",
        "description": (
            "Annual dry matter yield per hectare of grassland. The default "
            "9.0 t DM/ha/a is a demo assumption, not a measured value."
        ),
        "values": [
            {
                "name": "9.0 t DM/ha/a",
                "type": NUMERIC,
                "value": 9.0,
                "default": True,
                "source": DEMO_ASSUMPTION_SOURCE,
                "description": "Demo assumption for the Sötåsen showcase.",
            },
        ],
    },
    {
        "short_name": "crude_protein_fraction",
        "descriptive_name": "Crude protein fraction",
        "unit": "kg/kg DM",
        "description": (
            "Crude protein content of the harvested grassland biomass as a "
            "fraction of dry matter. The default 0.20 (20% CP) is a demo "
            "assumption, not a measured value."
        ),
        "values": [
            {
                "name": "0.20 (20% CP)",
                "type": NUMERIC,
                "value": 0.20,
                "default": True,
                "source": DEMO_ASSUMPTION_SOURCE,
                "description": "Demo assumption for the Sötåsen showcase.",
            },
        ],
    },
    {
        "short_name": "protein_recovery_fraction",
        "descriptive_name": "Protein recovery fraction",
        "unit": "fraction",
        "description": (
            "Fraction of the biomass crude protein recovered into the protein "
            "product. 4% and 20% are the endpoints of the range observed in "
            "the project; 12% is a midpoint demo assumption, not a measured "
            "mean; 42% is a literature benchmark reported in Thomas 2025."
        ),
        "values": [
            {
                "name": "4% (observed project low)",
                "type": SELECTION,
                "value": 0.04,
                "default": False,
                "source": SOURCE_CITATION_KEY,
                "description": "Lower endpoint of the recovery range observed in the project.",
            },
            {
                "name": "12% (midpoint)",
                "type": SELECTION,
                "value": 0.12,
                "default": True,
                "source": DEMO_ASSUMPTION_SOURCE,
                "description": (
                    "Midpoint demo assumption; not a measured mean of the "
                    "observed 4-20% recovery range."
                ),
            },
            {
                "name": "20% (observed project high)",
                "type": SELECTION,
                "value": 0.20,
                "default": False,
                "source": SOURCE_CITATION_KEY,
                "description": "Upper endpoint of the recovery range observed in the project.",
            },
            {
                "name": "42% (literature benchmark)",
                "type": SELECTION,
                "value": 0.42,
                "default": False,
                "source": SOURCE_CITATION_KEY,
                "description": "Literature benchmark reported in Thomas 2025.",
            },
        ],
    },
)


class Command(BaseCommand):
    help = "Create/update the private Sötåsen grass-to-protein demo inventory objects."

    def add_arguments(self, parser):
        parser.add_argument(
            "--owner",
            required=True,
            help="Username that will own the created sample series and scenario.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate references and report intended actions without writing.",
        )

    def handle(self, *args, **options):
        try:
            owner = User.objects.get(username=options["owner"])
        except User.DoesNotExist:
            raise CommandError(f"User '{options['owner']}' does not exist.") from None

        references = self._load_references()

        self._report = []
        with transaction.atomic():
            self._apply(owner, references)
            if options["dry_run"]:
                transaction.set_rollback(True)

        for line in self._report:
            self.stdout.write(line)
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("DRY RUN: no changes were written."))
        else:
            self.stdout.write(self.style.SUCCESS("Sötåsen demo inventory is set up."))

    def _load_references(self):
        geodataset = self._get_or_fail(GeoDataset, GEODATASET_ID, "GeoDataset")
        self._check_attribute(
            geodataset, "name", GEODATASET_NAME, f"GeoDataset {GEODATASET_ID}"
        )
        runtime_configuration = geodataset.get_runtime_configuration()
        if (
            runtime_configuration is None
            or runtime_configuration.backend_type != "local_relation"
        ):
            raise CommandError(
                f"GeoDataset {GEODATASET_ID} ('{geodataset.name}') is not a "
                "local_relation dataset."
            )

        material = self._get_or_fail(Material, MATERIAL_ID, "Material")
        self._check_attribute(
            material, "name", MATERIAL_NAME, f"Material {MATERIAL_ID}"
        )

        source = self._get_or_fail(Source, SOURCE_ID, "Source")
        self._check_attribute(
            source,
            "citation_key",
            SOURCE_CITATION_KEY,
            f"Source {SOURCE_ID}",
        )

        region = self._get_or_fail(Region, REGION_ID, "Region")
        self._check_attribute(region, "name", REGION_NAME, f"Region {REGION_ID}")

        catchment = self._get_or_fail(Catchment, CATCHMENT_ID, "Catchment")
        self._check_attribute(
            catchment, "name", CATCHMENT_NAME, f"Catchment {CATCHMENT_ID}"
        )
        if catchment.region_id != region.id:
            raise CommandError(
                f"Catchment {CATCHMENT_ID} ('{catchment.name}') does not belong "
                f"to Region {REGION_ID} ('{region.name}')."
            )

        return {
            "geodataset": geodataset,
            "material": material,
            "source": source,
            "region": region,
            "catchment": catchment,
        }

    @staticmethod
    def _get_or_fail(model, pk, label):
        obj = model.objects.filter(pk=pk).first()
        if obj is None:
            raise CommandError(
                f"{label} with id {pk} does not exist. The Sötåsen demo "
                "inventory requires this production object."
            )
        return obj

    @staticmethod
    def _check_attribute(obj, attribute, expected, label):
        actual = getattr(obj, attribute) or ""
        if actual.strip().casefold() != expected.strip().casefold():
            raise CommandError(
                f"{label} has unexpected {attribute} '{actual}' "
                f"(expected '{expected}')."
            )

    def _log(self, verb, obj):
        self._report.append(f"{verb}: {obj}")

    def _apply(self, owner, references):
        algorithm = self._ensure_algorithm(
            references["geodataset"], references["material"], references["source"]
        )
        parameters = self._ensure_parameters(algorithm)
        scenario = self._ensure_scenario(
            owner, references["region"], references["catchment"]
        )
        self._ensure_scenario_configuration(scenario, references["material"], algorithm)
        self._validate_configuration(scenario, parameters)

    def _ensure_algorithm(self, geodataset, material, source):
        algorithm, created = InventoryAlgorithm.objects.update_or_create(
            source_module=ALGORITHM_MODULE,
            function_name=ALGORITHM_FUNCTION,
            defaults={
                "name": ALGORITHM_NAME,
                "description": ALGORITHM_DESCRIPTION,
                "geodataset": geodataset,
                "source": source,
            },
        )
        algorithm.feedstocks.set([material])
        self._log(
            "Created" if created else "Updated", f"InventoryAlgorithm '{algorithm}'"
        )
        return algorithm

    def _ensure_parameters(self, algorithm):
        parameters = {}
        for spec in PARAMETERS:
            parameter = InventoryAlgorithmParameter.objects.filter(
                short_name=spec["short_name"], inventory_algorithm=algorithm
            ).first()
            fields = {
                "descriptive_name": spec["descriptive_name"],
                "unit": spec["unit"],
                "description": spec["description"],
                "is_required": True,
            }
            if parameter is None:
                parameter = InventoryAlgorithmParameter.objects.create(
                    short_name=spec["short_name"], **fields
                )
                parameter.inventory_algorithm.add(algorithm)
                self._log("Created", f"Parameter '{parameter}'")
            else:
                changed = [
                    key
                    for key, value in fields.items()
                    if getattr(parameter, key) != value
                ]
                if changed:
                    for key in changed:
                        setattr(parameter, key, fields[key])
                    parameter.save(update_fields=changed)
                self._log(
                    "Updated" if changed else "Unchanged", f"Parameter '{parameter}'"
                )

            self._ensure_parameter_values(parameter, spec["values"])
            parameters[spec["short_name"]] = parameter
        return parameters

    def _ensure_parameter_values(self, parameter, value_specs):
        expected = set()
        for spec in value_specs:
            value_obj = InventoryAlgorithmParameterValue.objects.filter(
                parameter=parameter, value=spec["value"]
            ).first()
            fields = {
                "name": spec["name"],
                "type": spec["type"],
                "description": spec["description"],
                "value": spec["value"],
                "standard_deviation": None,
                "source": spec["source"],
            }
            if value_obj is None:
                value_obj = InventoryAlgorithmParameterValue.objects.create(
                    parameter=parameter, default=spec["default"], **fields
                )
                self._log("Created", f"Parameter value '{value_obj.name}'")
            else:
                changed = [
                    key
                    for key, value in fields.items()
                    if getattr(value_obj, key) != value
                ]
                if changed:
                    for key in changed:
                        setattr(value_obj, key, fields[key])
                    value_obj.save(update_fields=changed)
                self._log(
                    "Updated" if changed else "Unchanged",
                    f"Parameter value '{value_obj.name}'",
                )
            expected.add(value_obj.id)

        stale = InventoryAlgorithmParameterValue.objects.filter(
            parameter=parameter
        ).exclude(id__in=expected)
        for value_obj in stale:
            self._log("Removed", f"stale parameter value '{value_obj}'")
        stale.delete()

        default_value = next(spec["value"] for spec in value_specs if spec["default"])
        InventoryAlgorithmParameterValue.objects.filter(
            parameter=parameter, default=True
        ).exclude(value=default_value).update(default=False)
        InventoryAlgorithmParameterValue.objects.filter(
            parameter=parameter, value=default_value, default=False
        ).update(default=True)

    def _ensure_scenario(self, owner, region, catchment):
        scenario, created = Scenario.objects.get_or_create(
            name=SCENARIO_NAME,
            owner=owner,
            defaults={
                "region": region,
                "catchment": catchment,
                "description": SCENARIO_DESCRIPTION,
                "publication_status": Scenario.STATUS_PRIVATE,
            },
        )
        if not created:
            # The related status row must exist before save() triggers the
            # post_save signal that flips the scenario status to CHANGED.
            ScenarioStatus.objects.get_or_create(scenario=scenario)
            scenario.region = region
            scenario.catchment = catchment
            scenario.description = SCENARIO_DESCRIPTION
            scenario.save()
        self._log("Created" if created else "Updated", f"Scenario '{scenario}'")
        return scenario

    def _ensure_scenario_configuration(self, scenario, material, algorithm):
        existing = ScenarioInventoryConfiguration.objects.filter(
            scenario=scenario,
            feedstock=material,
            inventory_algorithm=algorithm,
        )
        if existing.exists():
            existing.delete()
        scenario.add_inventory_algorithm(feedstock=material, algorithm=algorithm)
        self._log(
            "Configured",
            f"Scenario '{scenario}' with feedstock '{material}' "
            f"and algorithm '{algorithm}'",
        )

    @staticmethod
    def _validate_configuration(scenario, parameters):
        scenario.is_valid_configuration()
        configured_values = dict(
            ScenarioInventoryConfiguration.objects.filter(
                scenario=scenario
            ).values_list("inventory_parameter__short_name", "inventory_value__value")
        )
        for spec in PARAMETERS:
            parameter = parameters[spec["short_name"]]
            expected = next(
                spec_value["value"]
                for spec_value in spec["values"]
                if spec_value["default"]
            )
            if configured_values.get(parameter.short_name) != expected:
                raise CommandError(
                    f"Scenario is not configured with the default value of "
                    f"parameter '{parameter.short_name}'."
                )
