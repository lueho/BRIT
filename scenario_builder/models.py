import importlib

from django.contrib.auth.models import User
from django.contrib.gis.db.models import MultiPolygonField, PointField
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.query import QuerySet
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.urls import reverse

import case_studies
from material_manager.models import Material, MaterialSettings
from .exceptions import BlockedRunningScenario

TYPES = (
    ('administrative', 'administrative'),
    ('custom', 'custom'),
)

GIS_SOURCE_MODELS = (
    ('HamburgRoadsideTrees', 'HamburgRoadsideTrees'),
    ('HamburgGreenAreas', 'HamburgGreenAreas'),
    ('NantesGreenhouses', 'NantesGreenhouses')
)


# ----------- Geodata --------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class Region(models.Model):
    name = models.CharField(max_length=56, null=False)
    country = models.CharField(max_length=56, null=False)
    geom = MultiPolygonField(null=True)

    @staticmethod
    def get_absolute_url():
        return reverse('catchment_list')

    def __str__(self):
        return self.name


class Catchment(models.Model):
    name = models.CharField(max_length=256, default="Custom Catchment")
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    description = models.TextField(blank=True, null=True)
    type = models.CharField(max_length=14, choices=TYPES, default='custom')
    geom = MultiPolygonField()

    @staticmethod
    def get_absolute_url():
        return reverse('catchment_list')

    def __str__(self):
        return self.name


