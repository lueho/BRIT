import importlib
import pkgutil

from celery.result import AsyncResult
from celery.states import READY_STATES
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.query import QuerySet
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse

import sources
from bibliography.models import Source
from distributions.models import Timestep
from maps.models import Catchment, GeoDataset, Region
from materials.models import Material, SampleSeries
from utils.object_management.models import NamedUserCreatedObject

from .exceptions import BlockedRunningScenario


class InventoryAlgorithm(models.Model):
    """
    Links functions that are defined in the InventoryMixin to the corresponding geodatasets and feedstocks in the
    database. This model is for configuration by admins and must not be available to users. Customization by users can
    be done in InventoryAlgorithmParameter and InventoryAlgorithmParameterValue.
    """

    SOURCE_MODULE_PATH_ALIASES = {
        "flexibi_hamburg": "sources.roadside_trees.inventory.algorithms",
        "flexibi_nantes": "sources.greenhouses.inventory.algorithms",
    }
    SOURCE_MODULE_PATH_ALIASES_REVERSED = {
        "sources.roadside_trees.inventory.algorithms": "flexibi_hamburg",
        "sources.greenhouses.inventory.algorithms": "flexibi_nantes",
    }

    name = models.CharField(max_length=56)
    source_module = models.CharField(max_length=255, null=True)
    function_name = models.CharField(max_length=56, null=True)
    description = models.TextField(blank=True, null=True)
    geodataset = models.ForeignKey(
        GeoDataset, on_delete=models.CASCADE
    )  # TODO: Make many2many?
    feedstocks = models.ManyToManyField(Material)
    default = models.BooleanField(
        "Default for this combination of geodataset and feedstock", default=False
    )
    source = models.ForeignKey(Source, on_delete=models.PROTECT, null=True)

    # TODO: How are default values controlled?

    @staticmethod
    def normalize_source_module(source_module):
        if source_module in InventoryAlgorithm.SOURCE_MODULE_PATH_ALIASES_REVERSED:
            return InventoryAlgorithm.SOURCE_MODULE_PATH_ALIASES_REVERSED[source_module]
        if source_module.startswith("case_studies.") and source_module.endswith(
            ".algorithms"
        ):
            return source_module.removeprefix("case_studies.").removesuffix(
                ".algorithms"
            )
        return source_module

    @staticmethod
    def get_module_path(source_module):
        source_module = InventoryAlgorithm.normalize_source_module(source_module)
        if "." in source_module:
            return source_module
        return InventoryAlgorithm.SOURCE_MODULE_PATH_ALIASES.get(
            source_module, source_module
        )

    @staticmethod
    def task_reference_lookup_candidates(source_module):
        normalized_source_module = InventoryAlgorithm.normalize_source_module(
            source_module
        )
        candidates = [source_module]
        if normalized_source_module not in candidates:
            candidates.append(normalized_source_module)
        module_path = InventoryAlgorithm.get_module_path(normalized_source_module)
        if module_path not in candidates:
            candidates.append(module_path)
        return candidates

    @staticmethod
    def available_modules():
        legacy_modules = sorted(InventoryAlgorithm.SOURCE_MODULE_PATH_ALIASES)
        source_modules = []
        for module in pkgutil.iter_modules(sources.__path__):
            if not module.ispkg:
                continue
            module_path = f"sources.{module.name}.inventory.algorithms"
            try:
                inventory_module = importlib.import_module(module_path)
            except ModuleNotFoundError as exc:
                if exc.name != module_path and not module_path.startswith(
                    f"{exc.name}."
                ):
                    raise
                continue
            if hasattr(inventory_module, "InventoryAlgorithms"):
                source_modules.append(module_path)

        return legacy_modules + sorted(source_modules)

    @staticmethod
    def available_functions(module_name):
        module = importlib.import_module(
            InventoryAlgorithm.get_module_path(module_name)
        )
        return [
            alg
            for alg in module.InventoryAlgorithms.__dict__
            if not alg.startswith("__")
        ]

    @staticmethod
    def build_task_reference(source_module, function_name):
        return f"{InventoryAlgorithm.get_module_path(source_module)}:{function_name}"

    @staticmethod
    def parse_task_reference(task_reference):
        module_path, function_name = task_reference.split(":", 1)
        if module_path.startswith("case_studies.") and module_path.endswith(
            ".algorithms"
        ):
            source_module = module_path.removeprefix("case_studies.").removesuffix(
                ".algorithms"
            )
        else:
            source_module = module_path
        return source_module, function_name

    @classmethod
    def from_task_reference(cls, task_reference):
        source_module, function_name = cls.parse_task_reference(task_reference)
        for candidate in cls.task_reference_lookup_candidates(source_module):
            try:
                return cls.objects.get(
                    source_module=candidate, function_name=function_name
                )
            except cls.DoesNotExist:
                continue
        raise cls.DoesNotExist(
            f"InventoryAlgorithm matching query does not exist for {task_reference}."
        )

    @property
    def module_path(self):
        return self.get_module_path(self.source_module)

    @property
    def task_reference(self):
        return self.build_task_reference(self.source_module, self.function_name)

    def import_module(self):
        return importlib.import_module(self.module_path)

    def execute(self, **kwargs):
        module = self.import_module()
        return getattr(module.InventoryAlgorithms, self.function_name)(**kwargs)

    def default_values(self):
        """
        Returns a queryset of all default values of parameters of this algorithm.
        """
        values = {}
        for parameter in self.inventoryalgorithmparameter_set.all():
            if parameter not in values.keys():
                values[parameter] = []
            for value in InventoryAlgorithmParameterValue.objects.filter(
                parameter=parameter, default=True
            ):
                values[parameter].append(value)
        return values

    def __str__(self):
        return self.name


