from django.urls import reverse_lazy

from utils.tests.testcases import ViewWithPermissionsTestCase
from ..models import Culture


class CultureListViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['view_culture']
    url = reverse_lazy('culture-list')

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.culture = Culture.objects.create(name='Test Culture', description='Test Description')

    def test_get_http_200_ok_for_anonymous_user(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)