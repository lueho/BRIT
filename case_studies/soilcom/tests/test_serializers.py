from datetime import date
from decimal import Decimal

from django.db import models
from django.test import TestCase
from factory.django import mute_signals

from maps.models import Attribute, LauRegion, NutsRegion, RegionAttributeValue
from materials.models import MaterialCategory

from ..models import (
    Collection,
    CollectionCatchment,
    CollectionFrequency,
    CollectionSystem,
    Collector,
    FeeSystem,
    WasteCategory,
    WasteComponent,
    WasteFlyer,
    WasteStream,
)
from ..serializers import CollectionFlatSerializer, CollectionModelSerializer


class CollectionModelSerializerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        MaterialCategory.objects.create(name="Biowaste component")
        cls.allowed_material_1 = WasteComponent.objects.create(
            name="Allowed Material 1"
        )
        cls.allowed_material_2 = WasteComponent.objects.create(
            name="Allowed Material 2"
        )
        cls.forbidden_material_1 = WasteComponent.objects.create(
            name="Forbidden Material 1"
        )
        cls.forbidden_material_2 = WasteComponent.objects.create(
            name="Forbidden Material 2"
        )
        waste_stream = WasteStream.objects.create(
            name="Test waste stream",
            category=WasteCategory.objects.create(name="Test category"),
        )
        waste_stream.allowed_materials.add(cls.allowed_material_1)
        waste_stream.allowed_materials.add(cls.allowed_material_2)
        waste_stream.forbidden_materials.add(cls.forbidden_material_1)
        waste_stream.forbidden_materials.add(cls.forbidden_material_2)

        with mute_signals(models.signals.post_save):
            waste_flyer_1 = WasteFlyer.objects.create(
                abbreviation="WasteFlyer123", url="https://www.test-flyer.org"
            )
            waste_flyer_2 = WasteFlyer.objects.create(
                abbreviation="WasteFlyer456", url="https://www.best-flyer.org"
            )
        frequency = CollectionFrequency.objects.create(name="Test Frequency")
        cls.collection = Collection.objects.create(
            name="Test Collection",
            catchment=CollectionCatchment.objects.create(name="Test catchment"),
            collector=Collector.objects.create(name="Test collector"),
            collection_system=CollectionSystem.objects.create(name="Test system"),
            waste_stream=waste_stream,
            frequency=frequency,
            valid_from=date(2020, 1, 1),
            description="This is a test case.",
        )
        cls.collection.flyers.add(waste_flyer_1)
        cls.collection.flyers.add(waste_flyer_2)

    def test_all_keys_are_present_in_result_data(self):
        serializer = CollectionModelSerializer(self.collection)
        data = serializer.data
        self.assertIn("id", data)
        self.assertIn("catchment", data)
        self.assertIn("collector", data)
        self.assertIn("collection_system", data)
        self.assertIn("waste_category", data)
        self.assertIn("allowed_materials", data)
        self.assertIn("forbidden_materials", data)
        self.assertIn("frequency", data)
        self.assertIn("valid_from", data)
        self.assertIn("valid_until", data)
        self.assertIn("sources", data)
        self.assertIn("comments", data)

    def test_multiple_sources_in_representation(self):
        serializer = CollectionModelSerializer(self.collection)
        flyer_urls = serializer.data["sources"]
        self.assertIsInstance(flyer_urls, list)
        self.assertEqual(len(flyer_urls), 2)
        for url in flyer_urls:
            self.assertIsInstance(url, str)

    def test_required_bin_capacity_field_serialization(self):
        self.collection.required_bin_capacity = Decimal("120.0")
        self.collection.save()
        serializer = CollectionModelSerializer(self.collection)
        data = serializer.data
        self.assertIn("required_bin_capacity", data)
        self.assertEqual(Decimal(data["required_bin_capacity"]), Decimal("120.0"))
        self.collection.required_bin_capacity = None
        self.collection.save()
        serializer = CollectionModelSerializer(self.collection)
        data = serializer.data
        self.assertIsNone(data["required_bin_capacity"])

    def test_required_bin_capacity_reference_serialization(self):
        for value in ["person", "household", "property", "not_specified", None, ""]:
            self.collection.required_bin_capacity_reference = value
            self.collection.save()
            serializer = CollectionModelSerializer(self.collection)
            data = serializer.data
            if value is None:
                self.assertIsNone(data["required_bin_capacity_reference"])
            elif value == "":
                self.assertIn(data["required_bin_capacity_reference"], [None, ""])
            else:
                self.assertEqual(data["required_bin_capacity_reference"], value)

    def test_connection_type_serialization_handles_none_and_empty_string(self):
        # None case
        self.collection.connection_type = None
        self.collection.save()
        serializer = CollectionModelSerializer(self.collection)
        data = serializer.data
        self.assertIn("connection_type", data)
        self.assertIsNone(data["connection_type"])

        # Empty string case
        self.collection.connection_type = ""
        self.collection.save()
        serializer = CollectionModelSerializer(self.collection)
        data = serializer.data
        self.assertIn("connection_type", data)
        self.assertIn(data["connection_type"], [None, ""])


class CollectionFlatSerializerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        MaterialCategory.objects.create(name="Biowaste component")
        cls.allowed_material_1 = WasteComponent.objects.create(
            name="Allowed Material 1"
        )
        cls.allowed_material_2 = WasteComponent.objects.create(
            name="Allowed Material 2"
        )
        cls.forbidden_material_1 = WasteComponent.objects.create(
            name="Forbidden Material 1"
        )
        cls.forbidden_material_2 = WasteComponent.objects.create(
            name="Forbidden Material 2"
        )
        waste_stream = WasteStream.objects.create(
            name="Test waste stream",
            category=WasteCategory.objects.create(name="Test Category"),
        )
        waste_stream.allowed_materials.add(cls.allowed_material_1)
        waste_stream.allowed_materials.add(cls.allowed_material_2)
        waste_stream.forbidden_materials.add(cls.forbidden_material_1)
        waste_stream.forbidden_materials.add(cls.forbidden_material_2)

        with mute_signals(models.signals.post_save):
            waste_flyer_1 = WasteFlyer.objects.create(
                abbreviation="WasteFlyer123", url="https://www.test-flyer.org"
            )
            waste_flyer_2 = WasteFlyer.objects.create(
                abbreviation="WasteFlyer456", url="https://www.best-flyer.org"
            )
        frequency = CollectionFrequency.objects.create(name="Test Frequency")

        nutsregion = NutsRegion.objects.create(
            name="Hamburg", country="DE", nuts_id="DE600"
        )
        population = Attribute.objects.create(name="Population", unit="")
        population_density = Attribute.objects.create(
            name="Population density", unit="1/km"
        )
        RegionAttributeValue(region=nutsregion, attribute=population, value=123321)
        RegionAttributeValue(
            region=nutsregion, attribute=population_density, value=123.5
        )
        catchment1 = CollectionCatchment.objects.create(
            name="Test Catchment", region=nutsregion.region_ptr
        )
        cls.collection_nuts = Collection.objects.create(
            name="Test Collection Nuts",
            catchment=catchment1,
            collector=Collector.objects.create(name="Test Collector"),
            collection_system=CollectionSystem.objects.create(name="Test System"),
            waste_stream=waste_stream,
            fee_system=FeeSystem.objects.create(name="Test fee system"),
            frequency=frequency,
            valid_from=date(2020, 1, 1),
            description="This is a test case.",
        )
        cls.collection_nuts.flyers.add(waste_flyer_1)
        cls.collection_nuts.flyers.add(waste_flyer_2)

        lauregion = LauRegion.objects.create(
            name="Shetland Islands", country="UK", lau_id="S30000041"
        )
        catchment2 = CollectionCatchment.objects.create(
            name="Test Catchment", region=lauregion.region_ptr
        )
        cls.collection_lau = Collection.objects.create(
            name="Test Collection Lau",
            catchment=catchment2,
            collector=Collector.objects.create(name="Test Collector"),
            collection_system=CollectionSystem.objects.create(name="Test System"),
            waste_stream=waste_stream,
            fee_system=FeeSystem.objects.create(
                name="Fixed fee",
            ),
            frequency=frequency,
            description="This is a test case.",
        )
        cls.collection_lau.flyers.add(waste_flyer_1)
        cls.collection_lau.flyers.add(waste_flyer_2)

    def test_serializer_data_contains_all_fields(self):
        serializer = CollectionFlatSerializer(self.collection_nuts)
        keys = {
            "catchment",
            "nuts_or_lau_id",
            "collector",
            "collection_system",
            "country",
            "waste_category",
            "connection_type",
            "allowed_materials",
            "forbidden_materials",
            "fee_system",
            "frequency",
            "min_bin_size",
            "required_bin_capacity",
            "required_bin_capacity_reference",
            "population",
            "population_density",
            "comments",
            "sources",
            "valid_from",
            "valid_until",
            "created_at",
            "lastmodified_at",
        }
        self.assertSetEqual(keys, set(serializer.data.keys()))

    def test_serializer_gets_information_from_foreign_keys_correctly(self):
        serializer = CollectionFlatSerializer(self.collection_nuts)
        self.assertEqual("Test Catchment", serializer.data["catchment"])
        self.assertEqual("Test Collector", serializer.data["collector"])
        self.assertEqual("Test System", serializer.data["collection_system"])
        self.assertEqual("Test Category", serializer.data["waste_category"])
        self.assertEqual(
            "Allowed Material 1, Allowed Material 2",
            serializer.data["allowed_materials"],
        )
        self.assertEqual(
            "Forbidden Material 1, Forbidden Material 2",
            serializer.data["forbidden_materials"],
        )
        self.assertEqual("Test Frequency", serializer.data["frequency"])
        self.assertEqual(
            "https://www.test-flyer.org, https://www.best-flyer.org",
            serializer.data["sources"],
        )

    def test_nuts_id_is_read_correctly(self):
        serializer = CollectionFlatSerializer(self.collection_nuts)
        self.assertEqual("DE600", serializer.data["nuts_or_lau_id"])

    def test_country_is_read_correctly_from_nutsregion(self):
        serializer = CollectionFlatSerializer(self.collection_nuts)
        self.assertEqual("DE", serializer.data["country"])

    def test_lau_id_is_read_correctly(self):
        serializer = CollectionFlatSerializer(self.collection_lau)
        self.assertEqual("S30000041", serializer.data["nuts_or_lau_id"])

    def test_country_is_read_correctly_from_lauregion(self):
        serializer = CollectionFlatSerializer(self.collection_lau)
        self.assertEqual("UK", serializer.data["country"])

    def test_newline_characters_are_replaced_with_semicolons_in_comments(self):
        self.collection_nuts.description = (
            "This \n contains \r no newline \r\n characters."
        )
        self.collection_nuts.save()
        serializer = CollectionFlatSerializer(self.collection_nuts)
        self.assertNotIn("\n", serializer.data["comments"])
        self.assertNotIn("\r", serializer.data["comments"])
