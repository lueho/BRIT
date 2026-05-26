import os

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.test import TestCase

from utils.object_management.models import get_default_owner


class InitialDataTestCase(TestCase):
    def test_initial_superuser_is_created_from_migrations(self):
        User.objects.get(username=os.environ.get("ADMIN_USERNAME"))
        expected_usernames = {
            os.environ.get("ADMIN_USERNAME"),
            settings.DEFAULT_OBJECT_OWNER_USERNAME,
        }
        self.assertEqual(
            set(User.objects.values_list("username", flat=True)),
            expected_usernames,
        )

    def test_initial_group_registered_is_created_from_migrations(self):
        group = Group.objects.get(name="registered")
        self.assertIsInstance(group, Group)

    def test_initial_superuser_is_added_to_registered_group_during_migrations(self):
        user = User.objects.get(username=os.environ.get("ADMIN_USERNAME"))
        group = Group.objects.get(name="registered")
        self.assertIn(group, user.groups.all())


class UserTestCase(TestCase):
    def test_new_users_are_added_to_group_registered(self):
        user = User.objects.create(username="registered_user")
        registered = user.groups.get(name="registered")
        self.assertIsInstance(registered, Group)

    def test_get_default_owner(self):
        owner = get_default_owner()
        self.assertIsInstance(owner, User)
        self.assertEqual(owner.username, settings.DEFAULT_OBJECT_OWNER_USERNAME)
