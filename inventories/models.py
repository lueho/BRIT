import importlib

from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.query import QuerySet
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

import case_studies
from bibliography.models import Source
from distributions.models import Timestep
from maps.models import Catchment, GeoDataset, Region
from materials.models import Material, SampleSeries
from utils.models import NamedUserObjectModel, OwnedObjectModel
from .exceptions import BlockedRunningScenario


class Algorithm(NamedUserObjectModel):
    """
    Links functions that are defined in the InventoryMixin to the corresponding geodatasets and feedstocks in the
    database. This model is for configuration by admins and must not be available to users. Customization by users can
    be done in Parameter and ParameterValue.
    """
    source_module = models.CharField(max_length=255, null=True)
    function_name = models.CharField(max_length=56, null=True)
    geodataset = models.ForeignKey(GeoDataset, on_delete=models.CASCADE,
                                   related_name='algorithms')  # TODO: Make many2many?
    feedstocks = models.ManyToManyField(Material)
    default = models.BooleanField('Default for this combination of geodataset and feedstock', default=False)
    source = models.ForeignKey(Source, on_delete=models.PROTECT, null=True)

    @staticmethod
    def available_modules():
        return [name for name in dir(case_studies) if not name.startswith('__')]

    @staticmethod
    def available_functions(module_name):
        module = importlib.import_module('case_studies.' + module_name + '.algorithms')
        return [alg for alg in module.InventoryAlgorithms.__dict__ if not alg.startswith('__')]

    def default_values(self):
        """
        Returns a queryset of all default values of parameters of this algorithm.
        """
        values = {}
        for parameter in self.parameters.all():
            if parameter not in values.keys():
                values[parameter] = []
            for value in ParameterValue.objects.filter(parameter=parameter, default=True):
                values[parameter].append(value)
        return values

    def __str__(self):
        return self.name


class Parameter(NamedUserObjectModel):
    """
    The Parameter model represents a parameter that is associated with an algorithm.
    """

    descriptive_name = models.CharField(max_length=56)
    short_name = models.CharField(max_length=28,
                                  validators=[RegexValidator(regex=r'^\w{1,28}$',
                                                             message='Invalid parameter short_name. Do not use space'
                                                                     'or special characters.',
                                                             code='invalid_parameter_name')])
    algorithm = models.ForeignKey(Algorithm, on_delete=models.CASCADE, related_name='parameters')
    unit = models.CharField(max_length=20, blank=True, null=True)
    is_required = models.BooleanField(default=False)
    data_type = models.CharField(max_length=50)
    default_value = models.ForeignKey('ParameterValue', on_delete=models.PROTECT, related_name='default_for', null=True)

    def __str__(self):
        return self.short_name


class ParameterValue(NamedUserObjectModel):
    """
    The ParameterValue model represents the value of a parameter that is associated with an algorithm.
    """

    class ValueType(models.IntegerChoices):
        """
        The ValueType model represents the type of the value of a parameter.
        It can be either NUMERIC (1) or SELECTION (2).
        """
        NUMERIC = 1
        SELECTION = 2

    # TODO: This should now be data_type in Parameter
    type = models.IntegerField(choices=ValueType.choices, default=ValueType.NUMERIC)
    parameter = models.ForeignKey(Parameter, on_delete=models.CASCADE, null=True, related_name='values')
    value = models.FloatField()
    standard_deviation = models.FloatField(blank=True, null=True)
    source = models.ForeignKey(Source, on_delete=models.CASCADE, null=True)

    def __str__(self):
        if self.type == 1:
            return f'{self.value}'
        elif self.type == 2:
            return f'{self.name}'
        return self.name


class ScenarioConfigurationError(Exception):
    pass


class WrongParameterForInventoryAlgorithm(Exception):
    def __init__(self, value):
        f"""The provided value: {value} does not belong to a parameter of the chosen algorithm."""


class FeedstockNotImplemented(Exception):
    def __init__(self, feedstock):
        f"""The feedstock: {feedstock} cannot be included because there is not dataset and or 
        algorithm for it in this region"""


