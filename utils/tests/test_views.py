from django.test import (RequestFactory, TestCase)
from django.urls import reverse
from django_filters import CharFilter, FilterSet

from utils.properties.models import Property
from .testcases import ViewWithPermissionsTestCase
from ..views import BRITFilterView


class MockFilterSet(FilterSet):
    name = CharFilter(field_name='name', lookup_expr='icontains', initial='Initial property')

    class Meta:
        model = Property
        fields = ['name']


class BRITFilterViewTestCase(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.view = BRITFilterView()
        self.view.filterset_class = MockFilterSet

    def test_initial_filter_values_extraction(self):
        expected_initial_values = {'name': 'Initial name'}
        self.assertEqual(self.view.get_default_filters(), expected_initial_values)

    def test_get_with_empty_query_parameters(self):
        request = self.factory.get('/')
        self.view.request = request
        self.view.kwargs = {}
        response = self.view.get(request)

        self.assertEqual(response.status_code, 302)
        redirect_url = response.url
        self.assertEqual('/?name=Initial+property', redirect_url)

    def test_get_with_query_parameters(self):
        request = self.factory.get('/?name=Other+property')
        self.view.request = request
        self.view.kwargs = {}
        response = self.view.get(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data['filter'].data, {'name': ['Other property']})


class UtilsDashboardViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'view_property'
    url = reverse('utils-dashboard')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={self.url}')

    def test_get_http_403_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
