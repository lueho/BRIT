from django.db.models import Q
from django.test import TestCase

from distributions.models import TemporalDistribution, Timestep
from utils.models import Property
from ..filters import (CollectionFilterSet, CollectionsPerYearFilter, ConnectionRateFilter,
                       CollectorFilter, WasteFlyerFilter, SpecWasteCollectedFilter)
from ..models import (Collection, CollectionCatchment, CollectionCountOptions, CollectionFrequency,
                      CollectionPropertyValue, CollectionSeason, Collector, WasteFlyer)


class WasteFlyerFilterTestCase(TestCase):
    catchment = None

    @classmethod
    def setUpTestData(cls):
        for i in range(1, 5):
            WasteFlyer.objects.create(
                title=f'Waste flyer {i}',
                abbreviation=f'WF{i}',
                url=f'https://www.flyer{i}.com',
                url_valid=i % 2 == 0
            )
        cls.catchment = CollectionCatchment.objects.create(name='Parent')
        child_catchment = CollectionCatchment.objects.create(name='Child', parent=cls.catchment)
        for flyer in WasteFlyer.objects.filter(abbreviation__in=('WF1', 'WF2')):
            collection = Collection.objects.create(catchment=child_catchment, )
            collection.flyers.add(flyer)
        collection = Collection.objects.create(catchment=cls.catchment)
        collection.flyers.add(WasteFlyer.objects.get(abbreviation='WF3'))

    def setUp(self):
        pass

    def test_filter_form_has_no_formtags(self):
        filter_ = WasteFlyerFilter(queryset=WasteFlyer.objects.all())
        self.assertFalse(filter_.form.helper.form_tag)

    def test_url_valid(self):
        data = {'url_valid': 'False'}
        filter_ = WasteFlyerFilter(data, WasteFlyer.objects.all())
        self.assertTrue(filter_.is_valid())
        self.assertEqual(4, WasteFlyer.objects.count())
        self.assertEqual(2, filter_.qs.count())

    def test_get_catchment_returns_flyers_from_downstream_collections(self):
        data = {'catchment': self.catchment.id}
        filter_ = WasteFlyerFilter(data=data, queryset=WasteFlyer.objects.all())
        self.assertTrue(filter_.is_valid())
        self.assertQuerysetEqual(filter_.qs.order_by('id'),
                                 WasteFlyer.objects.filter(abbreviation__in=('WF1', 'WF2', 'WF3')).order_by('id'))


class CollectionsPerYearFilterTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        distribution = TemporalDistribution.objects.get(name='Months of the year')
        whole_year = CollectionSeason.objects.get(
            distribution=distribution,
            first_timestep=Timestep.objects.get(name='January'),
            last_timestep=Timestep.objects.get(name='December')
        )
        first_half_year = CollectionSeason.objects.create(
            distribution=distribution,
            first_timestep=Timestep.objects.get(name='January'),
            last_timestep=Timestep.objects.get(name='June')
        )
        second_half_year = CollectionSeason.objects.create(
            distribution=distribution,
            first_timestep=Timestep.objects.get(name='July'),
            last_timestep=Timestep.objects.get(name='December')
        )

        continuous_frequency = CollectionFrequency.objects.create(name='Continuous Frequency')
        seasonal_frequency = CollectionFrequency.objects.create(name='Seasonal Frequency')

        CollectionCountOptions.objects.create(frequency=continuous_frequency, season=whole_year, standard=35,
                                              option_1=70)
        CollectionCountOptions.objects.create(frequency=seasonal_frequency, season=first_half_year, standard=35)
        CollectionCountOptions.objects.create(frequency=seasonal_frequency, season=second_half_year, standard=35)

        cls.collection1 = Collection.objects.create(name='Collection 1', frequency=continuous_frequency)
        cls.collection2 = Collection.objects.create(name='Collection 2', frequency=continuous_frequency)
        cls.collection3 = Collection.objects.create(name='Collection 3', frequency=seasonal_frequency)
        cls.collection4 = Collection.objects.create(name='Collection 4')

    def test_filter_by_collections_per_year(self):
        filter_ = CollectionsPerYearFilter()
        qs = filter_.filter(Collection.objects.all(), (slice(26, 52), False))
        expected = Collection.objects.filter(pk__in=[self.collection1.pk, self.collection2.pk])
        self.assertQuerysetEqual(qs, expected, ordered=False)

    def test_filter_with_without_value_returns_full_queryset(self):
        filter_ = CollectionsPerYearFilter()
        qs = filter_.filter(Collection.objects.all(), None)
        self.assertQuerysetEqual(qs, Collection.objects.all(), ordered=False)

    def test_filter_by_collections_per_year_with_no_value(self):
        filter_ = CollectionsPerYearFilter()
        qs = filter_.filter(Collection.objects.all(), (slice(52, 100), True))
        expected = Collection.objects.filter(pk__in=[self.collection3.pk, self.collection4.pk])
        self.assertQuerysetEqual(qs, expected, ordered=False)


class ConnectionRateFilterTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.collection1 = Collection.objects.create(name='Collection 1')
        cls.collection2 = Collection.objects.create(name='Collection 2')
        cls.collection3 = Collection.objects.create(name='Collection 3')
        cls.collection4 = Collection.objects.create(name='Collection 4')

        # Add connection rate properties to collections
        prop = Property.objects.create(name='Connection rate')
        CollectionPropertyValue.objects.create(
            collection=cls.collection1,
            property=prop,
            year=2022,
            average=50
        )
        CollectionPropertyValue.objects.create(
            collection=cls.collection2,
            property=prop,
            year=2022,
            average=75
        )
        CollectionPropertyValue.objects.create(
            collection=cls.collection3,
            property=prop,
            year=2022,
            average=25
        )

    def test_filter_by_connection_rate(self):
        filter_ = ConnectionRateFilter()
        qs = filter_.filter(Collection.objects.all(), (slice(50, 75), False))
        expected = Collection.objects.filter(pk__in=[self.collection1.pk, self.collection2.pk])
        self.assertQuerysetEqual(qs, expected, ordered=False)

    def test_filter_with_without_value(self):
        filter_ = ConnectionRateFilter()
        qs = filter_.filter(Collection.objects.all(), None)
        expected = Collection.objects.all()
        self.assertQuerysetEqual(qs, expected, ordered=False)

    def test_filter_including_null_values(self):
        filter_ = ConnectionRateFilter()
        qs = filter_.filter(Collection.objects.all(), (slice(50, 75), True))
        expected = Collection.objects.filter(pk__in=[self.collection1.pk, self.collection2.pk, self.collection4.pk])
        self.assertQuerysetEqual(qs, expected, ordered=False)


class SpecWasteCollectedFilterTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.collection1 = Collection.objects.create(name='Collection 1')
        cls.collection2 = Collection.objects.create(name='Collection 2')
        cls.collection3 = Collection.objects.create(name='Collection 3')
        cls.collection4 = Collection.objects.create(name='Collection 4')

        # Add spec waste collected properties to collections
        prop = Property.objects.create(name='specific waste collected')
        CollectionPropertyValue.objects.create(
            collection=cls.collection1,
            property=prop,
            year=2022,
            average=100
        )
        CollectionPropertyValue.objects.create(
            collection=cls.collection2,
            property=prop,
            year=2021,
            average=200
        )
        CollectionPropertyValue.objects.create(
            collection=cls.collection3,
            property=prop,
            year=2019,
            average=300
        )

    def test_filter_by_spec_waste_collected(self):
        filter_ = SpecWasteCollectedFilter()
        qs = filter_.filter(Collection.objects.all(), (slice(100, 200), False))
        expected = Collection.objects.filter(pk__in=[self.collection1.pk, self.collection2.pk])
        self.assertQuerysetEqual(qs, expected, ordered=False)

    def test_filter_with_without_value(self):
        filter_ = SpecWasteCollectedFilter()
        qs = filter_.filter(Collection.objects.all(), None)
        expected = Collection.objects.all()
        self.assertQuerysetEqual(qs, expected, ordered=False)

    def test_filter_including_null_values(self):
        filter_ = SpecWasteCollectedFilter()
        qs = filter_.filter(Collection.objects.all(), (slice(100, 200), True))
        expected = Collection.objects.filter(pk__in=[self.collection1.pk, self.collection2.pk, self.collection4.pk])
        self.assertQuerysetEqual(qs, expected, ordered=False)


class CollectionFilterTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        distribution = TemporalDistribution.objects.get(name='Months of the year')
        cls.january = Timestep.objects.get(name='January')
        cls.june = Timestep.objects.get(name='June')
        cls.july = Timestep.objects.get(name='July')
        cls.december = Timestep.objects.get(name='December')
        whole_year = CollectionSeason.objects.get(
            distribution=distribution,
            first_timestep=cls.january,
            last_timestep=cls.december
        )
        first_half_year = CollectionSeason.objects.create(
            distribution=distribution,
            first_timestep=cls.january,
            last_timestep=cls.june
        )
        second_half_year = CollectionSeason.objects.create(
            distribution=distribution,
            first_timestep=cls.july,
            last_timestep=cls.december
        )
        cls.not_seasonal_frequency = CollectionFrequency.objects.create(name='Non-Seasonal Test Frequency')
        CollectionCountOptions.objects.create(frequency=cls.not_seasonal_frequency, season=whole_year, standard=35,
                                              option_1=70)
        cls.seasonal_frequency = CollectionFrequency.objects.create(name='Seasonal Test Frequency')
        CollectionCountOptions.objects.create(frequency=cls.seasonal_frequency, season=first_half_year, standard=35)
        CollectionCountOptions.objects.create(frequency=cls.seasonal_frequency, season=second_half_year, standard=35)
        cls.catchment = CollectionCatchment.objects.create(name='Test Catchment', type='administrative')
        child_catchment = CollectionCatchment.objects.create(name='Child Catchment', parent=cls.catchment,
                                                             type='administrative')
        cls.grandchild_catchment = CollectionCatchment.objects.create(parent=child_catchment, type='administrative')
        cls.unrelated_catchment = CollectionCatchment.objects.create(name='Unrelated Test Catchment',
                                                                     type='administrative')
        fixed_once_per_week = CollectionFrequency.objects.create(type='Fixed')
        CollectionCountOptions.objects.create(frequency=fixed_once_per_week, season=whole_year, standard=52)

        # Create collections
        cls.collection1 = Collection.objects.create(catchment=cls.catchment, frequency=cls.not_seasonal_frequency)
        cls.collection2 = Collection.objects.create(catchment=cls.unrelated_catchment, frequency=cls.seasonal_frequency)
        cls.child_collection = Collection.objects.create(catchment=child_catchment, frequency=fixed_once_per_week)

        # Add connection_rate properties
        prop_connection_rate = Property.objects.create(name='Connection rate')
        CollectionPropertyValue.objects.create(
            property=prop_connection_rate, collection=cls.collection1, year=2022, average=70)
        CollectionPropertyValue.objects.create(
            property=prop_connection_rate, collection=cls.collection2, year=2021, average=30)

        # Add specific waste collected properties
        prop_spec_waste_collected = Property.objects.create(name='specific waste collected', unit='kg/(cap.*a)')
        CollectionPropertyValue.objects.create(
            property=prop_spec_waste_collected, collection=cls.collection1, year=2022, average=100)
        CollectionPropertyValue.objects.create(
            property=prop_spec_waste_collected, collection=cls.collection1, year=2021, average=150)
        CollectionPropertyValue.objects.create(
            property=prop_spec_waste_collected, collection=cls.collection2, year=2022, average=200)

    def setUp(self):
        self.data = {field_name: field.initial for field_name, field in CollectionFilterSet().form.fields.items() if
                     field.initial}

    def test_only_initial_values_returns_complete_queryset(self):
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        self.assertQuerysetEqual(Collection.objects.order_by('id'), qs.order_by('id'))

    def test_catchment_filter(self):
        self.data.update({'catchment': self.catchment.pk})
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        self.assertEqual(2, qs.count())

    def test_filter_includes_child_catchments(self):
        self.data.update({'catchment': self.catchment.pk})
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        self.assertIn(self.child_collection, qs)

    def test_filter_includes_collections_from_upstream_catchments_if_there_are_none_downstream(self):
        self.data.update({'catchment': self.grandchild_catchment.pk})
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        self.assertIn(self.child_collection, qs)
        self.assertIn(self.collection1, qs)

    def test_connection_rate_range_filter_fields_exists_in_filter_and_form(self):
        self.data.update({'connection_rate_min': 50, 'connection_rate_max': 99})
        filtr = CollectionFilterSet(self.data, queryset=Collection.objects.all())
        self.assertIn('connection_rate', filtr.filters.keys())
        self.assertIn('connection_rate', filtr.form.fields.keys())

    def test_connection_rate_range_filter_renders_with_converted_percentage_values(self):
        self.data.update({'connection_rate_min': 50, 'connection_rate_max': 99})
        filtr = CollectionFilterSet(self.data, queryset=Collection.objects.all())
        self.assertInHTML(
            '<span class="numeric-slider-range-text" id="id_connection_rate_text">50% - 99%</span>',
            filtr.form.as_p())

    def test_connection_rate_returns_only_collections_in_given_range(self):
        self.data.update({'connection_rate_min': 50, 'connection_rate_max': 100, 'connection_rate_is_null': False})
        filtr = CollectionFilterSet(self.data, queryset=Collection.objects.all())
        qs = filtr.qs
        expected_qs = Collection.objects.filter(pk__in=[self.collection1.pk])
        self.assertQuerysetEqual(expected_qs, qs, ordered=False)

    def test_seasonal_frequency_filter_field_exists_in_filter_and_form(self):
        self.data.update({'seasonal_frequency': True})
        filtr = CollectionFilterSet(self.data, queryset=Collection.objects.all())
        self.assertIn('seasonal_frequency', filtr.filters.keys())
        self.assertIn('seasonal_frequency', filtr.form.fields.keys())

    def test_seasonal_frequency_filter_returns_collections_with_non_seasonal_frequency_on_false(self):
        self.data.update({'seasonal_frequency': False})
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        self.assertIn(self.collection1, qs)
        self.assertNotIn(self.collection2, qs)

    def test_seasonal_frequency_filter_returns_collections_with_seasonal_frequency_on_true(self):
        self.data.update({'seasonal_frequency': True})
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        self.assertIn(self.collection2, qs)
        self.assertNotIn(self.collection1, qs)

    def test_seasonal_frequency_filter_returns_all_collections_when_unselected(self):
        self.data.update({'seasonal_frequency': None})
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        self.assertQuerysetEqual(Collection.objects.order_by('id'), qs.order_by('id'))

    def test_optional_frequency_filter_field_exists_in_filter_and_form(self):
        self.data.update({'optional_frequency': True})
        filtr = CollectionFilterSet(self.data, queryset=Collection.objects.all())
        self.assertIn('optional_frequency', filtr.filters.keys())
        self.assertIn('optional_frequency', filtr.form.fields.keys())

    def test_optional_frequency_filter_returns_collections_without_options_on_false(self):
        self.data.update({'optional_frequency': False})
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        opts = CollectionCountOptions.objects.filter(Q(option_1__isnull=True) & Q(option_2__isnull=True) &
                                                     Q(option_3__isnull=True) & Q(frequency=self.seasonal_frequency))
        self.assertEqual(2, opts.count())
        for opt in opts:
            self.assertIsNone(opt.option_1)
        fr = opts.first().frequency
        self.assertEqual(Collection.objects.filter(frequency=fr).first(), self.collection2)
        self.assertIn(self.collection2, qs)
        self.assertNotIn(self.collection1, qs)

    def test_optional_frequency_filter_returns_collections_with_seasonal_frequency_on_true(self):
        self.data.update({'optional_frequency': True})
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        self.assertIn(self.collection1, qs)
        self.assertNotIn(self.collection2, qs)

    def test_optional_frequency_filter_returns_all_collections_when_unselected(self):
        self.data.update({'optional_frequency': None})
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        self.assertQuerysetEqual(Collection.objects.order_by('id'), qs.order_by('id'))

    def test_collections_per_year_field_exists_in_filter_form(self):
        filtr = CollectionFilterSet(queryset=Collection.objects.all())
        self.assertIn('collections_per_year', filtr.filters.keys())
        self.assertIn('collections_per_year', filtr.form.fields.keys())

    def test_collections_per_year_returns_only_matching_results(self):
        self.data.update({
            'collections_per_year_min': 60,
            'collections_per_year_max': 100,
            'collections_per_year_is_null': False
        })
        qs = CollectionFilterSet(self.data, queryset=Collection.objects.all()).qs
        expected = Collection.objects.filter(pk__in=[self.collection2.pk])
        self.assertQuerysetEqual(qs, expected, ordered=False)

    def test_collections_per_year_range_filter_renders_with_calculated_boundaries(self):
        filtr = CollectionFilterSet(self.data, queryset=Collection.objects.all())
        self.assertInHTML(
            '<span class="numeric-slider-range-text" id="id_collections_per_year_text">0 - 70</span>',
            filtr.form.as_p())

    def test_specific_waste_collected_field_exists_in_filter_form(self):
        filtr = CollectionFilterSet(queryset=Collection.objects.all())
        self.assertIn('spec_waste_collected', filtr.filters.keys())
        self.assertIn('spec_waste_collected', filtr.form.fields.keys())

    def test_get_spec_waste_collected_with_average_returns_correctly(self):
        data = {'spec_waste_collected_filter_method': 'average',
                'spec_waste_collected_min': 150,
                'spec_waste_collected_max': 1000}
        filtr = CollectionFilterSet(data=data, queryset=Collection.objects.all())
        filtr.is_valid()
        self.assertTrue(filtr.is_valid())
        qs = filtr.qs
        self.assertIn(self.collection2, qs)
        self.assertNotIn(self.collection1, qs)

    def test_spec_waste_collected_include_unknown_includes_null_values_if_checked(self):
        data = self.data.update(
            {'spec_waste_collected_filter_method': 'average',
             'spec_waste_collected_min': 0,
             'spec_waste_collected_max': 1000})
        filtr = CollectionFilterSet(data, queryset=Collection.objects.all())
        self.assertQuerysetEqual(Collection.objects.all().order_by('id'), filtr.qs.order_by('id'))

    def test_filter_form_has_no_formtags(self):
        filtr = CollectionFilterSet(queryset=Collection.objects.all())
        self.assertFalse(filtr.form.helper.form_tag)


class CollectorFilterTestCase(TestCase):

    def test_filter_form_has_no_formtags(self):
        filtr = CollectorFilter(queryset=Collector.objects.all())
        self.assertFalse(filtr.form.helper.form_tag)