class InventoryAlgorithmParameter(models.Model):
    descriptive_name = models.CharField(max_length=56)
    short_name = models.CharField(
        max_length=28,
        validators=[
            RegexValidator(
                regex=r"^\w{1,28}$",
                message="Invalid parameter short_name. Do not use space"
                "or special characters.",
                code="invalid_parameter_name",
            )
        ],
    )
    description = models.TextField(blank=True, null=True)
    inventory_algorithm = models.ManyToManyField(
        InventoryAlgorithm
    )  # TODO: convert to foreign key
    unit = models.CharField(max_length=20, blank=True, null=True)
    is_required = models.BooleanField(default=False)

    def default_value(self):
        return InventoryAlgorithmParameterValue.objects.get(
            parameter=self, default=True
        )

    def __str__(self):
        return self.short_name


class InventoryAlgorithmParameterValue(models.Model):
    class ValueType(models.IntegerChoices):
        NUMERIC = 1
        SELECTION = 2

    name = models.CharField(max_length=56)
    type = models.IntegerField(choices=ValueType.choices, default=ValueType.NUMERIC)
    description = models.TextField(blank=True, null=True)
    parameter = models.ForeignKey(
        InventoryAlgorithmParameter, on_delete=models.CASCADE, null=True
    )
    value = models.FloatField()
    standard_deviation = models.FloatField(blank=True, null=True)
    source = models.CharField(
        max_length=200, blank=True, null=True
    )  # TODO: connect to bibliography
    default = models.BooleanField(default=False)

    def __str__(self):
        if self.type == 1:
            return f"{self.value} ({self.source})"
        elif self.type == 2:
            return f"{self.name}"
        return self.name


@receiver(pre_save, sender=InventoryAlgorithmParameterValue)
def auto_default(sender, instance, **kwargs):
    """
    Makes sure that defaults are always set correctly, even if the user provides incoherent input.
    """
    # If there is no default, yet, make the new instance default
    if not instance.default:
        if not instance.parameter.inventoryalgorithmparametervalue_set.exclude(
            id=instance.id
        ).filter(default=True):
            instance.default = True


@receiver(post_save, sender=InventoryAlgorithmParameterValue)
def manage_parameter_value_defaults(sender, instance, created, **kwargs):
    """
    Makes sure that defaults are always set correctly, even if the user provides incoherent input.
    """
    # If the new instance is set to default and there are other old defaults, override them.
    if instance.default:
        for val in instance.parameter.inventoryalgorithmparametervalue_set.exclude(
            id=instance.id
        ).filter(default=True):
            val.default = False
            val.save()


class ScenarioConfigurationError(Exception):
    pass


class WrongParameterForInventoryAlgorithm(Exception):
    def __init__(self, value):
        super().__init__(
            f"The provided value: {value} does not belong to a parameter of the chosen algorithm."
        )


