from collections import UserDict

from brit.exceptions import UnitMismatchError


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


BACKGROUND_COLORS = [
    'rgba(4, 85, 94, 0.4)',
    'rgba(148, 51, 41, 0.4)',
    'rgba(99, 163, 60, 0.4)',
    'rgba(244, 154, 51, 0.4)',
    'rgba(130, 105, 55, 0.4)',
    'rgba(252, 199, 103, 0.4)',
    'rgba(255, 99, 132, 0.4)',
    'rgba(54, 162, 235, 0.4)',
    'rgba(255, 206, 86, 0.4)',
    'rgba(75, 192, 192, 0.4)',
    'rgba(153, 102, 255, 0.4)',
    'rgba(255, 159, 64, 0.4)',
]

BORDER_COLORS = [
    'rgba(4, 85, 94, 1)',
    'rgba(148, 51, 41, 1)',
    'rgba(99, 163, 60, 1)',
    'rgba(244, 154, 51, 1)',
    'rgba(130, 105, 55, 1)',
    'rgba(252, 199, 103, 1)',
    'rgba(255, 99, 132, 1)',
    'rgba(54, 162, 235, 1)',
    'rgba(255, 206, 86, 1)',
    'rgba(75, 192, 192, 1)',
    'rgba(153, 102, 255, 1)',
    'rgba(255, 159, 64, 1)'
]


class BaseDataSet(UserDict):
    background_colors = BACKGROUND_COLORS
    label = None
    unit = None

    def __init__(self, data=None, label=None, unit=None):
        super().__init__(data)
        self.label = label if label is not None else None
        self.unit = unit if unit is not None else None

    @property
    def xlabels(self):
        return list(self.keys())

    def __str__(self):
        return self.label


class DataSet(BaseDataSet):

    def __init__(self, **attrs):
        super().__init__(**attrs)


class BaseChart:
    """
    Adapter between django database and and chart.js
    """
    type = None
    _labels = None
    has_data = False
    data = None
    unit = None
    title = None
    id = None
    show_legend = None

    def __init__(self, **kwargs):
        self.id = kwargs.get('id', '')
        self.title = kwargs.get('title', '')
        self.type = kwargs.get('type')
        self.unit = kwargs.get('unit', '')
        self.show_legend = kwargs.get('show_legend', False)
        self.labels = kwargs.get('labels', [])
        self.data = []
        for d in kwargs.get('data', []):
            ds = BaseDataSet(dict(zip(kwargs.get('labels'), d['data'])))
            ds.label = d['label']
            ds.unit = d['unit']
            self.data.append(ds)

    @property
    def has_labels(self):
        return bool(self._labels) is not False

    @property
    def labels(self):
        return self._labels

    @labels.setter
    def labels(self, labels):
        if labels is not None and type(labels) not in (list, tuple):
            raise TypeError
        self._labels = labels

    def add_dataset(self, dataset=None, **kwargs):
        if dataset is not None:
            if dataset.unit != self.unit:
                raise UnitMismatchError
            if not self.data:
                for label in dataset.xlabels:
                    self.labels.append(label)
            self.data.append(dataset)

        else:
            if kwargs.get('unit') != self.unit:
                raise UnitMismatchError
            dataset = BaseDataSet(**kwargs)
            self.data.append(dataset)
            for label in dataset.xlabels:
                self.labels.append(label)
        self.has_data = True

    def as_old_dict(self):

        return {
            'id': self.id,
            'type': self.type,
            'title': self.title,
            'labels': self.labels,
            'data': [{'data': list(d.data.values()), 'label': d.label, 'unit': d.unit} for d in self.data],
            'unit': self.unit,
            'show_legend': self.show_legend
        }

    def as_dict(self):

        chart_dict = {
            'type': self.type,
            'data': {
                'labels': self.labels,
                'datasets': [],
            },
            'options': {
                'legend': {
                    'display': True,
                    'position': 'bottom',
                },
                'aspectRatio': 0.8
            },
        }
        for ds in self.data:
            chart_dict['data']['datasets'].append({
                'label': ds.label,
                'data': list(ds.values()),
                'backgroundColor': BACKGROUND_COLORS,
                'borderColor': BORDER_COLORS,
                'borderWidth': 1,
                'hoverOffset': 4
            })
        return chart_dict


class BarChart(BaseChart):

    def __init__(self, **kwargs):
        kwargs.update({'type': 'barchart'})
        super().__init__(**kwargs)


class DoughnutChart(BaseChart):

    def __init__(self, **kwargs):
        kwargs.update({'type': 'doughnut'})
        super().__init__(**kwargs)
