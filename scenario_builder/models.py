from django.contrib.auth.models import User
from django.contrib.gis.db.models import MultiPolygonField, PointField
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.db.models.query import QuerySet
from django.urls import reverse

TYPES = (
    ('administrative', 'administrative'),
    ('custom', 'custom'),
)

GIS_SOURCE_MODELS = (
    ('HamburgRoadsideTrees', 'HamburgRoadsideTrees'),
    ('HamburgGreenAreas', 'HamburgGreenAreas')
)


class Region(models.Model):
    name = models.CharField(max_length=56, null=False)
    country = models.CharField(max_length=56, null=False)
    geom = MultiPolygonField(null=True)

    def __str__(self):
        return self.name


class Catchment(models.Model):
    name = models.CharField(max_length=256, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=True)
    description = models.TextField(blank=True, null=True)
    type = models.CharField(max_length=14, choices=TYPES, default='custom', null=True)
    geom = MultiPolygonField(null=True)

    def __str__(self):
        return self.name


class MaterialManager(models.Manager):

    def feedstocks(self):
        return self.filter(is_feedstock=True)


class Material(models.Model):
    name = models.CharField(max_length=28)
    description = models.TextField(blank=True, null=True)
    is_feedstock = models.BooleanField(default=False)
    stan_flow_id = models.CharField(max_length=5,
                                    validators=[RegexValidator(regex=r'^[0-9]{5}?',
                                                               message='STAN id must have 5 digits.s',
                                                               code='invalid_stan_id')])

    objects = MaterialManager()

    def __str__(self):
        return self.name


