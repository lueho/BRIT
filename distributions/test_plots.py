from unittest import TestCase as NativeTestCase

from distributions.plots import BaseChart, BarChart, BaseDataSet
from flexibi_dst.exceptions import UnitMismatchError


class BaseDataSetTestCase(NativeTestCase):

    def setUp(self):
        self.ds = BaseDataSet()
        self.labels = ['First dataset', 'Second dataset']
        self.dataset_kwargs = {
            'label': 'Test dataset',
            'data': {'Column 1': 1.0, 'Column 2': 2.0, 'Column 3': 3.0},
            'unit': 'kg/a'
        }

    def test_create_dataset(self):
        self.assertIsInstance(self.ds, BaseDataSet)

    def test_set_and_get_label(self):
        self.assertIsNone(self.ds.label)
        for label in self.labels:
            self.ds.label = label
            self.assertEqual(self.ds.label, label)

    def test_get_xlabels(self):
        ds = BaseDataSet(**self.dataset_kwargs)
        xlabels = ['Column 1', 'Column 2', 'Column 3']
        self.assertListEqual(ds.xlabels, xlabels)

    def test_set_and_get_unit(self):
        self.assertIsNone(self.ds.unit)
        self.ds.unit = 'kg/a'
        self.assertEqual(self.ds.unit, 'kg/a')

    def test_dataset_str(self):
        self.ds.label = 'First dataset'
        self.assertEqual(str(self.ds), 'First dataset')

    def test_set_and_get_data(self):
        data = {'column 1': -1, 'column 2': 1}
        self.ds.data = data
        self.assertDictEqual(self.ds.data, data)

    def test_dataset_length(self):
        self.ds.data = {f'Column {i}': 1 for i in range(5)}
        self.assertEqual(len(self.ds), 5)

    def test_set_and_get_background_color(self):
        self.ds.bg_color = "#04555e"
        self.assertEqual(self.ds.bg_color, "#04555e")

    def test_create_dataset_with_kwargs(self):
        dataset = BaseDataSet(**self.dataset_kwargs)
        self.assertEqual(dataset.label, self.dataset_kwargs['label'])
        self.assertDictEqual(dataset.data, self.dataset_kwargs['data'])


class BasePlotTestCase(NativeTestCase):

    def setUp(self):
        self.chart = BaseChart()
        self.labels = ['First column', 'Second column', 'Third column']
        self.unit = 'Mg/a'
        self.dataset1_kwargs = {
            'label': 'Dataset 1',
            'data': {'Column 1': 1.0, 'Column 2': 2.0, 'Column 3': 3.0},
            'unit': self.unit
        }
        self.dataset1 = BaseDataSet(**self.dataset1_kwargs)
        self.dataset2_kwargs = {
            'label': 'Dataset 2',
            'data': {'Column 1': 1.5, 'Column 2': 2.5, 'Column 3': 3.5},
            'unit': self.unit
        }
        self.chart_dict = {
            'id': 'testChart',
            'title': 'Test chart',
            'labels': ['First column', 'Second column', 'Third column'],
            'unit': self.unit,
            'type': 'stacked-barchart',
            'show_legend': False,
            'data': [
                {'label': 'Dataset 1', 'data': [1.0, 2.0, 3.0], 'unit': self.unit},
                {'label': 'Dataset 2', 'data': [1.5, 2.5, 3.5], 'unit': self.unit}
            ]
        }

    def test_create_plot(self):
        self.assertIsInstance(self.chart, BaseChart)

    def test_set_and_get_plot_type(self):
        self.assertIsNone(self.chart.type)
        chart_types = ['stacked-barchart', 'piechart']
        for chart_type in chart_types:
            self.chart.type = chart_type
            self.assertEqual(self.chart.type, chart_type)

    def test_has_no_labels_at_instantiation(self):
        self.assertFalse(BaseChart().has_labels)

    def test_set_labels(self):
        self.chart.labels = self.labels
        self.assertTrue(self.chart.has_labels)
        self.assertEqual(self.chart.labels, self.labels)

    def test_set_labels_raises_type_error(self):
        with self.assertRaises(TypeError):
            self.chart.labels = 7

    def test_has_no_labels_after_label_deletion(self):
        self.chart.labels = self.labels
        self.chart.labels = None
        self.assertFalse(self.chart.has_labels)

    def test_set_and_get_unit(self):
        self.chart.unit = self.unit
        self.assertEqual(self.chart.unit, self.unit)

    def test_create_with_kwargs(self):
        chart = BaseChart(**self.chart_dict)
        self.maxDiff = None
        self.assertDictEqual(chart.as_dict(), self.chart_dict)

    def test_has_no_data_at_instantiation(self):
        self.assertFalse(self.chart.has_data)

    def test_add_and_get_dataset_with_object(self):
        self.chart.unit = self.unit
        self.chart.add_dataset(self.dataset1)
        self.assertTrue(self.chart.has_data)
        self.assertIsInstance(self.chart.data[0], BaseDataSet)
        self.assertEqual(self.chart.data[0], self.dataset1)

    def test_add_and_get_dataset_with_kwargs(self):
        self.chart.unit = self.unit
        self.chart.add_dataset(**self.dataset1_kwargs)
        self.assertTrue(self.chart.has_data)
        self.assertIsInstance(self.chart.data[0], BaseDataSet)
        self.assertEqual(vars(self.chart.data[0]), vars(BaseDataSet(**self.dataset1_kwargs)))

    def test_add_and_get_two_datasets(self):
        self.chart.unit = self.unit
        self.chart.add_dataset(self.dataset1)
        self.chart.add_dataset(**self.dataset2_kwargs)
        self.assertEqual(len(self.chart.data), 2)
        self.assertEqual(self.chart.data[0], self.dataset1)
        self.assertEqual(vars(self.chart.data[1]), vars(BaseDataSet(**self.dataset2_kwargs)))

    def test_add_dataset_raises_unit_mismatch_error(self):
        ds_kwargs = self.dataset2_kwargs.copy()
        ds_kwargs['unit'] = 'Imposter'
        with self.assertRaises(UnitMismatchError):
            self.chart.add_dataset(**ds_kwargs)

    def test_add_dataset_stores_labels(self):
        self.chart.unit = self.unit
        self.chart.add_dataset(**self.dataset2_kwargs)
        self.assertListEqual(self.chart.labels, ['Column 1', 'Column 2', 'Column 3'])

    def test_as_dict(self):
        self.chart.unit = self.unit
        self.chart.add_dataset(self.dataset1)
        self.chart.add_dataset(**self.dataset2_kwargs)
        self.chart.labels = self.labels
        self.chart.title = 'Test chart'
        self.chart.type = 'stacked-barchart'
        self.chart.show_legend = False
        self.chart.id = 'testChart'
        self.maxDiff = None
        self.assertDictEqual(self.chart.as_dict(), self.chart_dict)


class BarchartTestCase(NativeTestCase):

    def test_create_barchart(self):
        barchart = BarChart()
        self.assertEqual(barchart.type, 'barchart')
