from django.contrib.auth.models import Permission
from django.test import TestCase, modify_settings
from rest_framework.test import APIClient

from users.models import User


@modify_settings(MIDDLEWARE={'remove': 'ambient_toolbox.middleware.current_user.CurrentUserMiddleware'})
@modify_settings(MIDDLEWARE={'remove': 'debug_toolbar.middleware.DebugToolbarMiddleware'})
class UserLoginTestCase(TestCase):
    """
    CurrentUserMiddleware is used to track object creation and change. It causes errors in the TestCases with
    logins. This TestCase with disabled middleware can be used, where the object creation mechanism is not
    relevant to the test.
    """


class ViewWithPermissionsTestCase(UserLoginTestCase):
    """This TestCase is used for testing views with permissions. There are three levels of access:
    - outsider: no permissions
    - outsider: authenticated but without any special permissions
    - member: has permissions which are specified in the member_permissions class variable"""
    outsider = None
    member = None
    member_permissions = None

    @classmethod
    def setUpTestData(cls):
        cls.outsider = User.objects.create(username='outsider')
        cls.member = User.objects.create(username='member')
        if cls.member_permissions:
            if isinstance(cls.member_permissions, str):
                cls.member_permissions = [cls.member_permissions]
            for codename in cls.member_permissions:
                cls.member.user_permissions.add(Permission.objects.get(codename=codename))


class ViewSetWithPermissionsTestCase(ViewWithPermissionsTestCase):
    """
    This TestCase is used for testing ViewSets. It has the same functionality as ViewWithPermissionsTestCase,
    but it uses the APIClient class provided by django rest framework instead of the standard django test client.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.client = APIClient()


def comparable_model_dict(instance):
    """
    Removes '_state' so that two model instances can be compared by their __dict__ property.
    """
    return {k: v for k, v in instance.__dict__.items() if
            k not in ('_state', 'lastmodified_at', '_prefetched_objects_cache')}
