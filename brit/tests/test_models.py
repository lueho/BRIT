from django.test import TestCase, modify_settings

from users.models import get_default_owner
from ..models import OwnedObjectModel


class OwnedObject(OwnedObjectModel):
    """Concrete model that is used to test the abstract OwnedObjectModel"""


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class OwnedObjectModelTestCase(TestCase):

    def test_get_default_owner(self):
        obj = OwnedObject.objects.create()
        self.assertEqual(get_default_owner(), obj.owner)
