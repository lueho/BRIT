from django.conf import settings
from django.test import SimpleTestCase


class EnvironmentExampleTests(SimpleTestCase):
    def test_local_example_contains_core_variables(self):
        example_path = settings.BASE_DIR / "brit" / "settings" / ".env.example"

        self.assertTrue(example_path.exists())

        variables = {
            line.partition("=")[0]
            for line in example_path.read_text().splitlines()
            if line and not line.startswith("#") and "=" in line
        }
        expected_variables = {
            "ADMIN_USERNAME",
            "POSTGRES_DB",
            "POSTGRES_HOST",
            "POSTGRES_PASSWORD",
            "POSTGRES_PORT",
            "POSTGRES_USER",
            "REDIS_URL",
            "SECRET_KEY",
        }

        self.assertSetEqual(expected_variables - variables, set())
