from django.test import TestCase, modify_settings
from users.models import get_default_owner
from django.http.request import QueryDict, MultiValueDict

from ..filters import WasteFlyerFilter
from ..models import WasteFlyer


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
