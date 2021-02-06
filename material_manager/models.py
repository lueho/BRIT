import django_tables2 as tables
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.urls import reverse
from django.utils.html import format_html

from flexibi_dst.models import LiteratureSource, Timestep, TemporalDistribution


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

    def settings(self, owner):
        return self.materialsettings_set.filter(owner=owner)

    def add_settings(self, owner, standard=False, **kwargs):
        MaterialSettings.objects.create(
            material=self,
            owner=owner,
            standard=standard,
            name=kwargs.get('name'),
            description=kwargs.get('description'),
        )

    def get_absolute_url(self):
        return reverse('material_detail', kwargs={'pk': self.id})

    def __str__(self):
        return self.name


@receiver(post_save, sender=Material)
def initialize_material_settings(sender, instance, created, **kwargs):
    if created:
        instance.add_settings(owner=instance.owner, material=instance, standard=True)


class MaterialSettings(models.Model):
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, default='Customization')
    description = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    standard = models.BooleanField(default=True)

    def add_component_group(self, group, **kwargs):
        if 'component_group_settings' not in kwargs:
            kwargs['component_group_settings'] = MaterialComponentGroupSettings.objects.create(
                owner=self.owner,
                group=group,
                material_settings=self,
                fractions_of=kwargs.setdefault('fractions_of', 1)
            )

        return kwargs['component_group_settings']

    @property
    def component_ids(self):
        """
        Ids of components of groups that are assigned to this material.
        """
        return [pk for setting in self.materialcomponentgroupsettings_set.all() for pk in setting.component_ids]

    @property
    def group_ids(self):
        """
        Ids of component groups that have been assigned to this material.
        """
        return [setting['group'] for setting in self.materialcomponentgroupsettings_set.values('group').distinct()]

    @property
    def blocked_ids(self):
        """
        Returns a list of group ids that cannot be added to the material because they are already assigned.
        """
        ids = self.group_ids
        return ids

    def composition(self):
        group_settings = self.materialcomponentgroupsettings_set.all()
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

    def get_absolute_url(self):
        return reverse('material_settings', kwargs={'pk': self.id})

    def __str__(self):
        if self.standard:
            return f'Standard settings for material {self.material.name}'
        else:
            return f'Customization of material {self.material.name} by user {self.owner.username}'


class MaterialComponent(models.Model):
    """
    Represents any kind of component that a material can consists of (e.g. water, any kind of chemical element
    or more complex components, such as carbohydrates)
    """
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    def get_absolute_url(self):
        return reverse('material_component_detail', kwargs={'pk': self.id})

    def __str__(self):
        return self.name


class MaterialComponentGroup(models.Model):
    """
    Container model to group MaterialComponent instances
    """
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)

    def get_absolute_url(self):
        return reverse('material_component_group_detail', kwargs={'pk': self.id})

    def __str__(self):
        return self.name


