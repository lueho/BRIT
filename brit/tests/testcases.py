from django.test import TestCase, modify_settings

@modify_settings(MIDDLEWARE={'remove': 'ai_django_core.middleware.current_user.CurrentUserMiddleware'})
class UserLoginTestCase(TestCase):
    """
    CurrentUserMiddleware is used to track object creation and change. It causes errors in the TestCases with
    logins. This TestCase with disabled middleware can be used, where the object creation mechanism is not
    relevant to the test.
    """