class ScenarioStatus(models.Model):
    class Status(models.IntegerChoices):
        CHANGED = 1
        RUNNING = 2
        FINISHED = 3
        FAILED = 4

    scenario = models.OneToOneField('Scenario', on_delete=models.CASCADE, null=True)
    status = models.IntegerField(choices=Status.choices, default=Status.CHANGED)

    def __str__(self):
        return f'Status of Scenario {self.scenario}: {self.status}'


class Scenario(NamedUserObjectModel):
    description = models.TextField(blank=True, null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=True)
    catchment = models.ForeignKey(Catchment, on_delete=models.CASCADE, null=True, related_name='scenarios')

    @property
    def status(self):
        return ScenarioStatus.Status(self.scenariostatus.status)

    @status.setter
    def status(self, status: ScenarioStatus.Status):  # TODO: It might be confusing that is saves. Remove?
        self.scenariostatus.status = status
        self.scenariostatus.save()

    def set_status(self, status):
        if isinstance(status, ScenarioStatus.Status):
            self.scenariostatus.status = status
            self.scenariostatus.save()
        elif isinstance(status, int):
            if status == 1:
                self.scenariostatus.status = ScenarioStatus.Status.CHANGED
            elif status == 2:
                self.scenariostatus.status = ScenarioStatus.Status.RUNNING
            elif status == 3:
                self.scenariostatus.status = ScenarioStatus.Status.FINISHED
            elif status == 4:
                self.scenariostatus.status = ScenarioStatus.Status.FAILED
            self.scenariostatus.save()

    def feedstocks(self):
        """
        Returns all materials (SampleSeries) that have been included in this scenario.
        """
        return SampleSeries.objects.filter(id__in=self.scenarioconfiguration_set.all().values('feedstock'))

    def available_geodatasets(self, feedstock: Material = None, feedstocks: QuerySet = None):
        """
        Returns a queryset of geodatasets that can be used in this scenario. By providing either a Material object or
        a queryset of Materials as keyword argument feedstock/feedstocks respectively, the query is reduced to
        geodatasets which have algorithms for these given feedstocks.
        """
        if feedstocks is None and feedstock is None:
            feedstocks = Material.objects.filter(type='material')
        elif feedstocks is None and feedstock is not None:
            feedstocks = Material.objects.filter(id=feedstock.id)

        return GeoDataset.objects.filter(
            id__in=Algorithm.objects.filter(
                feedstocks__in=feedstocks, geodataset__region=self.region).values('geodataset'))

    def available_inventory_algorithms(self,
                                       feedstock: Material = None,
                                       feedstocks: QuerySet = None,
                                       geodataset: GeoDataset = None,
                                       geodatasets: QuerySet = None):

        if feedstocks is None and feedstock is None:
            feedstocks = Material.objects.filter(type='material')
        elif feedstocks is None and feedstock is not None:
            feedstocks = Material.objects.filter(id=feedstock.id)

        if geodatasets is None and geodataset is None:
            geodatasets = GeoDataset.objects.all()
        elif geodatasets is None and geodataset is not None:
            geodatasets = GeoDataset.objects.filter(id=geodataset.id)

        geodatasets = geodatasets.filter(region=self.region)

        return Algorithm.objects.filter(feedstocks__in=feedstocks, geodataset__in=geodatasets)

    def default_inventory_algorithms(self):
        return Algorithm.objects.filter(geodataset__region=self.region,
                                        default=True)

    def delete_result_layers(self):
        for layer in self.layer_set.all():
            layer.delete()

    def configuration_as_dict(self):
        """
        Fetches all configuration entries that are associated with this scenario and assembles a dictionary holding
        all configuration information for the inventory.
        :return: None
        """

        inventory_config = {}
        for entry in ScenarioConfiguration.objects.filter(scenario=self):
            for parameter_value in entry.parameter_settings.all():
                feedstock = entry.feedstock.id
                function = f'case_studies.{entry.algorithm.source_module}.algorithms:{entry.algorithm.function_name}'
                parameter = parameter_value.parameter.short_name if parameter_value.parameter.short_name else None
                value = None
                standard_deviation = None
                if parameter_value:
                    value = parameter_value.value
                    standard_deviation = parameter_value.standard_deviation
                if feedstock not in inventory_config.keys():
                    inventory_config[feedstock] = {}
                if function not in inventory_config[feedstock].keys():
                    inventory_config[feedstock][function] = {}
                    inventory_config[feedstock][function]['catchment_id'] = self.catchment.id
                    inventory_config[feedstock][function]['scenario_id'] = self.id
                    inventory_config[feedstock][function]['feedstock_id'] = feedstock
                if parameter and parameter not in inventory_config[feedstock][function]:
                    inventory_config[feedstock][function][parameter] = {'value': value,
                                                                        'standard_deviation': standard_deviation}
        return inventory_config

    def configuration_for_template(self):

        config = {}
        for entry in ScenarioConfiguration.objects.filter(scenario=self):
            feedstock = entry.feedstock
            algorithm = entry.algorithm
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
            'Name': self.name,
            'Case study region': {
                'Name': self.region.name,
            },
            'Catchment': {
                'Name': self.catchment.name,
                'Description': self.catchment.description
            },
            'Description': self.description,
        }
        return summary