class FeedstockNotImplemented(Exception):
    def __init__(self, feedstock):
        super().__init__(
            f"The feedstock: {feedstock} cannot be included because there is not dataset and or "
            "algorithm for it in this region"
        )


SCENARIO_STATUS = (
    ("administrative", "administrative"),
    ("custom", "custom"),
)


class ScenarioStatus(models.Model):
    class Status(models.IntegerChoices):
        CHANGED = 1
        RUNNING = 2
        FINISHED = 3

    scenario = models.OneToOneField("Scenario", on_delete=models.CASCADE, null=True)
    status = models.IntegerField(choices=Status.choices, default=Status.CHANGED)

    def __str__(self):
        return f"Status of Scenario {self.scenario}: {self.status}"


class Scenario(NamedUserCreatedObject):
    name = models.CharField(max_length=56, default="Custom Scenario")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    description = models.TextField(blank=True, null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=True)
    catchment = models.ForeignKey(
        Catchment, on_delete=models.CASCADE, null=True, related_name="scenarios"
    )  # TODO: make many-to-many?

    # TODO: Add duplicate functionality

    @property
    def status(self):
        return ScenarioStatus.Status(self.scenariostatus.status)

    @status.setter
    def status(
        self, status: ScenarioStatus.Status
    ):  # TODO: It might be confusing that is saves. Remove?
        self.scenariostatus.status = status
        self.scenariostatus.save()

    def set_status(self, status):
        if isinstance(status, ScenarioStatus.Status):
            self.scenariostatus.status = status
            self.scenariostatus.save()

    def available_feedstocks(self):
        """
        Returns all materials that can be included in this scenario.
        """
        materials = Material.objects.filter(
            id__in=self.available_inventory_algorithms().values("feedstocks")
        )
        return SampleSeries.objects.filter(material__in=materials)

    def feedstocks(self):
        """
        Returns all materials (SampleSeries) that have been included in this scenario.
        """
        return SampleSeries.objects.filter(
            id__in=self.scenarioinventoryconfiguration_set.all().values("feedstock")
        )

    def available_geodatasets(
        self, feedstock: Material = None, feedstocks: QuerySet = None
    ):
        """
        Returns a queryset of geodatasets that can be used in this scenario. By providing either a Material object or
        a queryset of Materials as keyword argument feedstock/feedstocks respectively, the query is reduced to
        geodatasets which have algorithms for these given feedstocks.
        """
        if feedstocks is None and feedstock is None:
            feedstocks = Material.objects.filter(type="material")
        elif feedstocks is None and feedstock is not None:
            feedstocks = Material.objects.filter(id=feedstock.id)

        return GeoDataset.objects.filter(
            id__in=InventoryAlgorithm.objects.filter(
                feedstocks__in=feedstocks, geodataset__region=self.region
            ).values("geodataset")
        )

    def evaluated_geodatasets(
        self, feedstock: Material = None, feedstocks: QuerySet = None
    ):
        if feedstocks is None and feedstock is None:
            feedstocks = Material.objects.filter(type="material")
        elif feedstocks is None and feedstock is not None:
            feedstocks = Material.objects.filter(id=feedstock.id)
        return GeoDataset.objects.filter(
            id__in=ScenarioInventoryConfiguration.objects.filter(
                scenario=self, feedstock__material__in=feedstocks
            ).values("geodataset")
        )

    def remaining_geodataset_options(
        self, feedstock: Material = None, feedstocks: QuerySet = None
    ):
        if feedstocks is None and feedstock is None:
            feedstocks = Material.objects.filter(type="material")
        elif feedstocks is None and feedstock is not None:
            feedstocks = Material.objects.filter(id=feedstock.id)
        return self.available_geodatasets(feedstocks=feedstocks).difference(
            self.evaluated_geodatasets(feedstocks=feedstocks)
        )

    def available_inventory_algorithms(
        self,
        feedstock: Material = None,
        feedstocks: QuerySet = None,
        geodataset: GeoDataset = None,
        geodatasets: QuerySet = None,
    ):
        if feedstocks is None and feedstock is None:
            feedstocks = Material.objects.filter(type="material")
        elif feedstocks is None and feedstock is not None:
            feedstocks = Material.objects.filter(id=feedstock.id)

        if geodatasets is None and geodataset is None:
            geodatasets = GeoDataset.objects.all()
        elif geodatasets is None and geodataset is not None:
            geodatasets = GeoDataset.objects.filter(id=geodataset.id)

        geodatasets = geodatasets.filter(region=self.region)

        return InventoryAlgorithm.objects.filter(
            feedstocks__in=feedstocks, geodataset__in=geodatasets
        )

    def evaluated_inventory_algorithms(self):
        return InventoryAlgorithm.objects.filter(
            id__in=ScenarioInventoryConfiguration.objects.filter(scenario=self).values(
                "inventory_algorithm"
            )
        )

    def remaining_inventory_algorithm_options(self, feedstock, geodataset):
        if ScenarioInventoryConfiguration.objects.filter(
            scenario=self, feedstock=feedstock, geodataset=geodataset
        ):
            return InventoryAlgorithm.objects.none()
        else:
            return InventoryAlgorithm.objects.filter(
                feedstock=feedstock.material, geodataset=geodataset
            )

    def default_inventory_algorithms(self):
        return InventoryAlgorithm.objects.filter(
            geodataset__region=self.region, default=True
        )

    def inventory_algorithm_config(self, algorithm, feedstock):
        configuration = self.configuration().filter(
            inventory_algorithm=algorithm, feedstock=feedstock
        )
        return {
            "scenario": self,
            "feedstock": feedstock,
            "geodataset": algorithm.geodataset,
            "inventory_algorithm": algorithm,
            "parameters": [
                {conf.inventory_parameter.short_name: conf.inventory_value.id}
                for conf in configuration.select_related(
                    "inventory_parameter", "inventory_value"
                )
                if conf.inventory_parameter and conf.inventory_value
            ],
        }

    def add_inventory_algorithm(
        self,
        feedstock: Material,
        algorithm: InventoryAlgorithm,
        custom_parameter_values=None,
    ):
        """
        Adds an inventory algorithm to and the given parameter values to the scenario configuration. If no
        parameter values are given, the algorithm will be added with default values.
        """

        # self.remove_inventory_algorithm(algorithm, feedstock)

        if feedstock not in self.available_feedstocks():
            raise FeedstockNotImplemented(feedstock)

        if custom_parameter_values:
            # for value in custom_parameter_values:
            #     if not value.parameter.inventory_algorithm == algorithm:
            #         raise WrongParameterForInventoryAlgorithm(value)
            values = custom_parameter_values
        else:
            values = algorithm.default_values()

        if not values:
            config = {
                "scenario": self,
                "feedstock": feedstock,
                "geodataset": algorithm.geodataset,
                "inventory_algorithm": algorithm,
            }
            ScenarioInventoryConfiguration.objects.create(**config)
            return

        for parameter, value_list in values.items():
            for value in value_list:
                config = {
                    "scenario": self,
                    "feedstock": feedstock,
                    "geodataset": algorithm.geodataset,
                    "inventory_algorithm": algorithm,
                    "inventory_parameter": parameter,
                    "inventory_value": value,
                }
                ScenarioInventoryConfiguration.objects.create(**config)

    def remove_inventory_algorithm(
        self, algorithm: InventoryAlgorithm, feedstock: SampleSeries
    ):
        """
        Remove all entries from the configuration that are associated with the given algorithm.
        """
        for config_entry in self.configuration().filter(
            inventory_algorithm=algorithm, feedstock=feedstock
        ):
            config_entry.delete()

    # def delete(self, **kwargs):
    #     self.delete_configuration()  # TODO: Does this happen automatically through cascading?
    #     super().delete()

    def delete_result_layers(self):
        for layer in self.layer_set.all():
            layer.delete()

    def delete_configuration(self):
        """
        Removes all entries from the configuration that are associated with this scenario. Handle with care!
        An improperly configured scenario will lead to unexpected behaviour.
        """
        for config_entry in self.configuration():
            config_entry.delete()

    def reset_configuration(self):
        self.delete_configuration()
        self.create_default_configuration()

    def is_valid_configuration(self):
        configuration = self.configuration()
        # At least one entry for a scenario
        if not configuration:
            raise ScenarioConfigurationError("The scenario is not configured.")

        # Get all inventory algorithms that are used in this scenario
        algorithms = [
            c.inventory_algorithm for c in configuration.distinct("inventory_algorithm")
        ]

        # Are all required parameters included in the configuration?
        required = InventoryAlgorithmParameter.objects.filter(
            inventory_algorithm__in=algorithms, is_required=True
        ).values_list("id")
        configured = configuration.values_list("inventory_parameter")
        if not set(required).issubset(configured):
            raise ScenarioConfigurationError("Not all required parameters are defined.")

        # Is each parameter only defined once per scenario?
        if not len(set(configured)) == len(configured):
            raise ScenarioConfigurationError(
                "There are double defined parameters in the configuration"
            )

    def create_default_configuration(self):
        """
        Gathers all defaults that are necessary to evaluate a defined base scenario and saves them as entries in
        ScenarioInventoryConfiguration. The scenario can now be evaluated with defaults or be customized in a second
        step.
        :return:
        """
        for parameter in InventoryAlgorithmParameter.objects.filter(
            inventory_algorithm__in=self.default_inventory_algorithms()
        ):
            config_entry = ScenarioInventoryConfiguration()
            config_entry.scenario = self
            config_entry.feedstock = parameter.inventory_algorithm.feedstock
            config_entry.inventory_algorithm = parameter.inventory_algorithm
            config_entry.geodataset = parameter.inventory_algorithm.geodataset
            config_entry.inventory_parameter = parameter
            config_entry.inventory_value = parameter.default_value()
            config_entry.save()

    def configuration(self):
        return ScenarioInventoryConfiguration.objects.filter(scenario=self)

    def inventory_execution_plan(self):
        inventory_config = {}
        for entry in self.configuration().select_related(
            "inventory_algorithm", "inventory_parameter", "inventory_value"
        ):
            feedstock = entry.feedstock.id
            algorithm = entry.inventory_algorithm
            parameter = (
                entry.inventory_parameter.short_name
                if entry.inventory_parameter
                else None
            )
            if entry.inventory_value:
                value = entry.inventory_value.value
                standard_deviation = entry.inventory_value.standard_deviation

            if feedstock not in inventory_config.keys():
                inventory_config[feedstock] = {}
            if algorithm.id not in inventory_config[feedstock].keys():
                inventory_config[feedstock][algorithm.id] = {
                    "algorithm": algorithm,
                    "kwargs": {
                        "catchment_id": self.catchment.id,
                        "scenario_id": self.id,
                        "feedstock_id": feedstock,
                    },
                }
            if (
                parameter
                and parameter not in inventory_config[feedstock][algorithm.id]["kwargs"]
            ):
                inventory_config[feedstock][algorithm.id]["kwargs"][parameter] = {
                    "value": value,
                    "standard_deviation": standard_deviation,
                }

        return [
            execution
            for feedstock_config in inventory_config.values()
            for execution in feedstock_config.values()
        ]

    def serialize_inventory_execution_plan(self, execution_plan):
        inventory_config = {}
        for execution in execution_plan:
            feedstock = execution["kwargs"]["feedstock_id"]
            function = execution["algorithm"].task_reference
            if feedstock not in inventory_config.keys():
                inventory_config[feedstock] = {}
            inventory_config[feedstock][function] = execution["kwargs"].copy()

        return inventory_config

    def configuration_for_template(self):
        config = {}
        for entry in self.configuration().select_related(
            "feedstock", "inventory_algorithm", "inventory_parameter", "inventory_value"
        ):
            feedstock = entry.feedstock
            algorithm = entry.inventory_algorithm
            parameter = entry.inventory_parameter
            value = entry.inventory_value

            if feedstock not in config.keys():
                config[feedstock] = {}
            if algorithm not in config[feedstock]:
                config[feedstock][algorithm] = {}
            if parameter not in config[feedstock][algorithm]:
                config[feedstock][algorithm][parameter] = value

        return config

    def result_features_collections(self):
        return [layer.get_feature_collection() for layer in self.layer_set()]

    def summary_dict(self):
        summary = {
            "Name": self.name,
            "Case study region": {
                "Name": self.region.name,
            },
            "Catchment": {
                "Name": self.catchment.name,
                "Description": self.catchment.description,
            },
            "Description": self.description,
        }
        return summary

    @property
    def detail_url(self):
        return self.get_absolute_url()

    @property
    def update_url(self):
        return reverse("scenario-update", kwargs={"pk": self.id})

    @property
    def delete_url(self):
        return reverse("scenario-delete-modal", kwargs={"pk": self.id})

    def get_absolute_url(self):
        return reverse("scenario-detail", kwargs={"pk": self.id})

    def __str__(self):
        return self.name


