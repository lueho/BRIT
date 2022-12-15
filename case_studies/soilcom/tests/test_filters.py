from django.db.models import Q
from django.http.request import QueryDict, MultiValueDict
from django.test import TestCase, modify_settings

from distributions.models import Timestep, TemporalDistribution
from users.models import get_default_owner
from ..filters import CollectionFilter, WasteFlyerFilter
from ..models import (Collection, CollectionCatchment, CollectionCountOptions, CollectionFrequency, CollectionSeason,
                      WasteFlyer)


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class WasteFlyerFilterTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        for i in range(1, 5):
            WasteFlyer.objects.create(
                owner=owner,
                title=f'Waste flyer {i}',
                abbreviation=f'WF{i}',
                url_valid=i % 2 == 0
            )

    def setUp(self):
        pass

    def test_init(self):
        params = {
            'csrfmiddlewaretoken': ['Hm7MXB2NjRCOIpNbGaRKR87VCHM5KwpR1t4AdZFgaqKfqui1EJwhKKmkxFKDfL3h'],
            'url_valid': ['False'],
            'page': ['2']
        }
        qdict = QueryDict('', mutable=True)
        qdict.update(MultiValueDict(params))
        newparams = qdict.copy()
        newparams.pop('csrfmiddlewaretoken')
        newparams.pop('page')
        qs = WasteFlyerFilter(newparams, queryset=WasteFlyer.objects.all()).qs
        self.assertEqual(4, WasteFlyer.objects.count())
        self.assertEqual(2, qs.count())


class CollectionFilterTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        distribution = TemporalDistribution.objects.get(name='Months of the year')
        cls.january = Timestep.objects.get(name='January')
        cls.june = Timestep.objects.get(name='June')
        cls.july = Timestep.objects.get(name='July')
        cls.december = Timestep.objects.get(name='December')
        whole_year = CollectionSeason.objects.create(
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
        CollectionCountOptions.objects.create(frequency=cls.seasonal_frequency, season=first_half_year, standard=17)
        CollectionCountOptions.objects.create(frequency=cls.seasonal_frequency, season=second_half_year, standard=18)
        cls.catchment = CollectionCatchment.objects.create(name='Test Catchment')
        child_catchment = CollectionCatchment.objects.create(name='Child Catchment', parent=cls.catchment)
        cls.grandchild_catchment = CollectionCatchment.objects.create(parent=child_catchment)
        cls.unrelated_catchment = CollectionCatchment.objects.create(name='Unrelated Test Catchment')
        cls.collection1 = Collection.objects.create(catchment=cls.catchment, frequency=cls.not_seasonal_frequency,
                                                    connection_rate=0.7)
        cls.collection2 = Collection.objects.create(catchment=cls.unrelated_catchment, frequency=cls.seasonal_frequency,
                                                    connection_rate=0.3)
        cls.child_collection = Collection.objects.create(catchment=child_catchment)

    def setUp(self):
        self.data = {field_name: field.initial for field_name, field in CollectionFilter().form.fields.items() if
                     field.initial}

    def test_only_initial_values_returns_complete_queryset(self):
        qs = CollectionFilter(self.data, queryset=Collection.objects.all()).qs
        self.assertQuerysetEqual(Collection.objects.order_by('id'), qs.order_by('id'))

    def test_catchment_filter(self):
        self.data.update({'catchment': self.catchment.pk})
        qs = CollectionFilter(self.data, queryset=Collection.objects.all()).qs
        self.assertEqual(2, qs.count())

    def test_filter_includes_child_catchments(self):
        self.data.update({'catchment': self.catchment.pk})
        qs = CollectionFilter(self.data, queryset=Collection.objects.all()).qs
        self.assertIn(self.child_collection, qs)

    def test_filter_includes_collections_from_upstream_catchments_if_there_are_none_downstream(self):
        self.data.update({'catchment': self.grandchild_catchment.pk})
        qs = CollectionFilter(self.data, queryset=Collection.objects.all()).qs
        self.assertIn(self.child_collection, qs)
        self.assertIn(self.collection1, qs)

    def test_connection_rate_range_filter_fields_exists_in_filter_and_form(self):
        self.data.update({'connection_rate_min': 50, 'connection_rate_max': 99})
        filtr = CollectionFilter(self.data, queryset=Collection.objects.all())
        self.assertIn('connection_rate', filtr.filters.keys())
        self.assertIn('connection_rate', filtr.form.fields.keys())

    def test_connection_rate_range_filter_renders_with_converted_percentage_values(self):
        self.data.update({'connection_rate_min': 50, 'connection_rate_max': 99})
        filtr = CollectionFilter(self.data, queryset=Collection.objects.all())
        self.assertInHTML('<span class="numeric-slider-range_text" id="id_connection_rate_text">50% - 99%</span>',
                          filtr.form.as_p())

    def test_connection_rate_returns_only_collections_in_given_range(self):
        self.data.update({'connection_rate_min': 50, 'connection_rate_max': 100})
        filtr = CollectionFilter(self.data, queryset=Collection.objects.all())
        qs = filtr.qs.order_by('id')
        expected_qs = Collection.objects.filter(Q(connection_rate__range=(0.5, 1)) | Q(connection_rate__isnull=True)).order_by('id')
        self.assertQuerysetEqual(expected_qs, qs)

    def test_connection_rate_include_unknown_includes_null_values_if_checked(self):
        self.data.update({'connection_rate_min': 0, 'connection_rate_max': 100})
        filtr = CollectionFilter(self.data, queryset=Collection.objects.all())
        self.assertQuerysetEqual(Collection.objects.all().order_by('id'), filtr.qs.order_by('id'))

    def test_seasonal_frequency_filter_field_exists_in_filter_and_form(self):
        self.data.update({'seasonal_frequency': True})
        filtr = CollectionFilter(self.data, queryset=Collection.objects.all())
        self.assertIn('seasonal_frequency', filtr.filters.keys())
        self.assertIn('seasonal_frequency', filtr.form.fields.keys())

    def test_seasonal_frequency_filter_returns_collections_with_non_seasonal_frequency_on_false(self):
        self.data.update({'seasonal_frequency': False})
        qs = CollectionFilter(self.data, queryset=Collection.objects.all()).qs
        self.assertIn(self.collection1, qs)
        self.assertNotIn(self.collection2, qs)

    def test_seasonal_frequency_filter_returns_collections_with_seasonal_frequency_on_true(self):
        self.data.update({'seasonal_frequency': True})
        qs = CollectionFilter(self.data, queryset=Collection.objects.all()).qs
        self.assertIn(self.collection2, qs)
        self.assertNotIn(self.collection1, qs)

    def test_seasonal_frequency_filter_returns_all_collections_when_unselected(self):
        self.data.update({'seasonal_frequency': None})
        qs = CollectionFilter(self.data, queryset=Collection.objects.all()).qs
        self.assertQuerysetEqual(Collection.objects.order_by('id'), qs.order_by('id'))

    def test_optional_frequency_filter_field_exists_in_filter_and_form(self):
        self.data.update({'optional_frequency': True})
        filtr = CollectionFilter(self.data, queryset=Collection.objects.all())
        self.assertIn('optional_frequency', filtr.filters.keys())
        self.assertIn('optional_frequency', filtr.form.fields.keys())

    def test_optional_frequency_filter_returns_collections_with_non_seasonal_frequency_on_false(self):
        self.data.update({'optional_frequency': False})
        qs = CollectionFilter(self.data, queryset=Collection.objects.all()).qs
        opts = CollectionCountOptions.objects.filter(Q(option_1__isnull=True) & Q(option_2__isnull=True) &
                                                     Q(option_3__isnull=True))
        self.assertEqual(2, opts.count())
        for opt in opts:
            self.assertIsNone(opt.option_1)
        fr = opts.first().frequency
        self.assertEqual(Collection.objects.filter(frequency=fr).first(), self.collection2)
        self.assertIn(self.collection2, qs)
        self.assertNotIn(self.collection1, qs)

    def test_optional_frequency_filter_returns_collections_with_seasonal_frequency_on_true(self):
        self.data.update({'optional_frequency': True})
        qs = CollectionFilter(self.data, queryset=Collection.objects.all()).qs
        self.assertIn(self.collection1, qs)
        self.assertNotIn(self.collection2, qs)

    def test_optional_frequency_filter_returns_all_collections_when_unselected(self):
        self.data.update({'optional_frequency': None})
        qs = CollectionFilter(self.data, queryset=Collection.objects.all()).qs
        self.assertQuerysetEqual(Collection.objects.order_by('id'), qs.order_by('id'))
