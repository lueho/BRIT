from flexibi_dst.exceptions import UnitMismatchError


class BaseDataSet:
    bg_color = None
    label = None
    unit = None
    _data = None

    def __init__(self, **attrs):
        for key, value in attrs.items():
            setattr(self, key, value)

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, data):
        if data is not None and type(data) is not list:
            raise TypeError
        self._data = data

    def as_dict(self):
        return {
            'label': self.label,
            'data': self.data,
            'unit': self.unit
        }

    def __len__(self):
        return len(self.data)

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
        self.data = [BaseDataSet(**d) for d in kwargs.get('data', [])]

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
            'data': [d.as_dict() for d in self.data],
            'unit': self.unit,
            'show_legend': self.show_legend
        }


class BarChart(BaseChart):

    def __init__(self, **kwargs):
        kwargs.update({'type': 'barchart'})
        super().__init__(**kwargs)
