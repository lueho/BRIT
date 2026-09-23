import importlib
import pkgutil

from celery.result import AsyncResult
from celery.states import READY_STATES
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.db.models import Q
from django.db.models.query import QuerySet
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse

import sources
from bibliography.models import Source
from distributions.models import Timestep
from maps.models import Catchment, GeoDataset, Region
from materials.models import Material, Sample, SampleSeries
from utils.object_management.models import NamedUserCreatedObject
from utils.object_management.permissions import filter_queryset_for_user

from .exceptions import BlockedRunningScenario


class InventoryAlgorithm(models.Model):
    """
    Links functions that are defined in the InventoryMixin to the corresponding geodatasets and feedstocks in the
    database. This model is for configuration by admins and must not be available to users. Customization by users can
    be done in InventoryAlgorithmParameter and InventoryAlgorithmParameterValue.
    """

    SOURCE_MODULE_PATH_ALIASES = {
        "flexibi_hamburg": "sources.roadside_trees.inventory.algorithms",
    }
    SOURCE_MODULE_PATH_ALIASES_REVERSED = {
        "sources.roadside_trees.inventory.algorithms": "flexibi_hamburg",
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
    supports_standalone_samples = models.BooleanField(default=False)
    supports_sample_series = models.BooleanField(default=True)
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


class InventoryInputQuerySet(models.QuerySet):
    def accessible_by_user(self, user):
        visible_samples = filter_queryset_for_user(
            Sample.objects.filter(standalone=True), user
        )
        visible_series = filter_queryset_for_user(SampleSeries.objects.all(), user)
        return self.filter(
            Q(sample_id__in=visible_samples.values("pk"))
            | Q(series_id__in=visible_series.values("pk"))
        )


class InventoryInputManager(models.Manager.from_queryset(InventoryInputQuerySet)):
    def for_object(self, value):
        if isinstance(value, Sample):
            if not value.standalone:
                raise ValidationError(
                    {"sample": "Only standalone samples can be inventory inputs."}
                )
            return self.get_or_create(sample=value, defaults={"series": None})[0]
        if isinstance(value, SampleSeries):
            return self.get_or_create(series=value, defaults={"sample": None})[0]
        if isinstance(value, InventoryInput):
            return value
        raise TypeError("Inventory inputs must wrap a Sample or SampleSeries.")


class InventoryInput(models.Model):
    """
    Adapter that lets scenarios, inventory amount shares and result layers
    reference either a standalone Sample or a temporal SampleSeries through a
    single feedstock relation.
    """

    sample = models.OneToOneField(
        Sample,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="inventory_input",
    )
    series = models.OneToOneField(
        SampleSeries,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="inventory_input",
    )

    objects = InventoryInputManager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(sample__isnull=False, series__isnull=True)
                    | Q(sample__isnull=True, series__isnull=False)
                ),
                name="inventory_input_exactly_one_source",
            )
        ]

    def clean(self):
        super().clean()
        if (self.sample_id is None) == (self.series_id is None):
            raise ValidationError("Select exactly one sample or sample series.")
        if self.sample_id and not self.sample.standalone:
            raise ValidationError(
                {"sample": "Only standalone samples can be inventory inputs."}
            )

    @property
    def input_object(self):
        return self.series or self.sample

    @property
    def material(self):
        return self.input_object.material

    @property
    def name(self):
        return self.input_object.name

    @property
    def is_temporal(self):
        return self.series_id is not None

    @property
    def kind(self):
        return "series" if self.is_temporal else "sample"

    @property
    def publication_status(self):
        return self.input_object.publication_status

    def __str__(self):
        label = "Series" if self.is_temporal else "Sample"
        return f"{label}: {self.material} — {self.name}"

    def retire(self):
        """
        Remove this input together with every scenario configuration and
        result layer that references it, and flag the affected scenarios.
        """
        with transaction.atomic():
            scenario_ids = set(
                ScenarioInventoryConfiguration.objects.filter(feedstock=self)
                .values_list("scenario_id", flat=True)
                .distinct()
            )
            for layer in self.layer_set.all():
                scenario_ids.add(layer.scenario_id)
                layer.delete()
            self.delete()
            for scenario in Scenario.objects.filter(id__in=scenario_ids):
                scenario.set_status(ScenarioStatus.Status.CHANGED)


