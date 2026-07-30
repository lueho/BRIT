from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from maps.models import Region
from sources.waste_collection.models import (
    Collection,
    CollectionCatchment,
    CollectionPropertyValue,
    CollectionSystem,
    WasteCategory,
)
from sources.waste_collection.waste_atlas.map_configs import MAP_CONFIGS
from sources.waste_collection.waste_atlas.map_selection import (
    COLLECTION_DETAIL_CATEGORY_BY_THEME,
    MAP_SELECTION_WASTE_CATEGORY_OVERRIDES,
    THEME_LABELS,
    WASTE_ATLAS_MAP_SELECTIONS,
)
from sources.waste_collection.waste_atlas.pages import MAP_PAGES
from utils.properties.models import Property, Unit


class ResidualWasteCompositionViewSetTests(APITestCase):
    endpoint = "/waste_collection/api/waste-atlas/residual-waste-composition/"

    @classmethod
    def setUpTestData(cls):
        cls.biowaste_property = Property.objects.create(
            name="total biowaste in residual waste"
        )
        cls.food_waste_property = Property.objects.create(
            name="total food waste in residual waste"
        )
        cls.percentage_unit, _ = Unit.objects.get_or_create(name="%")
        cls.kg_unit, _ = Unit.objects.get_or_create(name="kg/(cap.*a)")
        cls.biowaste_property.allowed_units.add(
            cls.percentage_unit,
            cls.kg_unit,
        )
        cls.food_waste_property.allowed_units.add(cls.kg_unit)

        cls.residual_category, _ = WasteCategory.objects.get_or_create(
            name="Residual waste"
        )
        cls.biowaste_category, _ = WasteCategory.objects.get_or_create(name="Biowaste")
        cls.door_to_door, _ = CollectionSystem.objects.get_or_create(
            name="Door to door"
        )

        cls.region = Region.objects.create(
            name="Rheinland-Pfalz composition test region",
            country="DE",
        )
        cls.catchment_with_data = CollectionCatchment.objects.create(
            name="Composition with data",
            region=cls.region,
        )
        cls.previous_collection = cls._create_collection(
            cls.catchment_with_data,
            cls.residual_category,
            2023,
        )
        cls.current_collection = cls._create_collection(
            cls.catchment_with_data,
            cls.residual_category,
            2024,
        )
        cls.current_collection.predecessors.add(cls.previous_collection)

        cls._create_property_value(
            cls.previous_collection,
            cls.biowaste_property,
            cls.percentage_unit,
            2021,
            18.24,
        )
        cls._create_property_value(
            cls.previous_collection,
            cls.biowaste_property,
            cls.percentage_unit,
            2023,
            23.44,
        )
        cls._create_property_value(
            cls.current_collection,
            cls.biowaste_property,
            cls.kg_unit,
            2024,
            30.2446,
        )
        cls._create_property_value(
            cls.current_collection,
            cls.food_waste_property,
            cls.kg_unit,
            2024,
            26.1086,
        )
        cls._create_property_value(
            cls.current_collection,
            cls.biowaste_property,
            cls.percentage_unit,
            2025,
            88,
            publication_status="review",
        )
        cls.staff_user = get_user_model().objects.create_user(
            username="composition-map-staff",
            is_staff=True,
        )

        cls.catchment_without_data = CollectionCatchment.objects.create(
            name="Composition without data",
            region=cls.region,
        )
        cls._create_collection(
            cls.catchment_without_data,
            cls.residual_category,
            2024,
        )

        cls.biowaste_only_catchment = CollectionCatchment.objects.create(
            name="Biowaste-only composition data",
            region=cls.region,
        )
        biowaste_collection = cls._create_collection(
            cls.biowaste_only_catchment,
            cls.biowaste_category,
            2024,
        )
        cls._create_property_value(
            biowaste_collection,
            cls.biowaste_property,
            cls.percentage_unit,
            2024,
            99,
        )

    @classmethod
    def _create_collection(cls, catchment, waste_category, year):
        return Collection.objects.create(
            catchment=catchment,
            waste_category=waste_category,
            collection_system=cls.door_to_door,
            valid_from=date(year, 1, 1),
            publication_status="published",
        )

    @staticmethod
    def _create_property_value(
        collection,
        property_obj,
        unit,
        year,
        average,
        publication_status="published",
    ):
        return CollectionPropertyValue.objects.create(
            collection=collection,
            property=property_obj,
            unit=unit,
            year=year,
            average=average,
            publication_status=publication_status,
        )

    def _by_catchment(self):
        response = self.client.get(
            self.endpoint,
            {"country": "DE", "year": 2024},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return {row["catchment_id"]: row for row in response.data}

    def test_returns_requested_metrics_with_analysis_and_amount_basis_years(self):
        row = self._by_catchment()[self.catchment_with_data.id]

        self.assertEqual(
            row,
            {
                "catchment_id": self.catchment_with_data.id,
                "bw_rw_percentage": 23.4,
                "bw_rw_kg": 30.2,
                "fwtot_rw_kg": 26.1,
                "analysis_year": 2023,
                "amount_basis_year": 2024,
            },
        )

    def test_returns_null_metrics_for_residual_catchment_without_analysis(self):
        row = self._by_catchment()[self.catchment_without_data.id]

        self.assertEqual(
            row,
            {
                "catchment_id": self.catchment_without_data.id,
                "bw_rw_percentage": None,
                "bw_rw_kg": None,
                "fwtot_rw_kg": None,
                "analysis_year": None,
                "amount_basis_year": 2024,
            },
        )

    def test_excludes_catchments_without_a_residual_waste_collection(self):
        self.assertNotIn(self.biowaste_only_catchment.id, self._by_catchment())

    def test_staff_preview_includes_the_latest_review_value(self):
        self.client.force_authenticate(self.staff_user)

        row = self._by_catchment()[self.catchment_with_data.id]

        self.assertEqual(row["bw_rw_percentage"], 88)
        self.assertEqual(row["analysis_year"], 2025)


class RheinlandPfalzResidualWasteCompositionMapTests(TestCase):
    expected_maps = {
        "bw_rw_percentage": {
            "title": "Total biowaste in residual waste",
            "legend_title": "Share of residual waste (%)",
        },
        "bw_rw_kg": {
            "title": "Total biowaste in residual waste",
            "legend_title": "Amount (kg/cap/a)",
        },
        "fwtot_rw_kg": {
            "title": "Total food waste in residual waste",
            "legend_title": "Amount (kg/cap/a)",
        },
    }

    def test_rheinland_pfalz_registers_the_three_composition_maps(self):
        pages_by_theme = {
            page["theme"]: page for page in MAP_PAGES if page["region"] == "rp"
        }

        for theme, expected in self.expected_maps.items():
            with self.subTest(theme=theme):
                page = pages_by_theme[theme]
                self.assertEqual(page["title"], expected["title"])
                self.assertEqual(page["config_key"], theme)
                self.assertIn(theme, WASTE_ATLAS_MAP_SELECTIONS["DE-RP"]["themes"])
                self.assertEqual(
                    MAP_SELECTION_WASTE_CATEGORY_OVERRIDES[theme],
                    "residual",
                )
                self.assertEqual(
                    COLLECTION_DETAIL_CATEGORY_BY_THEME[theme],
                    "residual",
                )
                self.assertIn(theme, THEME_LABELS)

    def test_composition_maps_use_quartiles_and_the_shared_endpoint(self):
        for theme, expected in self.expected_maps.items():
            with self.subTest(theme=theme):
                config = MAP_CONFIGS[theme]
                self.assertEqual(
                    config["dataUrl"],
                    "/waste_collection/api/waste-atlas/residual-waste-composition/",
                )
                self.assertEqual(config["dataField"], "_classified")
                self.assertEqual(config["numericField"], theme)
                self.assertEqual(len(config["quartileColors"]), 4)
                self.assertTrue(config["enableQuartiles"])
                self.assertEqual(config["legendTitle"], expected["legend_title"])
                self.assertNotIn("fileBase", config)

    def test_amount_maps_explain_the_2024_statistics_basis(self):
        for theme in ("bw_rw_kg", "fwtot_rw_kg"):
            with self.subTest(theme=theme):
                config = MAP_CONFIGS[theme]
                self.assertIn(
                    {"field": "amount_basis_year", "label": "Amount basis year"},
                    config["tooltipFields"],
                )
