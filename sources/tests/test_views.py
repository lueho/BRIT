from django.contrib.auth.models import User
from django.test import TestCase, modify_settings
from django.urls import reverse


# CurrentUserMiddleware is used to track object creation and change. It causes errors in the TestCases with
# logins. Can be disabled here because it is not relevant for these tests.
@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class SourcesListViewTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        User.objects.create(username='outsider')

    def setUp(self):
        self.outsider = User.objects.get(username='outsider')

    def test_get_http_200_redirect_for_anonymous(self):
        response = self.client.get(reverse('sources-list'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('sources-list'))
        self.assertEqual(response.status_code, 200)