class InventoryAmountShare(models.Model):
    owner = models.ForeignKey(User, default=1, on_delete=models.CASCADE)
    scenario = models.ForeignKey(Scenario, null=True, on_delete=models.CASCADE)
    feedstock = models.ForeignKey(SampleSeries, null=True, on_delete=models.CASCADE)
    timestep = models.ForeignKey(Timestep, null=True, on_delete=models.CASCADE)
    average = models.FloatField(default=0.0)
    standard_deviation = models.FloatField(default=0.0)


@receiver(pre_save, sender=Scenario)
def block_running_scenario(sender, instance, **kwargs):
    """Checks if a scenario is being evaluated before it can be saved."""
    if instance.pk is None:
        return

    scenario_status = ScenarioStatus.objects.filter(scenario_id=instance.pk).first()
    if scenario_status is None:
        return

    if scenario_status.status != ScenarioStatus.Status.RUNNING:
        return

    running_tasks = list(RunningTask.objects.filter(scenario_id=instance.pk))
    if not running_tasks:
        raise BlockedRunningScenario

    stale_task_ids = []
    for task in running_tasks:
        if AsyncResult(str(task.uuid)).state not in READY_STATES:
            raise BlockedRunningScenario
        stale_task_ids.append(task.id)

    if stale_task_ids:
        RunningTask.objects.filter(id__in=stale_task_ids).delete()
    scenario_status.status = ScenarioStatus.Status.CHANGED
    scenario_status.save()


