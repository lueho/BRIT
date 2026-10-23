from pathlib import Path

import yaml
from django.conf import settings
from django.test import SimpleTestCase


def _compose_services():
    compose = yaml.safe_load((Path(settings.BASE_DIR) / "compose.yml").read_text())
    return compose["services"]


class ComposeDatabaseReadinessTests(SimpleTestCase):
    def test_database_clients_wait_for_postgres_readiness(self):
        services = _compose_services()
        for name in ("web", "celery", "db_admin"):
            with self.subTest(service=name):
                dependencies = services[name]["depends_on"]
                self.assertIsInstance(dependencies, dict)
                self.assertEqual(dependencies["db"]["condition"], "service_healthy")
        probe = services["db"].get("healthcheck", {}).get("test", [])
        self.assertTrue(probe, "PostgreSQL needs a readiness probe")
        self.assertIn("pg_isready", " ".join(probe))
        self.assertIn("127.0.0.1", " ".join(probe))


class ComposeBootstrapServiceTests(SimpleTestCase):
    def test_init_service_bootstraps_after_database_and_redis(self):
        init = _compose_services()["init"]

        self.assertIn("bootstrap_database", init["command"])
        dependencies = init["depends_on"]
        self.assertEqual(dependencies["db"]["condition"], "service_healthy")
        self.assertEqual(dependencies["redis"]["condition"], "service_started")

    def test_init_service_matches_web_build_and_source_mount(self):
        services = _compose_services()
        init, web = services["init"], services["web"]

        self.assertEqual(init["build"], web["build"])
        self.assertEqual(init["volumes"], web["volumes"])
        self.assertEqual(init["env_file"], web["env_file"])
        self.assertNotIn("restart", init)

    def test_web_and_celery_wait_for_successful_bootstrap(self):
        services = _compose_services()
        for name in ("web", "celery"):
            with self.subTest(service=name):
                dependencies = services[name]["depends_on"]
                self.assertEqual(
                    dependencies["init"]["condition"],
                    "service_completed_successfully",
                )
                self.assertEqual(dependencies["db"]["condition"], "service_healthy")
                self.assertEqual(dependencies["redis"]["condition"], "service_started")

    def test_service_dependency_graph_has_no_cycle(self):
        services = _compose_services()
        visiting, visited = set(), set()

        def visit(name):
            self.assertNotIn(name, visiting)
            visiting.add(name)
            for dependency in services[name].get("depends_on") or {}:
                if dependency not in visited:
                    visit(dependency)
            visiting.discard(name)
            visited.add(name)

        for service_name in services:
            visit(service_name)
