import hashlib
import io
import json
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from sources.waste_collection.waste_atlas.map_configs import MAP_CONFIGS
from sources.waste_collection.waste_atlas.models import (
    WasteAtlasMapConfiguration,
    WasteAtlasRenderingSettings,
)
from sources.waste_collection.waste_atlas.pages import MAP_PAGES
from sources.waste_collection.waste_atlas.utils import ensure_initial_data

DEFAULTS_FILE = (
    Path(__file__).resolve().parents[1]
    / "waste_atlas"
    / "initial_map_configurations.json"
)

# SHA256 over
# json.dumps(map_configurations, sort_keys=True, ensure_ascii=True,
#            separators=(",", ":"))
# of the frozen canonical capture of the original 31-migration end state.
DEFAULT_CONFIGURATIONS_DIGEST = (
    "07ee944ea2f60b24b35945c05fac1fa3c935e0b321a45bba3af5fba65f82f322"
)


def _default_configurations():
    return json.loads(DEFAULTS_FILE.read_text())


def _rows():
    return list(WasteAtlasMapConfiguration.objects.order_by("key").values())


def _run_initializer():
    ensure_initial_data()


def _run_command():
    call_command("ensure_initial_data", app_label="waste_atlas", stdout=io.StringIO())


class WasteAtlasInitialDataTests(TestCase):
    def test_default_configurations_file_matches_frozen_capture(self):
        payload = json.dumps(
            _default_configurations(),
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
        )
        self.assertEqual(
            hashlib.sha256(payload.encode()).hexdigest(),
            DEFAULT_CONFIGURATIONS_DIGEST,
        )

    def test_initializer_creates_exact_default_rows(self):
        WasteAtlasMapConfiguration.objects.all().delete()
        WasteAtlasRenderingSettings.objects.all().delete()

        _run_command()

        configurations = _default_configurations()
        self.assertEqual(
            WasteAtlasMapConfiguration.objects.count(), len(configurations)
        )
        self.assertEqual(
            set(WasteAtlasMapConfiguration.objects.values_list("key", flat=True)),
            set(configurations),
        )
        for key, configuration in configurations.items():
            with self.subTest(key=key):
                self.assertEqual(
                    WasteAtlasMapConfiguration.objects.get(key=key).configuration,
                    configuration,
                )
        settings_row = WasteAtlasRenderingSettings.objects.get(
            pk=WasteAtlasRenderingSettings.SINGLETON_PK
        )
        self.assertEqual(
            settings_row.legend_width,
            WasteAtlasRenderingSettings._meta.get_field("legend_width").default,
        )
        self.assertEqual(
            settings_row.quartile_colors,
            WasteAtlasRenderingSettings._meta.get_field("quartile_colors").default(),
        )

    def test_initializer_twice_preserves_every_row_and_timestamp(self):
        _run_initializer()
        before = _rows()
        self.assertEqual(len(before), len(_default_configurations()))
        settings_before = list(WasteAtlasRenderingSettings.objects.values())

        _run_initializer()
        _run_command()

        self.assertEqual(_rows(), before)
        self.assertEqual(
            list(WasteAtlasRenderingSettings.objects.values()), settings_before
        )

    def test_initializer_preserves_customized_and_extra_rows(self):
        _run_initializer()

        target = WasteAtlasMapConfiguration.objects.get(key="connection_rate")
        target.configuration = {
            "nested": {"unknown": {"deep": [1, 2, {"x": "y"}]}},
            "dataUrl": "https://example.test/custom-endpoint/",
            "noDataColor": "#abc123",
        }
        target.save()

        empty = WasteAtlasMapConfiguration.objects.get(key="waste_ratio")
        empty.configuration = {}
        empty.save()

        renamed = WasteAtlasMapConfiguration.objects.get(key="orga_level")
        renamed.key = "orga_level_renamed"
        renamed.save()

        extra = WasteAtlasMapConfiguration.objects.create(
            key="custom_extra", configuration={"custom": True}
        )

        settings_row = WasteAtlasRenderingSettings.load()
        settings_row.quartile_colors = ["#101010", "#202020", "#303030", "#404040"]
        settings_row.legend_width = 555
        settings_row.save()
        settings_before = list(WasteAtlasRenderingSettings.objects.values())

        before = _rows()
        _run_initializer()
        _run_command()
        after = _rows()

        recreated = WasteAtlasMapConfiguration.objects.get(key="orga_level")
        self.assertEqual(
            recreated.configuration, _default_configurations()["orga_level"]
        )
        self.assertEqual([row for row in after if row["key"] != "orga_level"], before)

        self.assertEqual(
            WasteAtlasMapConfiguration.objects.get(key="connection_rate").configuration,
            target.configuration,
        )
        self.assertEqual(
            WasteAtlasMapConfiguration.objects.get(key="waste_ratio").configuration,
            {},
        )
        self.assertEqual(
            WasteAtlasMapConfiguration.objects.get(
                key="orga_level_renamed"
            ).configuration,
            renamed.configuration,
        )
        self.assertEqual(
            WasteAtlasMapConfiguration.objects.get(key="custom_extra").pk,
            extra.pk,
        )
        settings_row = WasteAtlasRenderingSettings.load()
        self.assertEqual(
            settings_row.quartile_colors,
            ["#101010", "#202020", "#303030", "#404040"],
        )
        self.assertEqual(settings_row.legend_width, 555)
        self.assertEqual(
            list(WasteAtlasRenderingSettings.objects.values()), settings_before
        )

    def test_initializer_restores_only_missing_default(self):
        _run_initializer()
        before = _rows()
        removed = WasteAtlasMapConfiguration.objects.get(key="paper_bags")
        removed_id = removed.pk
        removed_configuration = removed.configuration
        WasteAtlasMapConfiguration.objects.filter(pk=removed_id).delete()

        _run_initializer()

        after = _rows()
        self.assertEqual(len(after), len(before))
        restored = WasteAtlasMapConfiguration.objects.get(key="paper_bags")
        self.assertEqual(restored.configuration, removed_configuration)
        others_before = [row for row in before if row["key"] != "paper_bags"]
        others_after = [row for row in after if row["key"] != "paper_bags"]
        self.assertEqual(others_after, others_before)

    def test_map_configs_and_singleton_read_current_rows(self):
        _run_initializer()

        configuration = _default_configurations()["connection_rate"]
        self.assertEqual(MAP_CONFIGS["connection_rate"], configuration)
        self.assertIn("connection_rate", set(MAP_CONFIGS))

        row = WasteAtlasMapConfiguration.objects.get(key="connection_rate")
        row.configuration = {**row.configuration, "legendTitle": "Changed"}
        row.save()
        self.assertEqual(MAP_CONFIGS["connection_rate"]["legendTitle"], "Changed")

        settings_row = WasteAtlasRenderingSettings.load()
        self.assertEqual(settings_row.pk, WasteAtlasRenderingSettings.SINGLETON_PK)
        settings_row.legend_width = 432
        settings_row.save()
        self.assertEqual(WasteAtlasRenderingSettings.load().legend_width, 432)

    def test_page_registry_config_keys_are_covered_by_defaults(self):
        page_keys = {page["config_key"] for page in MAP_PAGES}
        self.assertTrue(page_keys)
        self.assertLessEqual(page_keys, set(_default_configurations()))