class MaterialComponentGroupSettings(models.Model):
    """
    Utility model to store the settings for component groups for each material in each customization. This model is not
    supposed to be edited directly by a user. It depends on user objects and must be deleted, when any of the user
    objects it depends on is deleted.
    """

    owner = models.ForeignKey(User, default=8, on_delete=models.CASCADE)
    group = models.ForeignKey(MaterialComponentGroup, null=True, on_delete=models.CASCADE)
    material_settings = models.ForeignKey(MaterialSettings, null=True, on_delete=models.CASCADE)
    temporal_distributions = models.ManyToManyField(TemporalDistribution)
    fractions_of = models.ForeignKey(MaterialComponent, on_delete=models.CASCADE, default=1)

    @property
    def material(self):
        return self.material_settings.material

    def components(self):
        """
        Queryset of all components that have been assigned to this group.
        """
        component_ids = [share['component'] for share in
                         self.materialcomponentshare_set.values('component').distinct()]
        return MaterialComponent.objects.filter(id__in=component_ids)

    @property
    def component_ids(self):
        """
        Ids of all material components that have been assigned to this group.
        """
        return [share['component'] for share in self.materialcomponentshare_set.values('component').distinct()]

    @property
    def blocked_ids(self):
        """
        Returns a list of ids that cannot be added to the group because they are either already assigned to the group
        or would create a circular reference.
        """
        ids = self.component_ids
        ids.append(self.fractions_of.id)
        return ids

    def add_component(self, component, **kwargs):
        """
        Takes care of all setup that is necessary to integrate a new material component into a component group.
        Can be called either by providing an already created MaterialComponentShare with the keyword argument 'share'
        or by passing keyword arguments for the creation of a new share.
        :param component:
        :param kwargs: average, standard_deviation, source
        :return:
        """
        if 'share' not in kwargs:
            kwargs['share'] = MaterialComponentShare.objects.create(
                component=component,
                group_settings=self,
                average=kwargs.setdefault('average', 0.0),
                standard_deviation=kwargs.setdefault('standard_deviation', 0.0),
                timestep=Timestep.objects.get(name='Average'),
                source=kwargs.setdefault('source', None)
            )

        self.add_component_to_distributions(kwargs['share'])
        return kwargs['share']

    def remove_component(self, component):
        self.materialcomponentshare_set.filter(component=component).delete()

    def add_component_to_distributions(self, share):
        for distribution in self.temporal_distributions.all():
            timesteps = distribution.timestep_set.all()
            for timestep in timesteps:
                MaterialComponentShare.objects.create(component=share.component,
                                                      group_settings=self,
                                                      timestep=timestep,
                                                      average=share.average,
                                                      standard_deviation=share.standard_deviation)

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
                reverse('material_component_group_remove_component', kwargs={
                    'pk': self.id,
                    'component_pk': component.id
                })
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
            reverse('material_component_group_add_component', kwargs={'pk': self.id})
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
            group_settings = None

            def __init__(self, *args, **kwargs):
                self.group_settings = kwargs.pop('group_settings')
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
                                'pk': self.group_settings.id,
                                'timestep_pk': Timestep.objects.get(name=bound_column.accessor).id
                            }),
                )

        if len(table_data) > 0:
            columns = {name: EditableColumn(group_settings=self) for name
                       in list(table_data[0].keys())}
            columns['id'] = f'distribution-table-group-{self.id}'
        else:
            columns = {}
        table_class = type(f'DistributionTable-{self.id}-{distribution.id}', (tables.Table,), columns)
        return table_class(table_data)

    def distribution_table_classes(self):
        return [self.distribution_table_class(distribution) for distribution in
                self.temporal_distributions.exclude(name='Average')]

    def get_absolute_url(self):
        return reverse('material_settings', kwargs={
            'pk': self.material_settings.id,
        })

    def __str__(self):
        if self.material_settings.standard:
            return f'Group {self.group.name} of standard material {self.material.name}'
        else:
            return f'Group {self.group.name} of customization of material {self.material.name} by user {self.material.owner.username}'


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
    component = models.ForeignKey(MaterialComponent, on_delete=models.CASCADE)
    group_settings = models.ForeignKey(MaterialComponentGroupSettings, on_delete=models.CASCADE)
    average = models.FloatField(default=0.0)
    standard_deviation = models.FloatField(default=0.0)
    timestep = models.ForeignKey(Timestep, on_delete=models.CASCADE)
    source = models.ForeignKey(LiteratureSource, on_delete=models.CASCADE, blank=True, null=True)

    @property
    def material(self):
        return self.material_settings.material

    @property
    def material_settings(self):
        return self.group_settings.material_settings

    @property
    def group(self):
        return self.group_settings.group

    def get_absolute_url(self):
        return reverse('material_settings', kwargs={'pk': self.material_settings.id})

    def __str__(self):
        return f'Component share of material: {self.material.name}, component: {self.component.name}'


@receiver(post_save, sender=MaterialComponentShare)
def catch_new_component(sender, instance, created, **kwargs):
    """
    Receives a signal, when a new share is created and calls all function that are required for a complete component
    group setup.
    """
    if created:
        if instance.timestep.name == 'Average':
            instance.group_settings.add_component(instance.component, share=instance)
        return
    return