class InventoryAmountShare(OwnedObjectModel):
    scenario = models.ForeignKey(Scenario, null=True, on_delete=models.CASCADE)
    feedstock = models.ForeignKey(SampleSeries, null=True,
                                  on_delete=models.CASCADE)  # TODO: Check if Material can be used, instead
    timestep = models.ForeignKey(Timestep, null=True, on_delete=models.CASCADE)
    average = models.FloatField(default=0.0)
    standard_deviation = models.FloatField(default=0.0)


@receiver(pre_save, sender=Scenario)
def block_running_scenario(sender, instance, **kwargs):
    """Checks if a scenario is being evaluated before it can be saved."""
    if hasattr(instance, 'status'):
        if instance.status == ScenarioStatus.Status.RUNNING:
            raise BlockedRunningScenario


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


class ScenarioConfiguration(OwnedObjectModel):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    feedstock = models.ForeignKey(SampleSeries, on_delete=models.CASCADE, null=True)
    geodataset = models.ForeignKey(GeoDataset, on_delete=models.CASCADE)
    algorithm = models.ForeignKey(Algorithm, on_delete=models.CASCADE)
    inventory_parameter = models.ForeignKey(Parameter, on_delete=models.CASCADE, null=True)  # TODO: remove
    inventory_value = models.ForeignKey(ParameterValue, on_delete=models.CASCADE, null=True)  # TODO: remove
    parameter_settings = models.ManyToManyField(ParameterValue, through='ScenarioParameterSetting',
                                                related_name='parameter_settings')

    def save(self, *args, **kwargs):
        # TODO: The status must also be changed, when any of the referenced foreign key objects change
        self.scenario.set_status(ScenarioStatus.Status.CHANGED)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return self.scenario.get_absolute_url()


@receiver(post_save, sender=ScenarioConfiguration)
def set_default_parameters(sender, instance, created, **kwargs):
    if created:
        for parameter in instance.algorithm.parameters.all():
            ScenarioParameterSetting.objects.create(
                scenario_configuration=instance,
                parameter_value=parameter.default_value
            )


class ScenarioParameterSetting(OwnedObjectModel):
    scenario_configuration = models.ForeignKey(ScenarioConfiguration, on_delete=models.CASCADE)
    parameter_value = models.ForeignKey(ParameterValue, on_delete=models.CASCADE)
    custom_value = models.CharField(max_length=255, blank=True, null=True)


class RunningTask(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    algorithm = models.ForeignKey(Algorithm, on_delete=models.CASCADE, null=True)
    uuid = models.UUIDField(primary_key=False)
