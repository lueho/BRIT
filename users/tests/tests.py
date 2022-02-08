from django.contrib.auth.models import User
from django.test import TestCase

from users.models import ReferenceUsers


class InitialUserTestCase(TestCase):

    def test_init(self):
        standard_owner = ReferenceUsers.objects.get.standard_owner
        self.assertIsInstance(standard_owner, User)
        self.assertEqual(User.objects.all().count(), 1)
        self.assertEqual(standard_owner.username, 'flexibi')
        standard_owner = ReferenceUsers.objects.get.standard_owner
        self.assertIsInstance(standard_owner, User)
        self.assertEqual(User.objects.all().count(), 1)
        self.assertEqual(standard_owner.username, 'flexibi')