@receiver(post_save, sender=Scenario)
def manage_scenario_status(sender, instance, created, **kwargs):
    """
    Whenever a new Scenario instance is created, this creates a ScenarioStatus instance for it.
    Whenever a Scenario instance has been edited, the status is changed to CHANGED.
    """
    if created:
        ScenarioStatus.objects.create(scenario=instance)
    else:
        instance.scenariostatus.status = ScenarioStatus.Status.CHANGED
        instance.scenariostatus.save()


class ScenarioInventoryConfiguration(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    feedstock = models.ForeignKey(SampleSeries, on_delete=models.CASCADE, null=True)
    geodataset = models.ForeignKey(GeoDataset, on_delete=models.CASCADE)
    inventory_algorithm = models.ForeignKey(
        InventoryAlgorithm, on_delete=models.CASCADE
    )
    inventory_parameter = models.ForeignKey(
        InventoryAlgorithmParameter, on_delete=models.CASCADE, null=True
    )
    inventory_value = models.ForeignKey(
        InventoryAlgorithmParameterValue, on_delete=models.CASCADE, null=True
    )

    def save(self, *args, **kwargs):
        # TODO: The status must also be changed, when any of the referenced foreign key objects change
        self.scenario.set_status(ScenarioStatus.Status.CHANGED)
        super().save(*args, **kwargs)

    # def save(self, *args, **kwargs):
    #     # Only save if there is no previous entry for a parameter in a scenario. Otherwise drop old entry first.
    #     if not ScenarioInventoryConfiguration.objects.filter(scenario=self.scenario,
    #                                                          inventory_algorithm=self.inventory_algorithm,
    #                                                          inventory_parameter=self.inventory_parameter):
    #         super(ScenarioInventoryConfiguration, self).save(*args, **kwargs)
    #     else:
    #         ScenarioInventoryConfiguration.objects \
    #             .filter(scenario=self.scenario,
    #                     inventory_algorithm=self.inventory_algorithm,
    #                     inventory_parameter=self.inventory_parameter) \
    #             .update(inventory_value=self.inventory_value)

    def get_absolute_url(self):
        return reverse("scenario-detail", kwargs={"pk": self.scenario.pk})


class RunningTask(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    algorithm = models.ForeignKey(
        InventoryAlgorithm, on_delete=models.CASCADE, null=True
    )
    uuid = models.UUIDField(primary_key=False)
