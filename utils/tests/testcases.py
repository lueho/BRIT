from django.contrib.auth.models import Permission
from django.test import TestCase, modify_settings

from users.models import User


@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
@modify_settings(MIDDLEWARE={'remove': 'debug_toolbar.middleware.DebugToolbarMiddleware'})
class UserLoginTestCase(TestCase):
    """
    CurrentUserMiddleware is used to track object creation and change. It causes errors in the TestCases with
    logins. This TestCase with disabled middleware can be used, where the object creation mechanism is not
    relevant to the test.
    """


class ViewWithPermissionsTestCase(UserLoginTestCase):
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


def comparable_model_dict(instance):
    """
    Removes '_state' so that two model instances can be compared by their __dict__ property.
    """
    return {k: v for k, v in instance.__dict__.items() if
            k not in ('_state', 'lastmodified_at', '_prefetched_objects_cache')}
