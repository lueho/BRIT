from datetime import date

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
    WasteStream,
)
from maps.models import Attribute, Region, RegionAttributeValue
from utils.properties.models import Property, Unit


class GreenWasteCollectionSystemCountViewSetTests(APITestCase):
    """Tests for Green Waste collection-system count atlas endpoint."""

    endpoint = "/waste_collection/api/waste-atlas/green-waste-collection-system-count/"

    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name="Region DE", country="DE")
        cls.catchment_a = CollectionCatchment.objects.create(
            name="Catchment A",
            region=cls.region,
        )
        cls.catchment_b = CollectionCatchment.objects.create(
            name="Catchment B",
            region=cls.region,
        )

        cls.d2d = CollectionSystem.objects.create(name="Door to door")
        cls.bring_point = CollectionSystem.objects.create(name="Bring point")
        cls.recycling = CollectionSystem.objects.create(name="Recycling centre")

        cls.green_category = WasteCategory.objects.create(name="Green waste")
        cls.bio_category = WasteCategory.objects.create(name="Biowaste")

        cls.green_stream = WasteStream.objects.create(category=cls.green_category)
        cls.bio_stream = WasteStream.objects.create(category=cls.bio_category)

        cls._create_collection(
            catchment=cls.catchment_a,
            waste_stream=cls.green_stream,
            collection_system=cls.d2d,
            year=2024,
        )
        cls._create_collection(
            catchment=cls.catchment_a,
            waste_stream=cls.green_stream,
            collection_system=cls.bring_point,
            year=2024,
        )
        # Duplicate system should not increase distinct system count.
        cls._create_collection(
            catchment=cls.catchment_a,
            waste_stream=cls.green_stream,
            collection_system=cls.bring_point,
            year=2024,
        )

        cls._create_collection(
            catchment=cls.catchment_b,
            waste_stream=cls.green_stream,
            collection_system=cls.recycling,
            year=2024,
        )
        # Non-green category in the same catchment must be ignored.
        cls._create_collection(
            catchment=cls.catchment_b,
            waste_stream=cls.bio_stream,
            collection_system=cls.d2d,
            year=2024,
        )
        # Different year must be ignored for year=2024 filter.
        cls._create_collection(
            catchment=cls.catchment_b,
            waste_stream=cls.green_stream,
            collection_system=cls.bring_point,
            year=2022,
        )

    @classmethod
    def _create_collection(cls, *, catchment, waste_stream, collection_system, year):
        """Create a collection row for atlas endpoint test data."""
        return Collection.objects.create(
            name=f"{catchment.name}-{collection_system.name}-{year}",
            catchment=catchment,
            waste_stream=waste_stream,
            collection_system=collection_system,
            valid_from=date(year, 1, 1),
        )

    def test_returns_distinct_green_waste_system_count_per_catchment(self):
        """It counts distinct systems for Green waste category only."""
        response = self.client.get(self.endpoint, {"country": "DE", "year": 2024})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        count_by_catchment = {
            row["catchment_id"]: row["collection_system_count"] for row in response.data
        }

        self.assertEqual(count_by_catchment[self.catchment_a.id], 2)
        self.assertEqual(count_by_catchment[self.catchment_b.id], 1)
        self.assertEqual(len(count_by_catchment), 2)


