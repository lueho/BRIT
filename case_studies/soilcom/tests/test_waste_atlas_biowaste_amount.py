from datetime import date

from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from case_studies.soilcom.derived_values import clear_derived_value_config_cache
from case_studies.soilcom.models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionCatchment,
    CollectionPropertyValue,
    CollectionSystem,
    WasteCategory,
)
from maps.models import Attribute, GeoPolygon, Region
from utils.properties.models import Property, Unit


@override_settings(
    SOILCOM_SPECIFIC_WASTE_PROPERTY_ID=None,
    SOILCOM_TOTAL_WASTE_PROPERTY_ID=None,
    SOILCOM_SPECIFIC_WASTE_UNIT_ID=None,
    SOILCOM_TOTAL_WASTE_UNIT_ID=None,
    SOILCOM_POPULATION_ATTRIBUTE_ID=None,
    SOILCOM_SPECIFIC_WASTE_PROPERTY_NAME="specific waste collected [bio-atlas-test]",
    SOILCOM_TOTAL_WASTE_PROPERTY_NAME="total waste collected [bio-atlas-test]",
    SOILCOM_SPECIFIC_WASTE_UNIT_NAME="kg/(cap.*a) [bio-atlas-test]",
    SOILCOM_TOTAL_WASTE_UNIT_NAME="Mg/a [bio-atlas-test]",
    SOILCOM_POPULATION_ATTRIBUTE_NAME="Population [bio-atlas-test]",
)
class BiowasteCollectionAmountViewSetTests(APITestCase):
    """Regression tests for Karte 18 biowaste amount provenance output."""

    endpoint = "/waste_collection/api/waste-atlas/biowaste-collection-amount/"
    outline_endpoint = (
        "/waste_collection/api/waste-atlas/biowaste-collection-amount/"
        "acpv-outline-geojson/"
    )

    @classmethod
    def setUpTestData(cls):
        """Create CPV and ACPV-backed test data for the atlas endpoint."""
        cls.specific_property = Property.objects.create(
            name="specific waste collected [bio-atlas-test]"
        )
        cls.total_property = Property.objects.create(
            name="total waste collected [bio-atlas-test]"
        )
        cls.specific_unit = Unit.objects.create(name="kg/(cap.*a) [bio-atlas-test]")
        cls.total_unit = Unit.objects.create(name="Mg/a [bio-atlas-test]")
        cls.population_attribute = Attribute.objects.create(
            name="Population [bio-atlas-test]",
            unit="cap",
        )

        cls.biowaste, _ = WasteCategory.objects.get_or_create(name="Biowaste")
        cls.d2d, _ = CollectionSystem.objects.get_or_create(name="Door to door")
        cls.no_collection, _ = CollectionSystem.objects.get_or_create(
            name="No separate collection"
        )

        cls.catchment_acpv_group_a_1 = CollectionCatchment.objects.create(
            name="Biowaste Amount Aggregated A1",
            region=cls._make_region(
                "Region DE Biowaste Amount Aggregated A1",
                ((0, 0), (0, 1), (1, 1), (1, 0), (0, 0)),
            ),
        )
        cls.catchment_acpv_group_a_2 = CollectionCatchment.objects.create(
            name="Biowaste Amount Aggregated A2",
            region=cls._make_region(
                "Region DE Biowaste Amount Aggregated A2",
                ((1, 0), (1, 1), (2, 1), (2, 0), (1, 0)),
            ),
        )
        cls.catchment_acpv_group_b = CollectionCatchment.objects.create(
            name="Biowaste Amount Aggregated B",
            region=cls._make_region(
                "Region DE Biowaste Amount Aggregated B",
                ((2, 0), (2, 1), (3, 1), (3, 0), (2, 0)),
            ),
        )
        cls.catchment_cpv = CollectionCatchment.objects.create(
            name="Biowaste Amount Direct",
            region=cls._make_region(
                "Region DE Biowaste Amount Direct",
                ((0, 1), (0, 2), (1, 2), (1, 1), (0, 1)),
            ),
        )
        cls.catchment_no_collection = CollectionCatchment.objects.create(
            name="Biowaste Amount No Collection",
            region=cls._make_region(
                "Region DE Biowaste Amount No Collection",
                ((1, 1), (1, 2), (2, 2), (2, 1), (1, 1)),
            ),
        )

        cls._create_collection(
            catchment=cls.catchment_acpv_group_a_1,
            collection_system=cls.d2d,
            year=2022,
        )
        cls._create_collection(
            catchment=cls.catchment_acpv_group_a_2,
            collection_system=cls.d2d,
            year=2022,
        )
        cls._create_collection(
            catchment=cls.catchment_acpv_group_b,
            collection_system=cls.d2d,
            year=2022,
        )
        cls.acpv_group_a_source_collection_1 = cls._create_collection(
            catchment=cls.catchment_acpv_group_a_1,
            collection_system=cls.d2d,
            year=2020,
        )
        cls.acpv_group_a_source_collection_2 = cls._create_collection(
            catchment=cls.catchment_acpv_group_a_2,
            collection_system=cls.d2d,
            year=2020,
        )
        cls.acpv_group_b_source_collection = cls._create_collection(
            catchment=cls.catchment_acpv_group_b,
            collection_system=cls.d2d,
            year=2020,
        )
        cls._create_collection(
            catchment=cls.catchment_cpv,
            collection_system=cls.d2d,
            year=2022,
        )
        cls.cpv_source_collection = cls._create_collection(
            catchment=cls.catchment_cpv,
            collection_system=cls.d2d,
            year=2020,
        )
        cls._create_collection(
            catchment=cls.catchment_no_collection,
            collection_system=cls.no_collection,
            year=2022,
        )

        cls.acpv_group_a = cls._create_agg_value(
            collections=[
                cls.acpv_group_a_source_collection_1,
                cls.acpv_group_a_source_collection_2,
            ],
            property_obj=cls.specific_property,
            unit_obj=cls.specific_unit,
            year=2020,
            average=85.0,
        )
        cls.acpv_group_b = cls._create_agg_value(
            collections=[cls.acpv_group_b_source_collection],
            property_obj=cls.specific_property,
            unit_obj=cls.specific_unit,
            year=2020,
            average=95.0,
        )
        cls._create_cpv(
            collection=cls.cpv_source_collection,
            property_obj=cls.specific_property,
            unit_obj=cls.specific_unit,
            year=2020,
            average=110.0,
        )

    def setUp(self):
        """Clear derived-value config cache before each test."""
        clear_derived_value_config_cache()

    def tearDown(self):
        """Clear derived-value config cache after each test."""
        clear_derived_value_config_cache()

    @classmethod
    def _make_region(cls, name, polygon_coords):
        return Region.objects.create(
            name=name,
            country="DE",
            borders=GeoPolygon.objects.create(
                geom=MultiPolygon(Polygon(polygon_coords))
            ),
        )

    @classmethod
    def _create_collection(cls, *, catchment, collection_system, year):
        """Create a collection row for the biowaste amount endpoint."""
        return Collection.objects.create(
            name=f"{catchment.name}-{collection_system.name}-{year}",
            catchment=catchment,
            waste_category=cls.biowaste,
            collection_system=collection_system,
            valid_from=date(year, 1, 1),
        )

    @classmethod
    def _create_cpv(cls, *, collection, property_obj, unit_obj, year, average):
        """Create one collection property value for a collection and year."""
        return CollectionPropertyValue.objects.create(
            name=f"CPV {collection.id} {property_obj.id} {year}",
            collection=collection,
            property=property_obj,
            unit=unit_obj,
            year=year,
            average=average,
            is_derived=False,
            publication_status="published",
        )

    @classmethod
    def _create_agg_value(cls, *, collections, property_obj, unit_obj, year, average):
        """Create one aggregated collection property value linked to collections."""
        agg = AggregatedCollectionPropertyValue.objects.create(
            name=f"ACPV {property_obj.id} {year} {average}",
            property=property_obj,
            unit=unit_obj,
            year=year,
            average=average,
            publication_status="published",
        )
        agg.collections.set(collections)
        return agg

    def test_returns_value_sources_for_cpv_and_acpv_rows(self):
        """Expose ACPV and CPV provenance on the biowaste amount endpoint."""
        response = self.client.get(self.endpoint, {"country": "DE", "year": 2022})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data_by_catchment = {row["catchment_id"]: row for row in response.data}

        self.assertEqual(
            data_by_catchment[self.catchment_acpv_group_a_1.id]["amount"], 85.0
        )
        self.assertEqual(
            data_by_catchment[self.catchment_acpv_group_a_1.id]["value_source"],
            "acpv",
        )
        self.assertEqual(
            data_by_catchment[self.catchment_acpv_group_a_1.id]["acpv_group_key"],
            f"acpv-{self.acpv_group_a.id}",
        )
        self.assertEqual(
            data_by_catchment[self.catchment_acpv_group_a_2.id]["amount"], 85.0
        )
        self.assertEqual(
            data_by_catchment[self.catchment_acpv_group_a_2.id]["value_source"],
            "acpv",
        )
        self.assertEqual(
            data_by_catchment[self.catchment_acpv_group_a_2.id]["acpv_group_key"],
            f"acpv-{self.acpv_group_a.id}",
        )
        self.assertEqual(
            data_by_catchment[self.catchment_acpv_group_b.id]["amount"], 95.0
        )
        self.assertEqual(
            data_by_catchment[self.catchment_acpv_group_b.id]["value_source"],
            "acpv",
        )
        self.assertEqual(
            data_by_catchment[self.catchment_acpv_group_b.id]["acpv_group_key"],
            f"acpv-{self.acpv_group_b.id}",
        )
        self.assertEqual(data_by_catchment[self.catchment_cpv.id]["amount"], 110.0)
        self.assertEqual(
            data_by_catchment[self.catchment_cpv.id]["value_source"], "cpv"
        )
        self.assertIsNone(data_by_catchment[self.catchment_cpv.id]["acpv_group_key"])
        self.assertTrue(
            data_by_catchment[self.catchment_no_collection.id]["no_collection"]
        )
        self.assertIsNone(
            data_by_catchment[self.catchment_no_collection.id]["value_source"]
        )
        self.assertIsNone(
            data_by_catchment[self.catchment_no_collection.id]["acpv_group_key"]
        )

    def test_returns_dissolved_outline_features_per_acpv_group(self):
        response = self.client.get(
            self.outline_endpoint,
            {"country": "DE", "year": 2022},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        features_by_group = {
            feature["properties"]["acpv_group_key"]: feature
            for feature in response.data["features"]
        }

        self.assertEqual(
            set(features_by_group),
            {f"acpv-{self.acpv_group_a.id}", f"acpv-{self.acpv_group_b.id}"},
        )
        self.assertEqual(
            features_by_group[f"acpv-{self.acpv_group_a.id}"]["properties"][
                "catchment_ids"
            ],
            sorted(
                [
                    self.catchment_acpv_group_a_1.id,
                    self.catchment_acpv_group_a_2.id,
                ]
            ),
        )
        self.assertEqual(
            features_by_group[f"acpv-{self.acpv_group_b.id}"]["properties"][
                "catchment_ids"
            ],
            [self.catchment_acpv_group_b.id],
        )
        self.assertIn(
            features_by_group[f"acpv-{self.acpv_group_a.id}"]["geometry"]["type"],
            {"Polygon", "MultiPolygon"},
        )
