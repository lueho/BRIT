from django.db.models import Sum

from flexibi_dst.models import TemporalDistribution
from scenario_builder.algorithms import InventoryAlgorithmsBase
from scenario_builder.models import Scenario
from .models import NantesGreenhouses, Greenhouse


class Distribution:
    name = ''
    temporal_distribution = None
    _components = None
    _shares = None

    def __init__(self, temporal_distribution, components=None, name=None):
        self.temporal_distribution = temporal_distribution
        self._components = components if components else []
        if name is not None:
            self.name = name
        self._shares = []

    class Share:
        _timestep = None
        _component = None
        _value = None

        def __init__(self, timestep, component):
            self._timestep = timestep
            self._component = component

        @property
        def timestep(self):
            return self._timestep

        @property
        def component(self):
            return self._component

        @property
        def value(self):
            return self._value

        @value.setter
        def value(self, value):
            self._value = value

    @property
    def shares(self):
        return self._shares

    @shares.setter
    def shares(self, qs):
        for share in qs:
            self.add_share(share.timestepset.timestep, share.component, share.average)

    def add_shares(self, qs):
        for share in qs:
            self.add_share(share.timestepset.timestep, share.component, share.average)

    def add_share(self, timestep, component, value):
        for s in self.shares:
            if s.timestep == timestep and s.component == component:
                s.value += value
                return
        share = self.Share(timestep, component)
        share.value = value
        self._shares.append(share)

    @property
    def timesteps(self):
        return self.temporal_distribution.timestep_set.all()

    @property
    def components(self):
        return self._components

    def serialize(self):
        dist = {
            'name': self.name,
            'distribution': self.temporal_distribution.id,
            'sets': []
        }
        sets = {}
        for share in self.shares:
            if share.timestep.id not in sets:
                sets[share.timestep.id] = {}
            sets[share.timestep.id][share.component.id] = share.value
        for timestep_id, set_content in sets.items():
            new_set = {'timestep': timestep_id, 'shares': []}
            for component_id, value in set_content.items():
                new_set['shares'].append({'component': component_id, 'average': value})
            dist['sets'].append(new_set)
        return dist


class InventoryAlgorithms(InventoryAlgorithmsBase):

    @classmethod
    def nantes_greenhouse_production(cls, **kwargs):
        """

        :param kwargs: catchment_id, scenario_id
        :return:
        """

        result = {
            'aggregated_values': [],
            'aggregated_distributions': [],
            'features': []
        }

        scenario = Scenario.objects.get(id=kwargs.get('scenario_id'))
        catchment = scenario.catchment
        clipped = NantesGreenhouses.objects.filter(geom__intersects=catchment.geom)

        # reference_distribution = CaseStudyBaseObjects.objects.get.reference_distribution
        feedstocks = scenario.feedstocks()
        # result['aggregated_values'].append({'name': 'feedstocks', 'value': [f.material.name for f in feedstocks], 'unit': ''})
        components = []
        for feedstock in feedstocks:
            macro_components = feedstock.materialcomponentgroupsettings_set.get(group__name='Macro Components')
            for component in macro_components.components():
                components.append(component)
        # result['aggregated_values'].append({'name': 'components', 'value': set([component.name for component in components]), 'unit': ''})

        # Which greenhouses are considered?
        filter_kwargs = {}  # TODO: add filter functionality here
        greenhouse_types = Greenhouse.objects.filter(**filter_kwargs)

        # filter the clipped layer
        clipped_filtered = NantesGreenhouses.objects.none()
        for greenhouse_type in greenhouse_types:
            clipped_filtered = clipped_filtered.union(NantesGreenhouses.objects.filter(**greenhouse_type.filter_kwargs))

        for feature in clipped_filtered:
            fields = {'geom': feature.geom}
            # fields = {f'total_{key}_production': feature.surface_ha * value for (key, value) in
            #           specific_annual_component_production.items()}
            result['features'].append(fields)

        distribution = Distribution(TemporalDistribution.objects.get(name='Months of the year'), name='Macro Components')

        total_surface = 0
        total_production = 0
        greenhouse_count = 0
        for greenhouse_type in greenhouse_types:
            greenhouse_group = clipped.filter(**greenhouse_type.filter_kwargs)
            if greenhouse_group.exists():
                total_group_surface = greenhouse_group.aggregate(Sum('surface_ha'))['surface_ha__sum']
                total_surface += total_group_surface
                greenhouse_count += greenhouse_group.count()
                for share in greenhouse_type.shares:
                    distribution.add_share(share.timestepset.timestep, share.component, total_group_surface * share.average)
                    total_production += total_group_surface * share.average
        result['aggregated_distributions'].append(distribution.serialize())

        result['aggregated_values'].append({
            'name': 'greenhouse_count',
            'value': greenhouse_count,
            'unit': ''})

        result['aggregated_values'].append({
            'name': 'total_surface',
            'value': total_surface,
            'unit': 'ha'})

        result['aggregated_values'].append({
            'name': 'Total production',
            'value': total_production,
            'unit': 'Mg/a'
        })

        return result
