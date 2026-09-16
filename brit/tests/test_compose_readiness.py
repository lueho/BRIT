from pathlib import Path

import yaml
from django.conf import settings
from django.test import SimpleTestCase


class ComposeDatabaseReadinessTests(SimpleTestCase):
    def test_database_clients_wait_for_postgres_readiness(self):
        compose = yaml.safe_load((Path(settings.BASE_DIR) / "compose.yml").read_text())
        services = compose["services"]
        for name in ("web", "celery", "db_admin"):
            with self.subTest(service=name):
                dependencies = services[name]["depends_on"]
                self.assertIsInstance(dependencies, dict)
                self.assertEqual(dependencies["db"]["condition"], "service_healthy")
        probe = services["db"].get("healthcheck", {}).get("test", [])
        self.assertTrue(probe, "PostgreSQL needs a readiness probe")
        self.assertIn("pg_isready", " ".join(probe))
        self.assertIn("127.0.0.1", " ".join(probe))
