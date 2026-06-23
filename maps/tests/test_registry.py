from django.test import SimpleTestCase

from maps import registry, urls
from maps.contracts import SourceDomainMapMount

urlpatterns = []


class SourceDomainMapRegistryTests(SimpleTestCase):
    def setUp(self):
        self.original_map_mounts = list(registry._MAP_MOUNTS)
        self.original_listeners = list(registry._MAP_MOUNT_LISTENERS)
        self.original_urlpatterns = list(urls.urlpatterns)
        self.original_urlpattern_keys = list(urls._SOURCE_DOMAIN_MAP_MOUNT_PATTERN_KEYS)
        registry._MAP_MOUNTS.clear()
        registry._MAP_MOUNT_LISTENERS.clear()
        urls.urlpatterns[:] = urls.urlpatterns[
            : urls._SOURCE_DOMAIN_MAP_MOUNT_INSERT_INDEX
        ] + urls.urlpatterns[
            urls._SOURCE_DOMAIN_MAP_MOUNT_INSERT_INDEX
            + len(urls._SOURCE_DOMAIN_MAP_MOUNT_PATTERN_KEYS) :
        ]
        urls._SOURCE_DOMAIN_MAP_MOUNT_PATTERN_KEYS.clear()

    def tearDown(self):
        registry._MAP_MOUNTS[:] = self.original_map_mounts
        registry._MAP_MOUNT_LISTENERS[:] = self.original_listeners
        urls.urlpatterns[:] = self.original_urlpatterns
        urls._SOURCE_DOMAIN_MAP_MOUNT_PATTERN_KEYS[:] = self.original_urlpattern_keys

    def test_map_mount_listener_receives_mount_registered_after_url_module_loaded(self):
        registry.register_source_domain_map_mount_listener(
            urls._append_source_domain_map_mount_pattern
        )

        registry.register_source_domain_map_contracts(
            slug="late-test",
            map_mount=SourceDomainMapMount(
                mount_path="late-test/",
                urlconf=__name__,
            ),
        )

        matching_patterns = [
            url_pattern
            for url_pattern in urls.urlpatterns
            if getattr(url_pattern.pattern, "_route", "") == "late-test/"
        ]
        self.assertEqual(len(matching_patterns), 1)

    def test_map_mount_listener_replays_previously_registered_mounts(self):
        map_mount = SourceDomainMapMount(
            mount_path="existing-test/",
            urlconf=__name__,
        )
        registry.register_source_domain_map_contracts(
            slug="existing-test",
            map_mount=map_mount,
        )

        observed = []
        registry.register_source_domain_map_mount_listener(observed.append)

        self.assertEqual(observed, [map_mount])
