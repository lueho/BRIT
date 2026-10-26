from django.conf import settings
from django.test import SimpleTestCase


class EnvironmentExampleTests(SimpleTestCase):
    def _example_variables(self):
        example_path = settings.BASE_DIR / "brit" / "settings" / ".env.example"

        self.assertTrue(example_path.exists())

        return {
            line.partition("=")[0]: line.partition("=")[2]
            for line in example_path.read_text().splitlines()
            if line and not line.startswith("#") and "=" in line
        }

    def test_local_example_contains_core_variables(self):
        variables = self._example_variables()
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

        self.assertSetEqual(expected_variables - set(variables), set())

    def test_redis_example_url_matches_compose_service(self):
        variables = self._example_variables()
        compose = (settings.BASE_DIR / "compose.yml").read_text()

        self.assertEqual(variables["REDIS_URL"], "redis://redis:6379/0")
        self.assertIn("image: redis:7-alpine", compose)
        self.assertNotIn("docker/redis", compose)