@override_settings(
    SOILCOM_SPECIFIC_WASTE_PROPERTY_ID=None,
    SOILCOM_TOTAL_WASTE_PROPERTY_ID=None,
    SOILCOM_SPECIFIC_WASTE_UNIT_ID=None,
    SOILCOM_TOTAL_WASTE_UNIT_ID=None,
    SOILCOM_POPULATION_ATTRIBUTE_ID=None,
    SOILCOM_SPECIFIC_WASTE_PROPERTY_NAME="specific waste collected [green-atlas-test]",
    SOILCOM_TOTAL_WASTE_PROPERTY_NAME="total waste collected [green-atlas-test]",
    SOILCOM_SPECIFIC_WASTE_UNIT_NAME="kg/(cap.*a) [green-atlas-test]",
    SOILCOM_TOTAL_WASTE_UNIT_NAME="Mg/a [green-atlas-test]",
    SOILCOM_POPULATION_ATTRIBUTE_NAME="Population [green-atlas-test]",
)
class GreenWasteCollectionAmountViewSetTests(APITestCase):
    """Tests for Green Waste collection amount atlas endpoint."""

    endpoint = "/waste_collection/api/waste-atlas/green-waste-collection-amount/"

    @classmethod
    def setUpTestData(cls):
        cls.specific_property = Property.objects.create(
            name="specific waste collected [green-atlas-test]"
        )
        cls.total_property = Property.objects.create(
            name="total waste collected [green-atlas-test]"
        )
        cls.specific_unit = Unit.objects.create(name="kg/(cap.*a) [green-atlas-test]")
        cls.total_unit = Unit.objects.create(name="Mg/a [green-atlas-test]")
        cls.population_attribute = Attribute.objects.create(
            name="Population [green-atlas-test]",
            unit="cap",
        )

        cls.region = Region.objects.create(name="Region DE Amount", country="DE")
        cls.green_category, _ = WasteCategory.objects.get_or_create(name="Green waste")
        cls.bio_category, _ = WasteCategory.objects.get_or_create(name="Biowaste")
        cls.green_stream = WasteStream.objects.create(category=cls.green_category)
        cls.bio_stream = WasteStream.objects.create(category=cls.bio_category)

        cls.d2d, _ = CollectionSystem.objects.get_or_create(name="Door to door")
        cls.bring_point, _ = CollectionSystem.objects.get_or_create(name="Bring point")
        cls.no_collection, _ = CollectionSystem.objects.get_or_create(
            name="No separate collection"
        )

        cls.catchment_agg = CollectionCatchment.objects.create(
            name="GW Amount Aggregated",
            region=cls.region,
        )
        cls.catchment_specific = CollectionCatchment.objects.create(
            name="GW Amount Specific",
            region=cls.region,
        )
        cls.catchment_total = CollectionCatchment.objects.create(
            name="GW Amount Total",
            region=cls.region,
        )
        cls.catchment_agg_total = CollectionCatchment.objects.create(
            name="GW Amount Aggregated Total",
            region=cls.region,
        )
        cls.catchment_no_collection = CollectionCatchment.objects.create(
            name="GW Amount No Collection",
            region=cls.region,
        )
        cls.catchment_ignored = CollectionCatchment.objects.create(
            name="GW Amount Ignored",
            region=cls.region,
        )

        cls.agg_collection_a = cls._create_collection(
            catchment=cls.catchment_agg,
            waste_stream=cls.green_stream,
            collection_system=cls.d2d,
            year=2024,
        )
        cls.agg_collection_b = cls._create_collection(
            catchment=cls.catchment_agg,
            waste_stream=cls.green_stream,
            collection_system=cls.bring_point,
            year=2024,
        )

        cls.specific_collection = cls._create_collection(
            catchment=cls.catchment_specific,
            waste_stream=cls.green_stream,
            collection_system=cls.d2d,
            year=2024,
        )
        cls.total_collection = cls._create_collection(
            catchment=cls.catchment_total,
            waste_stream=cls.green_stream,
            collection_system=cls.d2d,
            year=2024,
        )
        cls.agg_total_collection = cls._create_collection(
            catchment=cls.catchment_agg_total,
            waste_stream=cls.green_stream,
            collection_system=cls.d2d,
            year=2024,
        )
        cls.no_collection_collection = cls._create_collection(
            catchment=cls.catchment_no_collection,
            waste_stream=cls.green_stream,
            collection_system=cls.no_collection,
            year=2024,
        )
        cls._create_collection(
            catchment=cls.catchment_ignored,
            waste_stream=cls.bio_stream,
            collection_system=cls.d2d,
            year=2024,
        )

        cls._create_cpv(
            collection=cls.agg_collection_a,
            property_obj=cls.specific_property,
            unit_obj=cls.specific_unit,
            year=2024,
            average=80.0,
        )
        cls._create_agg_value(
            collections=[cls.agg_collection_a, cls.agg_collection_b],
            property_obj=cls.specific_property,
            unit_obj=cls.specific_unit,
            year=2024,
            average=120.0,
        )

        cls._create_cpv(
            collection=cls.specific_collection,
            property_obj=cls.specific_property,
            unit_obj=cls.specific_unit,
            year=2024,
            average=90.0,
        )

        cls._create_cpv(
            collection=cls.total_collection,
            property_obj=cls.total_property,
            unit_obj=cls.total_unit,
            year=2024,
            average=50.0,
        )

        cls._create_agg_value(
            collections=[cls.agg_total_collection],
            property_obj=cls.total_property,
            unit_obj=cls.total_unit,
            year=2024,
            average=30.0,
        )

        RegionAttributeValue.objects.create(
            name="Population GW Amount",
            region=cls.region,
            attribute=cls.population_attribute,
            date=date(2024, 1, 1),
            value=1000,
        )

    def setUp(self):
        """Clear derived-value config cache before each test."""
        clear_derived_value_config_cache()

    def tearDown(self):
        """Clear derived-value config cache after each test."""
        clear_derived_value_config_cache()

    @classmethod
    def _create_collection(cls, *, catchment, waste_stream, collection_system, year):
        """Create a collection row for green-waste amount endpoint test data."""
        return Collection.objects.create(
            name=f"{catchment.name}-{collection_system.name}-{year}",
            catchment=catchment,
            waste_stream=waste_stream,
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

    def test_returns_green_waste_amount_with_aggregation_and_fallbacks(self):
        """It prefers aggregated specific values and falls back to specific/total."""
        response = self.client.get(self.endpoint, {"country": "DE", "year": 2024})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data_by_catchment = {row["catchment_id"]: row for row in response.data}

        self.assertEqual(data_by_catchment[self.catchment_agg.id]["amount"], 120.0)
        self.assertEqual(data_by_catchment[self.catchment_specific.id]["amount"], 90.0)
        self.assertEqual(data_by_catchment[self.catchment_total.id]["amount"], 50.0)
        self.assertEqual(data_by_catchment[self.catchment_agg_total.id]["amount"], 30.0)

        self.assertTrue(
            data_by_catchment[self.catchment_no_collection.id]["no_collection"]
        )
        self.assertIsNone(data_by_catchment[self.catchment_no_collection.id]["amount"])

        self.assertNotIn(self.catchment_ignored.id, data_by_catchment)


class BinSizeViewSetTests(APITestCase):
    """Regression tests for Karte 23–26 min bin size and required bin capacity endpoints."""

    @classmethod
    def setUpTestData(cls):
        cls.bio_category, _ = WasteCategory.objects.get_or_create(name="Biowaste")
        cls.residual_category, _ = WasteCategory.objects.get_or_create(
            name="Residual waste"
        )
        cls.green_category, _ = WasteCategory.objects.get_or_create(name="Green waste")

        cls.bio_stream = WasteStream.objects.create(category=cls.bio_category)
        cls.residual_stream = WasteStream.objects.create(category=cls.residual_category)
        cls.green_stream = WasteStream.objects.create(category=cls.green_category)

        cls.d2d, _ = CollectionSystem.objects.get_or_create(name="Door to door")
        cls.bring_point, _ = CollectionSystem.objects.get_or_create(name="Bring point")

        cls.region = Region.objects.create(name="Region BinSize DE", country="DE")

        cls.catchment_bio = CollectionCatchment.objects.create(
            name="BinSize Bio", region=cls.region
        )
        cls.catchment_residual = CollectionCatchment.objects.create(
            name="BinSize Residual", region=cls.region
        )
        cls.catchment_no_bin = CollectionCatchment.objects.create(
            name="BinSize NoBin", region=cls.region
        )
        cls.catchment_ignored = CollectionCatchment.objects.create(
            name="BinSize Ignored", region=cls.region
        )

        cls.bio_col = Collection.objects.create(
            name="BinSize bio col",
            catchment=cls.catchment_bio,
            waste_stream=cls.bio_stream,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
            min_bin_size=80,
            required_bin_capacity=10,
            required_bin_capacity_reference="person",
        )
        cls.residual_col = Collection.objects.create(
            name="BinSize residual col",
            catchment=cls.catchment_residual,
            waste_stream=cls.residual_stream,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
            min_bin_size=120,
            required_bin_capacity=40,
            required_bin_capacity_reference="household",
        )
        # D2D collection with null bin size fields
        Collection.objects.create(
            name="BinSize no bin col",
            catchment=cls.catchment_no_bin,
            waste_stream=cls.bio_stream,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
        )
        # Non-D2D collection — must be excluded from bin size maps
        Collection.objects.create(
            name="BinSize bring point col",
            catchment=cls.catchment_ignored,
            waste_stream=cls.bio_stream,
            collection_system=cls.bring_point,
            valid_from=date(2024, 1, 1),
            min_bin_size=60,
        )

    # --- Karte 23: biowaste min bin size ---

    def test_biowaste_min_bin_size_returns_d2d_collections(self):
        """Karte 23 returns min_bin_size for D2D biowaste catchments."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/biowaste-min-bin-size/",
            {"country": "DE", "year": 2024},
        )
        self.assertEqual(response.status_code, 200)
        by_catchment = {r["catchment_id"]: r for r in response.data}
        self.assertEqual(by_catchment[self.catchment_bio.id]["min_bin_size"], 80.0)
        self.assertIn(self.catchment_no_bin.id, by_catchment)
        self.assertIsNone(by_catchment[self.catchment_no_bin.id]["min_bin_size"])
        self.assertNotIn(self.catchment_residual.id, by_catchment)

    def test_biowaste_min_bin_size_excludes_non_d2d(self):
        """Karte 23 excludes bring-point and other non-D2D collections."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/biowaste-min-bin-size/",
            {"country": "DE", "year": 2024},
        )
        by_catchment = {r["catchment_id"]: r for r in response.data}
        self.assertNotIn(self.catchment_ignored.id, by_catchment)

    # --- Karte 24: residual min bin size ---

    def test_residual_min_bin_size_returns_d2d_collections(self):
        """Karte 24 returns min_bin_size for D2D residual catchments."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/residual-min-bin-size/",
            {"country": "DE", "year": 2024},
        )
        self.assertEqual(response.status_code, 200)
        by_catchment = {r["catchment_id"]: r for r in response.data}
        self.assertEqual(
            by_catchment[self.catchment_residual.id]["min_bin_size"], 120.0
        )
        self.assertNotIn(self.catchment_bio.id, by_catchment)

    # --- Karte 25: biowaste required bin capacity ---

    def test_biowaste_required_bin_capacity_returns_value_and_reference(self):
        """Karte 25 returns required_bin_capacity and reference for biowaste D2D."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/biowaste-required-bin-capacity/",
            {"country": "DE", "year": 2024},
        )
        self.assertEqual(response.status_code, 200)
        by_catchment = {r["catchment_id"]: r for r in response.data}
        row = by_catchment[self.catchment_bio.id]
        self.assertEqual(row["required_bin_capacity"], 10.0)
        self.assertEqual(row["required_bin_capacity_reference"], "person")
        self.assertNotIn(self.catchment_residual.id, by_catchment)

    def test_biowaste_required_bin_capacity_null_when_not_set(self):
        """Karte 25 returns null capacity for catchments without the field set."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/biowaste-required-bin-capacity/",
            {"country": "DE", "year": 2024},
        )
        by_catchment = {r["catchment_id"]: r for r in response.data}
        row = by_catchment[self.catchment_no_bin.id]
        self.assertIsNone(row["required_bin_capacity"])
        self.assertIsNone(row["required_bin_capacity_reference"])

    # --- Karte 26: residual required bin capacity ---

    def test_residual_required_bin_capacity_returns_value_and_reference(self):
        """Karte 26 returns required_bin_capacity and reference for residual D2D."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/residual-required-bin-capacity/",
            {"country": "DE", "year": 2024},
        )
        self.assertEqual(response.status_code, 200)
        by_catchment = {r["catchment_id"]: r for r in response.data}
        row = by_catchment[self.catchment_residual.id]
        self.assertEqual(row["required_bin_capacity"], 40.0)
        self.assertEqual(row["required_bin_capacity_reference"], "household")
        self.assertNotIn(self.catchment_bio.id, by_catchment)


