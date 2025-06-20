from django.urls import reverse
import logging

from utils.tests.testcases import ViewWithPermissionsTestCase
from utils.object_management.views import UserCreatedObjectAutocompleteView


class UtilsDashboardViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "view_property"
    url = reverse("utils-dashboard")

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
