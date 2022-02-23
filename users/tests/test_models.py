from django.contrib.auth.models import Group, User
from django.test import TestCase


class UserTestCase(TestCase):

    def test_new_users_are_added_to_group_registered(self):
        user = User.objects.create(username='registered_user', password='very-secure!')
        registered = user.groups.get(name='registered')
        self.assertIsInstance(registered, Group)
