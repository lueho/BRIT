from django.urls import reverse

from utils.tests.testcases import ViewWithPermissionsTestCase


class SourcesListViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

    def test_get_http_200_redirect_for_anonymous(self):
        response = self.client.get(reverse('sources-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sources-list'))
        self.assertEqual(response.status_code, 200)
