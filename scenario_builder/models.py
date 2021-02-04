import importlib

import django_tables2 as tables
from django.contrib.auth.models import User
from django.contrib.gis.db.models import MultiPolygonField, PointField
from django.contrib.postgres.fields import ArrayField
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.query import QuerySet
from django.db.models.signals import pre_save, post_save, m2m_changed
from django.dispatch import receiver
from django.urls import reverse
from django.utils.html import format_html

import case_studies
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


class SeasonalDistribution(models.Model):
    """
    Model to deal with different types of input data that represent seasonal distribution of any kind. Input and output
    with differing time steps and start-stop-cycles can be managed. All entries are with reference to one year.
    """
    # Into how many timesteps is the full year divided? e.g. 12 months, 365 days etc
    # The values array must have the same length, filled with zeros, of not applicable to whole year
    timesteps = models.IntegerField(default=12)
    # Within one year, how many cycles are represented by the given data?
    cycles = models.IntegerField(default=1)
    # In which timestep does each cycle start and end? array must have form [start1, end1, start2, end2, ...]
    start_stop = ArrayField(models.IntegerField(), default=list([1, 12]))
    values = ArrayField(models.FloatField(), default=list([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]))


class TemporalDistribution(models.Model):
    """
    Model to organize timesteps into named distributions (e.g. months are timesteps of the temporal distribution 'months
    of the year').
    """
    name = models.CharField(max_length=255, blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Timestep(models.Model):
    """
    Defines a timestep for organisation of seasonal distributions
    """
    name = models.CharField(max_length=255, blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    distribution = models.ForeignKey(TemporalDistribution, default=1, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Region(models.Model):
    name = models.CharField(max_length=56, null=False)
    country = models.CharField(max_length=56, null=False)
    geom = MultiPolygonField(null=True)

    def __str__(self):
        return self.name


class Catchment(models.Model):
    name = models.CharField(max_length=256, default="Custom Catchment")
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    description = models.TextField(blank=True, null=True)
    type = models.CharField(max_length=14, choices=TYPES, default='custom')
    geom = MultiPolygonField()

    def __str__(self):
        return self.name


class LiteratureSource(models.Model):
    authors = models.CharField(max_length=500, null=True)
    title = models.CharField(max_length=500, null=True)
    abbreviation = models.CharField(max_length=50, null=True)

    def __str__(self):
        return self.abbreviation


# ----------- Materials ------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class MaterialManager(models.Manager):

    def feedstocks(self):
        return self.filter(is_feedstock=True)


class Material(models.Model):
    """
    Holds all materials used
    """
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    is_feedstock = models.BooleanField(default=False)
    stan_flow_id = models.CharField(max_length=5,
                                    blank=True,
                                    null=True,
                                    validators=[RegexValidator(regex=r'^[0-9]{5}?',
                                                               message='STAN id must have 5 digits.s',
                                                               code='invalid_stan_id')])

    objects = MaterialManager()

    def component_groups(self, scenario=None):
        """
        :param scenario:
        :return: [MaterialComponentGroup]
        """
        return [group for group in self.grouped_component_shares(scenario=scenario).keys()]

    def grouped_component_shares(self, scenario=None):
        group_settings = MaterialComponentGroupSettings.objects.filter(material=self, scenario=scenario)

        grouped_shares = {}
        for setting in group_settings:
            grouped_shares[setting.group] = {
                'shares': []
            }
            for share in MaterialComponentShare.objects.filter(group_settings=setting):
                grouped_shares[setting.group]['shares'].append(share)

        return grouped_shares

    def grouped_component_shares_settings(self, scenario=None):
        if scenario is None:
            scenario = Scenario.objects.get(id=0)

        group_settings = MaterialComponentGroupSettings.objects.filter(material=self, scenario=scenario)

        grouped_shares = {}
        for setting in group_settings:
            grouped_shares[setting] = {
                'averages': [],
                'averages_table': setting.averages_table_class(),
                'distribution_tables': setting.distribution_table_classes()
            }
            for share in MaterialComponentShare.objects.filter(group_settings=setting,
                                                               timestep=Timestep.objects.get(name='Average')):
                grouped_shares[setting]['averages'].append(share)

        return grouped_shares

    def distribution_tables_data(self, scenario=None):
        if scenario is None:
            scenario = Scenario.objects.get(id=0)
        table_list = []
        group_settings = MaterialComponentGroupSettings.objects.filter(scenario=scenario, material=self)
        for setting in group_settings:
            table_list.append(setting.distribution_table_data())
        return table_list

    def __str__(self):
        return self.name


class MaterialComponent(models.Model):
    """
    Represents any kind of component that a material can consists of (e.g. water, any kind of chemical element
    or more complex components, such as carbohydrates)
    """
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class MaterialComponentGroup(models.Model):
    """
    Container model to group MaterialComponent instances
    """
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class MaterialComponentGroupSettings(models.Model):
    """
    Utility model to store the settings for component groups for each material in each scenario. This model is not
    supposed to be edited directly by a user. It depends on user objects and must be deleted, when any of the user
    objects it depends on is deleted.
    """

    group = models.ForeignKey(MaterialComponentGroup, null=True, on_delete=models.CASCADE)
    material = models.ForeignKey(Material, null=True, on_delete=models.CASCADE)
    scenario = models.ForeignKey('Scenario', null=True, on_delete=models.CASCADE)
    temporal_distributions = models.ManyToManyField(TemporalDistribution)
    fractions_of = models.ForeignKey(MaterialComponent, on_delete=models.CASCADE, default=1)

    # TODO: Restrain fractions_of:
    #  ==> component must be configured for the material-scenario combination
    #  ==> component must not be included in the same group (no circular reference)

    def components(self):
        component_ids = [share['component'] for share in
                         self.materialcomponentshare_set.values('component').distinct()]
        return MaterialComponent.objects.filter(id__in=component_ids)

    def add_component_to_distributions(self, share):
        for distribution in self.temporal_distributions.all():
            timesteps = distribution.timestep_set.all()
            for timestep in timesteps:
                MaterialComponentShare.objects.create(component=share.component,
                                                      group_settings=self,
                                                      timestep=timestep,
                                                      average=share.average,
                                                      standard_deviation=share.standard_deviation)

    def remove_component(self, component):
        self.materialcomponentshare_set.filter(component=component).delete()

    @property
    def temporal_distribution_ids(self):
        return [dist.id for dist in self.temporal_distributions.all()]

    def add_temporal_distribution(self, distribution):
        """
        Adds shares for all timesteps of a new distribution for all components of this group. This is meant to be
        called by the m2m_changed signal but can be called manually as well.
        :param distribution:
        :return:
        """
        # In case this method is called manually and not by m2m_changed
        if distribution not in self.temporal_distributions.all():
            self.temporal_distributions.add(distribution)

        # Use average and standard deviation of component averages as default values for all timesteps
        average_timestep = Timestep.objects.get(name='Average')
        for component in self.components():
            average_share = MaterialComponentShare.objects.get(component=component,
                                                               group_settings=self,
                                                               timestep=average_timestep)
            for timestep in distribution.timestep_set.all():
                MaterialComponentShare.objects.create(component=component,
                                                      group_settings=self,
                                                      timestep=timestep,
                                                      average=average_share.average,
                                                      standard_deviation=average_share.standard_deviation)

    def remove_temporal_distribution(self, distribution):
        if distribution in self.temporal_distributions.all():
            self.temporal_distributions.remove(distribution)
        self.materialcomponentshare_set.filter(timestep__in=distribution.timestep_set.all()).delete()

    def shares(self):
        return self.materialcomponentshare_set.all()

    def averages_table_data(self):
        timestep = Timestep.objects.get(name='Average')
        table_data = []
        for component in self.components():
            share = MaterialComponentShare.objects.get(component=component, group_settings=self, timestep=timestep)
            source_name = None
            if share.source:
                source_name = share.source.abbreviation
            edit_html = format_html(
                '''
                <a href="{0}">
                    <i class="fas fa-fw fa-edit"></i>
                </a>
                ''',
                reverse('material_component_group_share_update', kwargs={'pk': share.id})
            )
            remove_html = format_html(
                '''
                <a href="{0}">
                    <i class="fas fa-fw fa-trash"></i>
                </a>
                ''',
                reverse('material_component_group_share_remove_component', kwargs={'pk': share.id})
            )
            table_row = {
                'component': component.name,
                'weight fraction': f'{share.average} +- {share.standard_deviation}',
                'source': source_name,
                'edit': edit_html,
                'remove': remove_html
            }
            table_data.append(table_row)
        if len(table_data) == 0:
            table_data.append({
                'component': None,
                'weight fraction': None,
                'source': None
            })
        return table_data

    def averages_table_class(self):
        table_data = self.averages_table_data()

        add_component_html = format_html(
            '''
            <a href="{0}">
                <i class="fas fa-fw fa-plus"></i> Add component
            </a>
            ''',
            reverse('material_component_group_add_component', kwargs={
                'scenario_pk': self.scenario.id,
                'material_pk': self.material.id,
                'group_pk': self.group.id
            })
        )
        if len(table_data) > 0:
            columns = {name: (tables.Column(footer=add_component_html) if name == 'component' else tables.Column()) for
                       name in list(table_data[0].keys())}
        else:
            columns = {}
        table_class = type(f'AveragesTable{self.id}', (tables.Table,), columns)
        return table_class(table_data)

    def distribution_table_data(self, distribution):
        table_data = []
        for component in self.components():
            table_row = {'component': component.name}
            shares = self.materialcomponentshare_set.filter(
                component=component,
                timestep__in=distribution.timestep_set.all()
            )
            for share in shares:
                table_row[share.timestep.name] = f'{share.average}'
            table_data.append(table_row)
        if len('table_data') == 0:
            table_row = {'component': None}
            for timestep in distribution.timestep_set.all():
                table_row[timestep.name] = None
        return table_data

    def distribution_table_class(self, distribution):
        table_data = self.distribution_table_data(distribution)

        class EditableColumn(tables.Column):
            scenario = None
            material = None
            group = None

            def __init__(self, *args, **kwargs):
                self.scenario = kwargs.pop('scenario')
                self.material = kwargs.pop('material')
                self.group = kwargs.pop('group')
                super().__init__(*args, **kwargs)

            def render_footer(self, bound_column, table):
                return format_html(
                    '''
                    <a href="{0}">
                        <i class="fas fa-fw fa-edit"></i>
                    </a>
                    ''',
                    reverse('material_component_group_share_distribution_update',
                            kwargs={
                                'scenario_pk': self.scenario.id,
                                'material_pk': self.material.id,
                                'group_pk': self.group.id,
                                'timestep_pk': Timestep.objects.get(name=bound_column.accessor).id
                            }),
                )

        if len(table_data) > 0:
            columns = {name: EditableColumn(scenario=self.scenario, material=self.material, group=self.group) for name
                       in list(table_data[0].keys())}
            columns['id'] = f'distribution-table-group-{self.id}'
        else:
            columns = {}
        table_class = type(f'DistributionTable-{self.id}-{distribution.id}', (tables.Table,), columns)
        return table_class(table_data)

    def distribution_table_classes(self):
        return [self.distribution_table_class(distribution) for distribution in
                self.temporal_distributions.exclude(name='Average')]

    def __str__(self):
        return f'Group: {self.group.name}, material: {self.material.name}, scenario: {self.scenario.name}'


@receiver(m2m_changed, sender=MaterialComponentGroupSettings.temporal_distributions.through)
def initialize_added_temporal_distribution(sender, instance, action, pk_set, **kwargs):
    if action == 'post_add':
        for pk in pk_set:
            if not pk == 2:
                dist = TemporalDistribution.objects.get(id=pk)
                instance.add_temporal_distribution(dist)


class MaterialComponentShare(models.Model):
    """
    Utility model used to assign values to components for different group settings. This model is not
    supposed to be edited directly by a user. It depends on user objects and must be deleted, when any of the user
    objects it depends on is deleted.
    """
    component = models.ForeignKey(MaterialComponent, null=True, on_delete=models.CASCADE)
    group_settings = models.ForeignKey(MaterialComponentGroupSettings, null=True, on_delete=models.CASCADE)
    average = models.FloatField(null=True, default=0.0)
    standard_deviation = models.FloatField(null=True, default=0.0)
    timestep = models.ForeignKey(Timestep, blank=True, null=True, on_delete=models.CASCADE)
    source = models.ForeignKey(LiteratureSource, on_delete=models.CASCADE, null=True)

    @property
    def scenario(self):
        return self.group_settings.scenario

    @property
    def material(self):
        return self.group_settings.material

    @property
    def group(self):
        return self.group_settings.group

    def get_absolute_url(self):
        return reverse('material_detail', kwargs={'scenario_pk': self.scenario.id, 'material_pk': self.material.id})

    def __str__(self):
        return f'Material: {self.group_settings.material.name},\
         scenario: {self.group_settings.scenario.name}, component: {self.component.name}'


@receiver(post_save, sender=MaterialComponentShare)
def manage_distribution_shares(sender, instance, created, **kwargs):
    if created:
        if instance.timestep.name == 'Average':
            instance.group_settings.add_component_to_distributions(instance)
        return
    return


# ----------- Geodata --------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

class GeoDataset(models.Model):
    name = models.CharField(max_length=56, null=False)
    description = models.TextField(blank=True, null=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=False)
    model_name = models.CharField(max_length=56, choices=GIS_SOURCE_MODELS, null=True)

    def get_absolute_url(self):
        return reverse(self.model_name)

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
    source_module = models.CharField(max_length=255, null=True)
    function_name = models.CharField(max_length=56, null=True)
    description = models.TextField(blank=True, null=True)
    geodataset = models.ForeignKey(GeoDataset, on_delete=models.CASCADE)
    feedstock = models.ManyToManyField(Material, limit_choices_to={'is_feedstock': True})
    default = models.BooleanField('Default for this combination of geodataset and feedstock', default=False)
    source = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return self.name

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

    # def save(self, *args, **kwargs):
    #     """
    #     There can only be one default algorithm per geodataset/feedstock combination. This method adds a corresponding
    #     check when a record is saved. It gets rid of any previous default entry with the same geodataset/feedstock
    #     combination when the new algorithm is marked as default.
    #     """
    #     if not self.default:
    #         if not InventoryAlgorithm.objects.filter(geodataset=self.geodataset, feedstock=self.feedstock,
    #                                                  default=True):
    #             self.default = True
    #         return super(InventoryAlgorithm, self).save(*args, **kwargs)
    #     with transaction.atomic():
    #         InventoryAlgorithm.objects.filter(geodataset=self.geodataset, feedstock=self.feedstock, default=True) \
    #             .update(default=False)
    #         return super(InventoryAlgorithm, self).save(*args, **kwargs)


class InventoryAlgorithmParameter(models.Model):
    descriptive_name = models.CharField(max_length=56)
    short_name = models.CharField(max_length=28,
                                  validators=[RegexValidator(regex=r'^\w{1,28}$',
                                                             message='Invalid parameter short_name. Do not use space'
                                                                     'or special characters.',
                                                             code='invalid_parameter_name')])
    description = models.TextField(blank=True, null=True)
    inventory_algorithm = models.ManyToManyField(InventoryAlgorithm)
    unit = models.CharField(max_length=20, blank=True, null=True)
    is_required = models.BooleanField(default=False)

    def __str__(self):
        return self.short_name

    def default_value(self):
        return InventoryAlgorithmParameterValue.objects.get(parameter=self, default=True)


class InventoryAlgorithmParameterValue(models.Model):
    name = models.CharField(max_length=56)
    description = models.TextField(blank=True, null=True)
    parameter = models.ForeignKey(InventoryAlgorithmParameter, on_delete=models.CASCADE, null=True)
    value = models.FloatField()
    standard_deviation = models.FloatField(null=True)
    source = models.CharField(max_length=200, blank=True, null=True)
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


class ScenarioManager(models.Manager):

    def create(self, **kwargs):
        scenario = super().create(**kwargs)
        return scenario


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

    objects = ScenarioManager()

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
        return Material.objects.filter(id__in=self.available_inventory_algorithms().values('feedstock'))

    def included_feedstocks(self):
        return Material.objects.filter(
            id__in=ScenarioInventoryConfiguration.objects.filter(scenario=self).values('feedstock'))

    def feedstocks(self):
        used_feedstock_ids = [
            a['feedstock'] for a in ScenarioInventoryConfiguration.objects.filter(scenario=self)
                .order_by()
                .values('feedstock')
                .distinct()
        ]
        return Material.objects.filter(id__in=used_feedstock_ids)

    def add_feedstock(self, feedstock: Material):
        # not needed anymore. Each feedstock is added automatically with an associated inventory_algorithm.
        # No feedstocks should be added without inventory_algorithm
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

    def remove_inventory_algorithm(self, algorithm: InventoryAlgorithm, feedstock: Material):
        """
        Remove all entries from the configuration that are associated with the given algorithm.
        """
        for config_entry in ScenarioInventoryConfiguration.objects.filter(scenario=self,
                                                                          inventory_algorithm=algorithm,
                                                                          feedstock=feedstock):
            config_entry.delete()

    def delete(self, **kwargs):
        self.delete_configuration()  # TODO: Does this happen automatically through cascading?
        super().delete()

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
            parameter = entry.inventory_parameter.short_name
            value = entry.inventory_value.value
            standard_deviation = entry.inventory_value.standard_deviation

            if feedstock not in inventory_config.keys():
                inventory_config[feedstock] = {}
            if function not in inventory_config[feedstock].keys():
                inventory_config[feedstock][function] = {}
                inventory_config[feedstock][function]['catchment_id'] = self.catchment.id
                inventory_config[feedstock][function]['scenario_id'] = self.id
                inventory_config[feedstock][function]['feedstock_id'] = feedstock
            if parameter not in inventory_config[feedstock][function]:
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

    def get_absolute_url(self):
        return reverse('scenario_detail', kwargs={'pk': self.pk})

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
    feedstock = models.ForeignKey(Material, limit_choices_to={'is_feedstock': True}, on_delete=models.CASCADE)
    geodataset = models.ForeignKey(GeoDataset, on_delete=models.CASCADE)
    inventory_algorithm = models.ForeignKey(InventoryAlgorithm, on_delete=models.CASCADE)
    inventory_parameter = models.ForeignKey(InventoryAlgorithmParameter, on_delete=models.CASCADE)
    inventory_value = models.ForeignKey(InventoryAlgorithmParameterValue, on_delete=models.CASCADE)

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
        return reverse('scenario_detail', kwargs={'pk': self.scenario.pk})