@override_settings(
    SOILCOM_SPECIFIC_WASTE_PROPERTY_ID=None,
    SOILCOM_TOTAL_WASTE_PROPERTY_ID=None,
    SOILCOM_SPECIFIC_WASTE_UNIT_ID=None,
    SOILCOM_TOTAL_WASTE_UNIT_ID=None,
    SOILCOM_POPULATION_ATTRIBUTE_ID=None,
    SOILCOM_SPECIFIC_WASTE_PROPERTY_NAME="specific waste collected [organic-atlas-test]",
    SOILCOM_TOTAL_WASTE_PROPERTY_NAME="total waste collected [organic-atlas-test]",
    SOILCOM_SPECIFIC_WASTE_UNIT_NAME="kg/(cap.*a) [organic-atlas-test]",
    SOILCOM_TOTAL_WASTE_UNIT_NAME="Mg/a [organic-atlas-test]",
    SOILCOM_POPULATION_ATTRIBUTE_NAME="Population [organic-atlas-test]",
)
class OrganicAmountViewSetTests(APITestCase):
    """Regression tests for Karte 27 (organic amount) and Karte 28 (organic ratio)."""

    @classmethod
    def setUpTestData(cls):
        clear_derived_value_config_cache()

        cls.specific_property = Property.objects.create(
            name="specific waste collected [organic-atlas-test]"
        )
        cls.total_property = Property.objects.create(
            name="total waste collected [organic-atlas-test]"
        )
        cls.specific_unit = Unit.objects.create(name="kg/(cap.*a) [organic-atlas-test]")
        cls.total_unit = Unit.objects.create(name="Mg/a [organic-atlas-test]")
        cls.population_attribute = Attribute.objects.create(
            name="Population [organic-atlas-test]",
            unit="cap",
        )

        cls.bio_category, _ = WasteCategory.objects.get_or_create(name="Biowaste")
        cls.green_category, _ = WasteCategory.objects.get_or_create(name="Green waste")
        cls.residual_category, _ = WasteCategory.objects.get_or_create(
            name="Residual waste"
        )

        cls.bio_stream = WasteStream.objects.create(category=cls.bio_category)
        cls.green_stream = WasteStream.objects.create(category=cls.green_category)
        cls.residual_stream = WasteStream.objects.create(category=cls.residual_category)

        cls.d2d, _ = CollectionSystem.objects.get_or_create(name="Door to door")

        cls.region = Region.objects.create(name="Region Organic DE", country="DE")

        cls.catchment_both = CollectionCatchment.objects.create(
            name="Organic Both", region=cls.region
        )
        cls.catchment_bio_only = CollectionCatchment.objects.create(
            name="Organic Bio Only", region=cls.region
        )
        cls.catchment_green_only = CollectionCatchment.objects.create(
            name="Organic Green Only", region=cls.region
        )
        cls.catchment_residual_only = CollectionCatchment.objects.create(
            name="Organic Residual Only", region=cls.region
        )

        bio_col_both = Collection.objects.create(
            name="Organic bio both",
            catchment=cls.catchment_both,
            waste_stream=cls.bio_stream,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
        )
        CollectionPropertyValue.objects.create(
            collection=bio_col_both,
            property=cls.specific_property,
            unit=cls.specific_unit,
            year=2024,
            average=100.0,
        )

        green_col_both = Collection.objects.create(
            name="Organic green both",
            catchment=cls.catchment_both,
            waste_stream=cls.green_stream,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
        )
        acpv = AggregatedCollectionPropertyValue.objects.create(
            name="Organic green ACPV both",
            property=cls.specific_property,
            unit=cls.specific_unit,
            year=2024,
            average=80.0,
            publication_status="published",
        )
        acpv.collections.set([green_col_both])

        residual_col_both = Collection.objects.create(
            name="Organic residual both",
            catchment=cls.catchment_both,
            waste_stream=cls.residual_stream,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
        )
        CollectionPropertyValue.objects.create(
            collection=residual_col_both,
            property=cls.specific_property,
            unit=cls.specific_unit,
            year=2024,
            average=200.0,
        )

        bio_col_bio_only = Collection.objects.create(
            name="Organic bio only col",
            catchment=cls.catchment_bio_only,
            waste_stream=cls.bio_stream,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
        )
        CollectionPropertyValue.objects.create(
            collection=bio_col_bio_only,
            property=cls.specific_property,
            unit=cls.specific_unit,
            year=2024,
            average=60.0,
        )

        green_col_green_only = Collection.objects.create(
            name="Organic green only col",
            catchment=cls.catchment_green_only,
            waste_stream=cls.green_stream,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
        )
        CollectionPropertyValue.objects.create(
            collection=green_col_green_only,
            property=cls.specific_property,
            unit=cls.specific_unit,
            year=2024,
            average=50.0,
        )

        residual_col_only = Collection.objects.create(
            name="Organic residual only col",
            catchment=cls.catchment_residual_only,
            waste_stream=cls.residual_stream,
            collection_system=cls.d2d,
            valid_from=date(2024, 1, 1),
        )
        CollectionPropertyValue.objects.create(
            collection=residual_col_only,
            property=cls.specific_property,
            unit=cls.specific_unit,
            year=2024,
            average=150.0,
        )

    def setUp(self):
        clear_derived_value_config_cache()

    # --- Karte 27: organic collection amount ---

    def test_organic_amount_sums_bio_and_green(self):
        """Karte 27 returns the sum of bio + green waste amounts per catchment."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/organic-collection-amount/",
            {"country": "DE", "year": 2024},
        )
        self.assertEqual(response.status_code, 200)
        by_catchment = {r["catchment_id"]: r for r in response.data}
        self.assertAlmostEqual(by_catchment[self.catchment_both.id]["amount"], 180.0)

    def test_organic_amount_bio_only_catchment(self):
        """Karte 27 includes catchments with only bio waste."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/organic-collection-amount/",
            {"country": "DE", "year": 2024},
        )
        by_catchment = {r["catchment_id"]: r for r in response.data}
        self.assertAlmostEqual(by_catchment[self.catchment_bio_only.id]["amount"], 60.0)

    def test_organic_amount_green_only_catchment(self):
        """Karte 27 includes catchments with only green waste."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/organic-collection-amount/",
            {"country": "DE", "year": 2024},
        )
        by_catchment = {r["catchment_id"]: r for r in response.data}
        self.assertAlmostEqual(
            by_catchment[self.catchment_green_only.id]["amount"], 50.0
        )

    def test_organic_amount_excludes_residual_only_catchment(self):
        """Karte 27 does not include catchments with residual waste only."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/organic-collection-amount/",
            {"country": "DE", "year": 2024},
        )
        by_catchment = {r["catchment_id"]: r for r in response.data}
        self.assertNotIn(self.catchment_residual_only.id, by_catchment)

    # --- Karte 28: organic waste ratio ---

    def test_organic_ratio_computed_correctly(self):
        """Karte 28 computes organic / (organic + residual) for catchments with both."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/organic-waste-ratio/",
            {"country": "DE", "year": 2024},
        )
        self.assertEqual(response.status_code, 200)
        by_catchment = {r["catchment_id"]: r for r in response.data}
        row = by_catchment[self.catchment_both.id]
        self.assertAlmostEqual(row["organic_amount"], 180.0)
        self.assertAlmostEqual(row["residual_amount"], 200.0)
        self.assertAlmostEqual(row["ratio"], 180.0 / 380.0, places=4)

    def test_organic_ratio_null_when_only_organic(self):
        """Karte 28 returns null ratio for catchments without residual data."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/organic-waste-ratio/",
            {"country": "DE", "year": 2024},
        )
        by_catchment = {r["catchment_id"]: r for r in response.data}
        self.assertIsNone(by_catchment[self.catchment_bio_only.id]["ratio"])

    def test_organic_ratio_includes_residual_only_catchment(self):
        """Karte 28 includes residual-only catchments (null ratio)."""
        response = self.client.get(
            "/waste_collection/api/waste-atlas/organic-waste-ratio/",
            {"country": "DE", "year": 2024},
        )
        by_catchment = {r["catchment_id"]: r for r in response.data}
        self.assertIn(self.catchment_residual_only.id, by_catchment)
        self.assertIsNone(by_catchment[self.catchment_residual_only.id]["ratio"])
