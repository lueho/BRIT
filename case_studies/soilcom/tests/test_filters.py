from django.http.request import QueryDict, MultiValueDict
from django.test import TestCase, modify_settings

from users.models import get_default_owner
from ..filters import CollectionFilter, WasteFlyerFilter
from ..models import Collection, CollectionCatchment, WasteFlyer


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
        cls.catchment = CollectionCatchment.objects.create(name='Test Catchment')
        child_catchment = CollectionCatchment.objects.create(parent=cls.catchment)
        cls.grandchild_catchment = CollectionCatchment.objects.create(parent=child_catchment)
        cls.unrelated_catchment = CollectionCatchment.objects.create()
        cls.collection1 = Collection.objects.create(catchment=cls.catchment)
        cls.collection2 = Collection.objects.create(catchment=cls.unrelated_catchment)
        cls.child_collection = Collection.objects.create(catchment=child_catchment)

    def test_catchment_filter(self):
        qs = CollectionFilter(data={'catchment': self.catchment.pk}, queryset=Collection.objects.all()).qs
        self.assertEqual(2, qs.count())

    def test_filter_includes_child_catchments(self):
        qs = CollectionFilter(data={'catchment': self.catchment.pk}, queryset=Collection.objects.all()).qs
        self.assertIn(self.child_collection, qs)

    def test_filter_includes_collections_from_upstream_catchments_if_there_are_none_downstream(self):
        qs = CollectionFilter(data={'catchment': self.grandchild_catchment.pk}, queryset=Collection.objects.all()).qs
        self.assertIn(self.child_collection, qs)
        self.assertIn(self.collection1, qs)