class MaterialComponent(models.Model):
    name = models.CharField(max_length=20)
    description = models.TextField(blank=True, null=True)
    average = models.FloatField()
    standard_deviation = models.FloatField(null=True)
    source = models.CharField(max_length=20)
    material = models.ForeignKey(Material, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class GeoDataset(models.Model):
    name = models.CharField(max_length=56, null=False)
    description = models.TextField(blank=True, null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=False)
    model_name = models.CharField(max_length=56, choices=GIS_SOURCE_MODELS, null=True)

    def __str__(self):
        return self.name


class SFBSite(models.Model):
    name = models.CharField(max_length=20, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    geom = PointField(null=True)

    def __str__(self):
        return self.name


class InventoryAlgorithm(models.Model):
    """
    Links functions that are defined in the InventoryMixin to the corresponding geodatasets and feedstocks in the
    database. This model is for configuration by admins and must not be available to users. Customization by users can
    be done in InventoryAlgorithmParameter and InventoryAlgorithmParameterValue.
    """
    name = models.CharField(max_length=56)
    function_name = models.CharField(max_length=56, null=True)
    description = models.TextField(blank=True, null=True)
    geodataset = models.ForeignKey(GeoDataset, on_delete=models.CASCADE)
    feedstock = models.ForeignKey(Material, on_delete=models.CASCADE, limit_choices_to={'is_feedstock': True})
    default = models.BooleanField('Default for this combination of geodataset and feedstock', default=False)
    source = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return self.name

    def default_values(self):
        """
        Returns a queryset of all default values of parameters of this algorithm.
        """
        return InventoryAlgorithmParameterValue.objects.filter(parameter__inventory_algorithm=self, default=True)

    def save(self, *args, **kwargs):
        """
        There can only be one default algorithm per geodataset/feedstock combination. This method adds a corresponding
        check when a record is saved. It gets rid of any previous default entry with the same geodataset/feedstock
        combination when the new algorithm is marked as default.
        """
        if not self.default:
            if not InventoryAlgorithm.objects.filter(geodataset=self.geodataset, feedstock=self.feedstock,
                                                     default=True):
                self.default = True
            return super(InventoryAlgorithm, self).save(*args, **kwargs)
        with transaction.atomic():
            InventoryAlgorithm.objects.filter(geodataset=self.geodataset, feedstock=self.feedstock, default=True) \
                .update(default=False)
            return super(InventoryAlgorithm, self).save(*args, **kwargs)


class InventoryAlgorithmParameter(models.Model):
    short_name = models.CharField(max_length=28,
                                  validators=[RegexValidator(regex=r'^\w{1,28}$',
                                                             message='Invalid parameter short_name. Do not use space'
                                                                     'or special characters.',
                                                             code='invalid_parameter_name')])
    descriptive_name = models.CharField(max_length=56)
    description = models.TextField(blank=True, null=True)
    inventory_algorithm = models.ForeignKey(InventoryAlgorithm, on_delete=models.CASCADE, null=True)
    unit = models.CharField(max_length=20, blank=True, null=True)
    is_required = models.BooleanField(default=False)

    def __str__(self):
        return self.short_name

    def default_value(self):
        return InventoryAlgorithmParameterValue.objects.get(parameter=self, default=True)


class InventoryAlgorithmParameterValue(models.Model):
    name = models.CharField(max_length=56)
    description = models.TextField(blank=True, null=True)
    parameter = models.ForeignKey(InventoryAlgorithmParameter, on_delete=models.CASCADE)
    value = models.FloatField()
    standard_deviation = models.FloatField(null=True)
    source = models.CharField(max_length=200, blank=True, null=True)
    default = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        """
        There can only be one default value for each parameter. This method checks if the default value has changed
        and enforces uniqueness.
        """
        if not self.default:
            if not InventoryAlgorithmParameterValue.objects.filter(parameter=self.parameter, default=True):
                self.default = True
            return super(InventoryAlgorithmParameterValue, self).save(*args, **kwargs)
        with transaction.atomic():
            InventoryAlgorithmParameterValue.objects.filter(parameter=self.parameter, default=True).update(
                default=False)
            return super(InventoryAlgorithmParameterValue, self).save(*args, **kwargs)

    def __str__(self):
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


class ScenarioManager(models.Manager):

    def create(self, **kwargs):
        scenario = super().create(**kwargs)
        return scenario


class Scenario(models.Model):
    name = models.CharField(max_length=56, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    description = models.TextField(blank=True, null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=True)
    site = models.ForeignKey(SFBSite, on_delete=models.CASCADE, null=True)  # TODO: make many-to-many?
    catchment = models.ForeignKey(Catchment, on_delete=models.CASCADE, null=True)  # TODO: make many-to-many?

    objects = ScenarioManager()

    def available_feedstocks(self):
        return Material.objects.filter(id__in=self.available_inventory_algorithms().values('feedstock'))

    def included_feedstocks(self):
        return Material.objects.filter(
            id__in=ScenarioInventoryConfiguration.objects.filter(scenario=self).values('feedstock'))

    def add_feedstock(self, feedstock: Material):
        # not needed anymore. Each feedstock is added automatically with an associated inventory_algorithm.
        # No feedstocks should be added witout inventory_algorihtm
        pass

    def remaining_feedstock_options(self):
        pass

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
                scenario=self, feedstock__in=feedstocks).values('geodataset'))

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
            return InventoryAlgorithm.objects.filter(feedstock=feedstock, geodataset=geodataset)

    def default_inventory_algorithms(self):
        return InventoryAlgorithm.objects.filter(geodataset__region=self.region,
                                                 default=True)

    def inventory_algorithm_config(self, algorithm):
        return {
            'scenario': self,
            'feedstock': algorithm.feedstock,
            'geodataset': algorithm.geodataset,
            'inventory_algorithm': algorithm,
            'parameters': [{conf.inventory_parameter.id: conf.inventory_value.id} for conf in
                           ScenarioInventoryConfiguration.objects.filter(scenario=self, inventory_algorithm=algorithm)]
        }

    def add_inventory_algorithm(self, algorithm: InventoryAlgorithm, custom_parameter_values=None):
        """
        Adds an inventory algorithm to and the given parameter values to the scenario configuration. If no
        parameter values are given, the algorithm will be added with default values.
        """

        self.remove_inventory_algorithm(algorithm)

        if algorithm.feedstock not in self.available_feedstocks():
            raise FeedstockNotImplemented(algorithm.feedstock)

        if custom_parameter_values:
            for value in custom_parameter_values:
                if not value.parameter.inventory_algorithm == algorithm:
                    raise WrongParameterForInventoryAlgorithm(value)
            values = custom_parameter_values
        else:
            values = algorithm.default_values()

        for value in values:
            config = {
                'scenario': self,
                'feedstock': algorithm.feedstock,
                'geodataset': algorithm.geodataset,
                'inventory_algorithm': algorithm,
                'inventory_parameter': value.parameter,
                'inventory_value': value
            }
            ScenarioInventoryConfiguration.objects.create(**config)

    def remove_inventory_algorithm(self, algorithm: InventoryAlgorithm):
        """
        Remove all entries from the configuration that are associated with the given algorithm.
        """
        for config_entry in ScenarioInventoryConfiguration.objects.filter(scenario=self,
                                                                          inventory_algorithm=algorithm):
            config_entry.delete()

    def delete(self):
        self.delete_configuration()  # TODO: Does this happen automatically through cascading?
        super().delete()

    def delete_result_layers(self):
        for layer in self.layer_set.all():
            layer.delete()

    def delete_configuration(self):
        """
        Removes all entries from the configuration that are associated with this scenario. Handle with care!
        An unconfigured scenario will lead to unexpected behaviour.
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
            function = entry.inventory_algorithm.function_name
            parameter = entry.inventory_parameter.short_name
            value = entry.inventory_value.value
            standard_deviation = entry.inventory_value.standard_deviation

            if function not in inventory_config.keys():
                inventory_config[function] = {}
                inventory_config[function]['catchment_id'] = self.catchment.id
                inventory_config[function]['scenario_id'] = self.id
            if parameter not in inventory_config[function]:
                inventory_config[function][parameter] = {'value': value, 'standard_deviation': standard_deviation}

        return inventory_config

    def configuration_for_template(self):

        config = {}
        for entry in ScenarioInventoryConfiguration.objects.filter(scenario=self):
            algorithm = entry.inventory_algorithm
            feedstock = algorithm.feedstock
            parameter = entry.inventory_parameter
            value = entry.inventory_value

            if algorithm not in config.keys():
                config[algorithm] = {}
            if parameter not in config[algorithm]:
                config[algorithm][parameter] = value

        return config

    def result_features_collections(self):
        return [layer.get_feature_collection() for layer in self.layer_set()]

    def get_absolute_url(self):
        return reverse('scenario_detail', kwargs={'pk': self.pk})

    def __str__(self):
        return self.name


class ScenarioInventoryConfiguration(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    feedstock = models.ForeignKey(Material, limit_choices_to={'is_feedstock': True}, on_delete=models.CASCADE)
    geodataset = models.ForeignKey(GeoDataset, on_delete=models.CASCADE)
    inventory_algorithm = models.ForeignKey(InventoryAlgorithm, on_delete=models.CASCADE)
    inventory_parameter = models.ForeignKey(InventoryAlgorithmParameter, on_delete=models.CASCADE)
    inventory_value = models.ForeignKey(InventoryAlgorithmParameterValue, on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        # Only save if there is no previous entry for a parameter in a scenario. Otherwise drop old entry first.
        if not ScenarioInventoryConfiguration.objects.filter(scenario=self.scenario,
                                                             inventory_algorithm=self.inventory_algorithm,
                                                             inventory_parameter=self.inventory_parameter):
            super(ScenarioInventoryConfiguration, self).save(*args, **kwargs)
        else:
            ScenarioInventoryConfiguration.objects \
                .filter(scenario=self.scenario,
                        inventory_algorithm=self.inventory_algorithm,
                        inventory_parameter=self.inventory_parameter) \
                .update(inventory_value=self.inventory_value)

    def get_absolute_url(self):
        return reverse('scenario_detail', kwargs={'pk': self.scenario.pk})
