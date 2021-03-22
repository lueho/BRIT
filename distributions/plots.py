from collections import UserDict

from flexibi_dst.exceptions import UnitMismatchError


class BaseDataSet(UserDict):
    bg_color = None
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
        self.labels = kwargs.get('labels')
        self.data = []
        for d in kwargs.get('data', []):
            ds = BaseDataSet(dict(zip(kwargs.get('labels'), d['data'])))
            ds.label = d['label']
            ds.unit = d['unit']
            self.data.append(ds)

    @property
    def has_labels(self):
        return self._labels is not None

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
            self.data.append(dataset)
        else:
            if kwargs.get('unit') != self.unit:
                raise UnitMismatchError
            self.data.append(BaseDataSet(**kwargs))
        self.has_data = True

    def as_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'title': self.title,
            'labels': self.labels,
            'data': [{'data': list(d.data.values()), 'label': d.label, 'unit': d.unit} for d in self.data],
            'unit': self.unit,
            'show_legend': self.show_legend
        }


class BarChart(BaseChart):

    def __init__(self, **kwargs):
        kwargs.update({'type': 'barchart'})
        super().__init__(**kwargs)
