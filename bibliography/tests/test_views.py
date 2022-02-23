from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from ..models import Source


class SourceListViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider', password='very-secure!')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('source-list'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-list'))
        self.assertEqual(response.status_code, 200)


class SourceCreateViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider', password='very-secure!')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(reverse('source-create'))
        self.assertEqual(response.status_code, 302)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-create'))
        self.assertEqual(response.status_code, 200)


class SourceDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner', password='very-secure!')
        User.objects.create(username='outsider', password='very-secure!')

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.source = Source.objects.create(
            owner=self.owner
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('source-detail', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-detail', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 200)


class SourceModalDetailViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='owner', password='very-secure!')
        User.objects.create(username='outsider', password='very-secure!')

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.source = Source.objects.create(
            owner=self.owner
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('source-detail-modal', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_logged_in_users(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('source-detail-modal', kwargs={'pk': self.source.pk}))
        self.assertEqual(response.status_code, 200)