class SFBSite(models.Model):
    name = models.CharField(max_length=20, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    geom = PointField(null=True)

    def __str__(self):
        return self.name


class GeoDataset(models.Model):
    """
    Holds meta information about datasets from the core module or scenario extensions.
    """
    name = models.CharField(max_length=56, null=False)
    description = models.TextField(blank=True, null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=False)
    model_name = models.CharField(max_length=56, choices=GIS_SOURCE_MODELS, null=True)

    def get_absolute_url(self):
        return reverse(f'{self.model_name}')

    def __str__(self):
        return self.name


class InventoryAlgorithm(models.Model):
    """
    Links functions that are defined in the InventoryMixin to the corresponding geodatasets and feedstocks in the
    database. This model is for configuration by admins and must not be available to users. Customization by users can
    be done in InventoryAlgorithmParameter and InventoryAlgorithmParameterValue.
    """
    name = models.CharField(max_length=56)
    source_module = models.CharField(max_length=255, null=True)
    function_name = models.CharField(max_length=56, null=True)
    description = models.TextField(blank=True, null=True)
    geodataset = models.ForeignKey(GeoDataset, on_delete=models.CASCADE)  # TODO: Make many2many?
    feedstock = models.ManyToManyField(Material, limit_choices_to={'is_feedstock': True})  # TODO: rename to plural
    default = models.BooleanField('Default for this combination of geodataset and feedstock', default=False)
    source = models.CharField(max_length=200, blank=True, null=True)  # TODO: connect to library

    # TODO: How are default values controlled?

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
        for parameter in self.inventoryalgorithmparameter_set.all():
            if parameter not in values.keys():
                values[parameter] = []
            for value in InventoryAlgorithmParameterValue.objects.filter(parameter=parameter, default=True):
                values[parameter].append(value)
        return values

    def __str__(self):
        return self.name


class InventoryAlgorithmParameter(models.Model):
    descriptive_name = models.CharField(max_length=56)
    short_name = models.CharField(max_length=28,
                                  validators=[RegexValidator(regex=r'^\w{1,28}$',
                                                             message='Invalid parameter short_name. Do not use space'
                                                                     'or special characters.',
                                                             code='invalid_parameter_name')])
    description = models.TextField(blank=True, null=True)
    inventory_algorithm = models.ManyToManyField(InventoryAlgorithm)  # TODO: convert to foreign key
    unit = models.CharField(max_length=20, blank=True, null=True)
    is_required = models.BooleanField(default=False)

    def default_value(self):
        return InventoryAlgorithmParameterValue.objects.get(parameter=self, default=True)

    def __str__(self):
        return self.short_name


class InventoryAlgorithmParameterValue(models.Model):
    name = models.CharField(max_length=56)
    description = models.TextField(blank=True, null=True)
    parameter = models.ForeignKey(InventoryAlgorithmParameter, on_delete=models.CASCADE, null=True)
    value = models.FloatField()
    standard_deviation = models.FloatField(null=True)
    source = models.CharField(max_length=200, blank=True, null=True)  # TODO: connect to library
    default = models.BooleanField(default=False)

    def __str__(self):
        return self.name


@receiver(pre_save, sender=InventoryAlgorithmParameterValue)
def auto_default(sender, instance, **kwargs):
    """
    Makes sure that defaults are always set correctly, even if the user provides incoherent input.
    """
    # If there is no default, yet, make the new instance default
    if not instance.default:
        if not instance.parameter.inventoryalgorithmparametervalue_set.exclude(id=instance.id).filter(default=True):
            instance.default = True


@receiver(post_save, sender=InventoryAlgorithmParameterValue)
def manage_scenario_status(sender, instance, created, **kwargs):
    """
    Makes sure that defaults are always set correctly, even if the user provides incoherent input.
    """
    # If the new instance is set to default and there are other old defaults, override them.
    if instance.default:
        for val in instance.parameter.inventoryalgorithmparametervalue_set.exclude(id=instance.id).filter(default=True):
            val.default = False
            val.save()


class ScenarioConfigurationError(Exception):
    pass


class WrongParameterForInventoryAlgorithm(Exception):
    def __init__(self, value):
        f"""The provided value: {value} does not belong to a parameter of the chosen algorithm."""


class FeedstockNotImplemented(Exception):
    def __init__(self, feedstock):
        f"""The feedstock: {feedstock} cannot be included because there is not dataset and or 
        algorithm for it in this region"""


SCENARIO_STATUS = (
    ('administrative', 'administrative'),
    ('custom', 'custom'),
)


class ScenarioStatus(models.Model):
    class Status(models.IntegerChoices):
        CHANGED = 1
        RUNNING = 2
        FINISHED = 3

    scenario = models.OneToOneField('Scenario', on_delete=models.CASCADE, null=True)
    status = models.IntegerField(choices=Status.choices, default=Status.CHANGED)

    def __str__(self):
        return f'Status of Scenario {self.scenario}: {self.status}'


class Scenario(models.Model):
    name = models.CharField(max_length=56, default='Custom Scenario')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    description = models.TextField(blank=True, null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=True)
    site = models.ForeignKey(SFBSite, on_delete=models.CASCADE, null=True)  # TODO: make many-to-many?
    catchment = models.ForeignKey(Catchment, on_delete=models.CASCADE, null=True)  # TODO: make many-to-many?

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

    def available_feedstocks(self):
        """
        Returns all materials that can be included in this scenario.
        """
        materials = Material.objects.filter(id__in=self.available_inventory_algorithms().values('feedstock'))
        return MaterialSettings.objects.filter(material__in=materials)

    def feedstocks(self):
        """
        Returns all materials (MaterialSettings) that have been included in this scenario.
        """
        return MaterialSettings.objects.filter(id__in=self.scenarioinventoryconfiguration_set.all().values('feedstock'))

    def available_geodatasets(self, feedstock: Material = None, feedstocks: QuerySet = None):
        """
        Returns a queryset of geodatasets that can be used in this scenario. By providing either a Material object or
        a queryset of Materials as keyword argument feedstock/feedstocks respectively, the query is reduced to
        geodatasets which have algorithms for these given feedstocks.
        """
        if feedstocks is None and feedstock is None:
            feedstocks = Material.objects.feedstocks()
        elif feedstocks is None and feedstock is not None:
            feedstocks = Material.objects.filter(id=feedstock.id)

        return GeoDataset.objects.filter(
            id__in=InventoryAlgorithm.objects.filter(
                feedstock__in=feedstocks, geodataset__region=self.region).values('geodataset'))

    def evaluated_geodatasets(self, feedstock: Material = None, feedstocks: QuerySet = None):
        if feedstocks is None and feedstock is None:
            feedstocks = Material.objects.feedstocks()
        elif feedstocks is None and feedstock is not None:
            feedstocks = Material.objects.filter(id=feedstock.id)
        return GeoDataset.objects.filter(
            id__in=ScenarioInventoryConfiguration.objects.filter(
                scenario=self, feedstock__material__in=feedstocks).values('geodataset'))

    def remaining_geodataset_options(self, feedstock: Material = None, feedstocks: QuerySet = None):
        if feedstocks is None and feedstock is None:
            feedstocks = Material.objects.feedstocks()
        elif feedstocks is None and feedstock is not None:
            feedstocks = Material.objects.filter(id=feedstock.id)
        return self.available_geodatasets(
            feedstocks=feedstocks).difference(self.evaluated_geodatasets(feedstocks=feedstocks))

    def available_inventory_algorithms(self,
                                       feedstock: Material = None,
                                       feedstocks: QuerySet = None,
                                       geodataset: GeoDataset = None,
                                       geodatasets: QuerySet = None):

        if feedstocks is None and feedstock is None:
            feedstocks = Material.objects.feedstocks()
        elif feedstocks is None and feedstock is not None:
            feedstocks = Material.objects.filter(id=feedstock.id)

        if geodatasets is None and geodataset is None:
            geodatasets = GeoDataset.objects.all()
        elif geodatasets is None and geodataset is not None:
            geodatasets = GeoDataset.objects.filter(id=geodataset.id)

        geodatasets = geodatasets.filter(region=self.region)

        return InventoryAlgorithm.objects.filter(feedstock__in=feedstocks, geodataset__in=geodatasets)

    def evaluated_inventory_algorithms(self):
        return InventoryAlgorithm.objects.filter(
            id__in=ScenarioInventoryConfiguration.objects.filter(scenario=self).values('inventory_algorithm'))

    def remaining_inventory_algorithm_options(self, feedstock, geodataset):

        if ScenarioInventoryConfiguration.objects.filter(scenario=self, feedstock=feedstock, geodataset=geodataset):
            return InventoryAlgorithm.objects.none()
        else:
            return InventoryAlgorithm.objects.filter(feedstock=feedstock.material, geodataset=geodataset)

    def default_inventory_algorithms(self):
        return InventoryAlgorithm.objects.filter(geodataset__region=self.region,
                                                 default=True)

    def inventory_algorithm_config(self, algorithm):
        return {
            'scenario': self,
            'feedstocks': Material.objects.filter(id__in=[c['feedstock_id'] for c in
                                                          self.scenarioinventoryconfiguration_set.filter(
                                                              inventory_algorithm=algorithm).values()]),
            'geodataset': algorithm.geodataset,
            'inventory_algorithm': algorithm,
            'parameters': [{conf.inventory_parameter.id: conf.inventory_value.id} for conf in
                           ScenarioInventoryConfiguration.objects.filter(scenario=self, inventory_algorithm=algorithm)]
        }

    def add_inventory_algorithm(self, feedstock: Material, algorithm: InventoryAlgorithm, custom_parameter_values=None):
        """
        Adds an inventory algorithm to and the given parameter values to the scenario configuration. If no
        parameter values are given, the algorithm will be added with default values.
        """

        # self.remove_inventory_algorithm(algorithm, feedstock)

        if feedstock not in self.available_feedstocks():
            raise FeedstockNotImplemented(algorithm.feedstock)

        if custom_parameter_values:
            # for value in custom_parameter_values:
            #     if not value.parameter.inventory_algorithm == algorithm:
            #         raise WrongParameterForInventoryAlgorithm(value)
            values = custom_parameter_values
        else:
            values = algorithm.default_values()

        if not values:
            config = {
                'scenario': self,
                'feedstock': feedstock,
                'geodataset': algorithm.geodataset,
                'inventory_algorithm': algorithm,
            }
            ScenarioInventoryConfiguration.objects.create(**config)
            return

        for parameter, value_list in values.items():
            for value in value_list:
                config = {
                    'scenario': self,
                    'feedstock': feedstock,
                    'geodataset': algorithm.geodataset,
                    'inventory_algorithm': algorithm,
                    'inventory_parameter': parameter,
                    'inventory_value': value
                }
                ScenarioInventoryConfiguration.objects.create(**config)

    def remove_inventory_algorithm(self, algorithm: InventoryAlgorithm, feedstock: MaterialSettings):
        """
        Remove all entries from the configuration that are associated with the given algorithm.
        """
        for config_entry in ScenarioInventoryConfiguration.objects.filter(scenario=self,
                                                                          inventory_algorithm=algorithm,
                                                                          feedstock=feedstock):
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
        for config_entry in ScenarioInventoryConfiguration.objects.filter(scenario=self):
            config_entry.delete()

    def reset_configuration(self):
        self.delete_configuration()
        self.create_default_configuration()

    def is_valid_configuration(self):
        # At least one entry for a scenario
        if not ScenarioInventoryConfiguration.objects.filter(scenario=self):
            raise ScenarioConfigurationError('The scenario is not configured.')

        # Get all inventory algorithms that are used in this scenario
        algorithms = [c.inventory_algorithm for c in
                      ScenarioInventoryConfiguration.objects.filter(scenario=self).distinct('inventory_algorithm')]

        # Are all required parameters included in the configuration?
        required = \
            InventoryAlgorithmParameter.objects.filter(inventory_algorithm__in=algorithms, is_required=True) \
                .values_list('id')
        configured = \
            ScenarioInventoryConfiguration.objects.filter(inventory_algorithm__in=algorithms) \
                .values_list('inventory_parameter')
        if not set(required).issubset(configured):
            raise ScenarioConfigurationError('Not all required parameters are defined.')

        # Is each parameter only defined once per scenario?
        if not len(set(configured)) == len(configured):
            raise ScenarioConfigurationError('There are double defined parameters in the configuration')

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

    def configuration_as_dict(self):
        """
        Fetches all configuration entries that are associated with this scenario and assembles a dictionary holding
        all configuration information for the inventory.
        :return: None
        """

        inventory_config = {}
        for entry in ScenarioInventoryConfiguration.objects.filter(scenario=self):
            feedstock = entry.feedstock.id
            function = 'case_studies.' + \
                       entry.inventory_algorithm.source_module + \
                       '.algorithms:' + \
                       entry.inventory_algorithm.function_name
            parameter = entry.inventory_parameter.short_name if entry.inventory_parameter else None
            if entry.inventory_value:
                value = entry.inventory_value.value
                standard_deviation = entry.inventory_value.standard_deviation

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
        for entry in ScenarioInventoryConfiguration.objects.filter(scenario=self):
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

    @property
    def detail_url(self):
        return self.get_absolute_url()

    @property
    def update_url(self):
        return reverse('scenario_update', kwargs={'pk': self.id})

    @property
    def delete_url(self):
        return reverse('scenario_delete', kwargs={'pk': self.id})

    def get_absolute_url(self):
        return reverse('scenario_detail', kwargs={'pk': self.id})

    def __str__(self):
        return self.name


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


class ScenarioInventoryConfiguration(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    feedstock = models.ForeignKey(MaterialSettings, on_delete=models.CASCADE, null=True)
    geodataset = models.ForeignKey(GeoDataset, on_delete=models.CASCADE)
    inventory_algorithm = models.ForeignKey(InventoryAlgorithm, on_delete=models.CASCADE)
    inventory_parameter = models.ForeignKey(InventoryAlgorithmParameter, on_delete=models.CASCADE, null=True)
    inventory_value = models.ForeignKey(InventoryAlgorithmParameterValue, on_delete=models.CASCADE, null=True)

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
        return reverse('scenario_detail', kwargs={'pk': self.scenario.pk})
