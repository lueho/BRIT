from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import TestCase

from sources.waste_collection.waste_atlas.models import (
    WasteAtlasMapConfiguration,
)
from sources.waste_collection.waste_atlas.templatetags.atlas_tags import (
    atlas_js_config,
)


class WasteAtlasMapConfigurationTests(TestCase):
    def test_database_changes_are_used_by_rendered_map_config(self):
        map_config = WasteAtlasMapConfiguration.objects.create(
            key="editable-map",
            configuration={
                "title": "Initial title",
                "dataUrl": "/api/initial/",
                "dataField": "value",
                "categories": [],
            },
        )
        map_config.configuration["title"] = "Edited online"
        map_config.save()

        rendered_config = atlas_js_config(
            {
                "country": "SE",
                "year": "2025",
                "nuts_prefix": "SE1",
                "nuts_level": "1",
            },
            map_config.key,
        )

        self.assertEqual(rendered_config["title"], "Edited online")
        self.assertEqual(rendered_config["country"], "SE")
        self.assertEqual(rendered_config["year"], 2025)
        self.assertEqual(rendered_config["nutsPrefix"], "SE1")
        self.assertEqual(rendered_config["nutsLevel"], 1)

    def test_runtime_scope_overrides_stored_scope_values(self):
        WasteAtlasMapConfiguration.objects.create(
            key="scoped-map",
            configuration={
                "country": "IT",
                "year": 2020,
                "nutsPrefix": "ITH",
                "nutsLevel": 2,
                "changeMode": True,
                "fromYear": 2019,
            },
        )

        rendered_config = atlas_js_config(
            {
                "country": "DE",
                "year": "2024",
                "nuts_prefix": "DEA",
                "nuts_level": "1",
            },
            "scoped-map",
        )

        self.assertEqual(rendered_config["country"], "DE")
        self.assertEqual(rendered_config["year"], 2024)
        self.assertEqual(rendered_config["nutsPrefix"], "DEA")
        self.assertEqual(rendered_config["nutsLevel"], 1)
        self.assertNotIn("changeMode", rendered_config)
        self.assertNotIn("fromYear", rendered_config)

    def test_configuration_must_be_a_json_object(self):
        map_config = WasteAtlasMapConfiguration(
            key="invalid-map",
            configuration=["not", "an", "object"],
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Map configuration must be a JSON object.",
        ):
            map_config.full_clean()

    def test_configuration_is_editable_in_django_admin(self):
        self.assertIn(WasteAtlasMapConfiguration, admin.site._registry)