@receiver(post_save, sender=Sample)
def create_inventory_input_for_sample(sender, instance, raw=False, **kwargs):
    if raw:
        return
    if instance.standalone:
        InventoryInput.objects.for_object(instance)
        return
    stale = InventoryInput.objects.filter(sample=instance).first()
    if stale is not None:
        stale.retire()


@receiver(post_save, sender=SampleSeries)
def create_inventory_input_for_series(sender, instance, raw=False, **kwargs):
    if raw:
        return
    InventoryInput.objects.for_object(instance)


SCENARIO_STATUS = (
    ("administrative", "administrative"),
    ("custom", "custom"),
)


class ScenarioStatus(models.Model):
    class Status(models.IntegerChoices):
        CHANGED = 1
        RUNNING = 2
        FINISHED = 3
        FAILED = 4

    class Meta:
        verbose_name_plural = "scenario statuses"

    scenario = models.OneToOneField("Scenario", on_delete=models.CASCADE, null=True)
    status = models.IntegerField(choices=Status.choices, default=Status.CHANGED)
    failed_algorithm = models.ForeignKey(
        InventoryAlgorithm,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
    )
    failure_message = models.TextField(blank=True)

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
    def status(self, status: ScenarioStatus.Status):
        self.set_status(status)

    def set_status(self, status):
        if isinstance(status, ScenarioStatus.Status):
            self.scenariostatus.status = status
            update_fields = ["status"]
            if status != ScenarioStatus.Status.FAILED:
                self.scenariostatus.failed_algorithm = None
                self.scenariostatus.failure_message = ""
                update_fields.extend(["failed_algorithm", "failure_message"])
            self.scenariostatus.save(update_fields=update_fields)

    def available_feedstocks(self, user=None):
        """
        Returns all inventory inputs that can be included in this scenario.
        """
        algorithms = self.available_inventory_algorithms().prefetch_related(
            "feedstocks"
        )
        supported = set()
        for algorithm in algorithms:
            for material in algorithm.feedstocks.all():
                if algorithm.supports_sample_series:
                    supported.add((material.id, "series"))
                if algorithm.supports_standalone_samples:
                    supported.add((material.id, "sample"))

        candidates = InventoryInput.objects.select_related(
            "sample__material", "series__material"
        ).filter(Q(series__isnull=False) | Q(sample__standalone=True))
        if user is not None:
            candidates = candidates.accessible_by_user(user)
        return candidates.filter(
            pk__in=[
                candidate.pk
                for candidate in candidates
                if (candidate.material.id, candidate.kind) in supported
            ]
        )

    def feedstocks(self):
        """
        Returns all inventory inputs that have been included in this scenario.
        """
        return InventoryInput.objects.filter(
            id__in=self.scenarioinventoryconfiguration_set.all().values("feedstock")
        )

    @staticmethod
    def _feedstock_materials(feedstock):
        material = (
            feedstock.material if isinstance(feedstock, InventoryInput) else feedstock
        )
        return Material.objects.filter(id=material.id)

    def available_geodatasets(
        self, feedstock: Material = None, feedstocks: QuerySet = None
    ):
        """
        Returns a queryset of geodatasets that can be used in this scenario. By providing either a Material or
        InventoryInput object or a queryset of Materials as keyword argument feedstock/feedstocks respectively,
        the query is reduced to geodatasets which have algorithms for these given feedstocks.
        """
        if feedstocks is None and feedstock is None:
            feedstocks = Material.objects.filter(type="material")
        elif feedstocks is None and feedstock is not None:
            feedstocks = self._feedstock_materials(feedstock)

        algorithms = InventoryAlgorithm.objects.filter(
            feedstocks__in=feedstocks, geodataset__region=self.region
        )
        if isinstance(feedstock, InventoryInput):
            if feedstock.is_temporal:
                algorithms = algorithms.filter(supports_sample_series=True)
            else:
                algorithms = algorithms.filter(supports_standalone_samples=True)
        return GeoDataset.objects.filter(id__in=algorithms.values("geodataset"))

    def evaluated_geodatasets(
        self, feedstock: Material = None, feedstocks: QuerySet = None
    ):
        if feedstocks is None and feedstock is None:
            feedstocks = Material.objects.filter(type="material")
        elif feedstocks is None and feedstock is not None:
            feedstocks = self._feedstock_materials(feedstock)
        return GeoDataset.objects.filter(
            id__in=ScenarioInventoryConfiguration.objects.filter(
                Q(feedstock__series__material__in=feedstocks)
                | Q(feedstock__sample__material__in=feedstocks),
                scenario=self,
            ).values("geodataset")
        )

    def remaining_geodataset_options(
        self, feedstock: Material = None, feedstocks: QuerySet = None
    ):
        if feedstocks is None and feedstock is None:
            feedstocks = Material.objects.filter(type="material")
        elif feedstocks is None and feedstock is not None:
            feedstocks = self._feedstock_materials(feedstock)
        return self.available_geodatasets(
            feedstock=feedstock, feedstocks=feedstocks
        ).difference(self.evaluated_geodatasets(feedstocks=feedstocks))

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
            material = (
                feedstock.material
                if isinstance(feedstock, InventoryInput)
                else feedstock
            )
            feedstocks = Material.objects.filter(id=material.id)

        if geodatasets is None and geodataset is None:
            geodatasets = GeoDataset.objects.all()
        elif geodatasets is None and geodataset is not None:
            geodatasets = GeoDataset.objects.filter(id=geodataset.id)

        geodatasets = geodatasets.filter(region=self.region)

        algorithms = InventoryAlgorithm.objects.filter(
            feedstocks__in=feedstocks, geodataset__in=geodatasets
        )
        if isinstance(feedstock, InventoryInput):
            if feedstock.is_temporal:
                algorithms = algorithms.filter(supports_sample_series=True)
            else:
                algorithms = algorithms.filter(supports_standalone_samples=True)
        return algorithms

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
        algorithms = InventoryAlgorithm.objects.filter(
            feedstocks=feedstock.material, geodataset=geodataset
        )
        if isinstance(feedstock, InventoryInput):
            if feedstock.is_temporal:
                algorithms = algorithms.filter(supports_sample_series=True)
            else:
                algorithms = algorithms.filter(supports_standalone_samples=True)
        return algorithms

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

        feedstock = InventoryInput.objects.for_object(feedstock)

        if feedstock not in self.available_feedstocks():
            raise FeedstockNotImplemented(feedstock)

        supported = (
            algorithm.supports_sample_series
            if feedstock.is_temporal
            else algorithm.supports_standalone_samples
        )
        if (
            not supported
            or not algorithm.feedstocks.filter(pk=feedstock.material.pk).exists()
        ):
            raise FeedstockNotImplemented(feedstock)

        if custom_parameter_values:
            # for value in custom_parameter_values:
            #     if not value.parameter.inventory_algorithm == algorithm:
            #         raise WrongParameterForInventoryAlgorithm(value)
            values = custom_parameter_values
        else:
            values = algorithm.default_values()

        with transaction.atomic():
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
        feedstock = InventoryInput.objects.for_object(feedstock)
        for config_entry in self.configuration().filter(
            inventory_algorithm=algorithm, feedstock=feedstock
        ):
            config_entry.delete()

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

        # Is each parameter only defined once per feedstock and algorithm?
        parameter_entries = list(
            configuration.filter(inventory_parameter__isnull=False).values_list(
                "feedstock", "inventory_algorithm", "inventory_parameter"
            )
        )
        if not len(set(parameter_entries)) == len(parameter_entries):
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
        for algorithm in self.default_inventory_algorithms():
            if not algorithm.supports_sample_series:
                continue
            for feedstock in SampleSeries.objects.filter(
                material__in=algorithm.feedstocks.all()
            ):
                self.add_inventory_algorithm(feedstock, algorithm)

    def configuration(self):
        return ScenarioInventoryConfiguration.objects.filter(scenario=self)

    def inventory_execution_plan(self):
        inventory_config = {}
        for entry in self.configuration().select_related(
            "inventory_algorithm",
            "inventory_parameter",
            "inventory_value",
            "feedstock__sample",
            "feedstock__series",
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
                        "inventory_input_id": entry.feedstock.id,
                        "feedstock_id": entry.feedstock.input_object.id,
                        "feedstock_kind": entry.feedstock.kind,
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
            feedstock = execution["kwargs"].get(
                "inventory_input_id", execution["kwargs"]["feedstock_id"]
            )
            function = execution["algorithm"].task_reference
            if feedstock not in inventory_config.keys():
                inventory_config[feedstock] = {}
            inventory_config[feedstock][function] = execution["kwargs"].copy()

        return inventory_config

    def configuration_for_template(self):
        config = {}
        for entry in self.configuration().select_related(
            "feedstock__sample",
            "feedstock__series",
            "inventory_algorithm",
            "inventory_parameter",
            "inventory_value",
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
    feedstock = models.ForeignKey(InventoryInput, null=True, on_delete=models.CASCADE)
    timestep = models.ForeignKey(Timestep, null=True, on_delete=models.CASCADE)
    average = models.FloatField(default=0.0)
    standard_deviation = models.FloatField(default=0.0)

    def clean(self):
        super().clean()
        if self.feedstock_id and not self.feedstock.is_temporal:
            raise ValidationError(
                {
                    "feedstock": "Inventory amount shares require a temporal sample series."
                }
            )


@receiver(pre_save, sender=Scenario)
def block_running_scenario(sender, instance, **kwargs):
    """Checks if a scenario is being evaluated before it can be saved."""
    if instance.pk is None:
        return

    with transaction.atomic():
        scenario_status = (
            ScenarioStatus.objects.select_for_update()
            .filter(scenario_id=instance.pk)
            .first()
        )
        if scenario_status is None:
            return

        if scenario_status.status != ScenarioStatus.Status.RUNNING:
            return

        running_tasks = list(
            RunningTask.objects.select_for_update().filter(scenario_id=instance.pk)
        )
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
        scenario_status.save(update_fields=["status"])


@receiver(post_save, sender=Scenario)
def manage_scenario_status(sender, instance, created, **kwargs):
    """
    Whenever a new Scenario instance is created, this creates a ScenarioStatus instance for it.
    Whenever a Scenario instance has been edited, the status is changed to CHANGED.
    """
    if created:
        ScenarioStatus.objects.create(scenario=instance)
    else:
        instance.set_status(ScenarioStatus.Status.CHANGED)


class ScenarioInventoryConfiguration(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    feedstock = models.ForeignKey(InventoryInput, on_delete=models.CASCADE, null=True)
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


def _mark_referencing_scenarios_changed(model_class, instance):
    """Set status to CHANGED for all scenarios that reference the given instance
    through ScenarioInventoryConfiguration."""
    field_map = {
        InventoryAlgorithm: "inventory_algorithm",
        InventoryAlgorithmParameterValue: "inventory_value",
    }
    fk_field = field_map.get(model_class)
    if fk_field is None:
        return
    scenario_ids = (
        ScenarioInventoryConfiguration.objects.filter(**{fk_field: instance})
        .values_list("scenario_id", flat=True)
        .distinct()
    )
    for scenario in Scenario.objects.filter(id__in=scenario_ids):
        scenario.set_status(ScenarioStatus.Status.CHANGED)


@receiver(post_save, sender=InventoryAlgorithm)
def propagate_algorithm_change_to_scenarios(sender, instance, created, **kwargs):
    if not created:
        _mark_referencing_scenarios_changed(InventoryAlgorithm, instance)


@receiver(post_save, sender=InventoryAlgorithmParameterValue)
def propagate_parameter_value_change_to_scenarios(sender, instance, created, **kwargs):
    if not created:
        _mark_referencing_scenarios_changed(InventoryAlgorithmParameterValue, instance)


class RunningTask(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    algorithm = models.ForeignKey(
        InventoryAlgorithm, on_delete=models.CASCADE, null=True
    )
    uuid = models.UUIDField(primary_key=False)
