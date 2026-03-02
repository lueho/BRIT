from datetime import date
from decimal import Decimal

from django.db import models
from django.test import TestCase
from factory.django import mute_signals

from maps.models import Attribute, LauRegion, NutsRegion, RegionAttributeValue
from materials.models import MaterialCategory

from ..models import (
    REQUIRED_BIN_CAPACITY_REFERENCE_CHOICES,
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
from ..serializers import (
    CollectionFlatSerializer,
    CollectionImportRecordSerializer,
    CollectionModelSerializer,
)


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

    def test_required_bin_capacity_field_label(self):
        serializer = CollectionModelSerializer(self.collection)
        self.assertEqual(
            serializer.fields["required_bin_capacity"].label,
            "Minimum required specific bin capacity (L/reference unit)",
        )

    def test_required_bin_capacity_reference_serialization(self):
        choices = dict(REQUIRED_BIN_CAPACITY_REFERENCE_CHOICES)
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
                expected = choices.get(value, value)
                self.assertEqual(data["required_bin_capacity_reference"], expected)

    def test_serializer_method_fields_have_matching_methods(self):
        serializer = CollectionModelSerializer(self.collection)
        serializer_method_fields = {
            name: field
            for name, field in serializer.fields.items()
            if field.__class__.__name__ == "SerializerMethodField"
        }
        for field_name, field in serializer_method_fields.items():
            method_name = getattr(field, "method_name", f"get_{field_name}")
            self.assertTrue(
                hasattr(serializer, method_name),
                msg=(
                    f"SerializerMethodField '{field_name}' is missing its method "
                    f"'{method_name}' on {serializer.__class__.__name__}"
                ),
            )

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
        RegionAttributeValue.objects.create(
            region=nutsregion.region_ptr,
            attribute=population,
            date=date(2020, 1, 1),
            value=123321,
        )
        RegionAttributeValue.objects.create(
            region=nutsregion.region_ptr,
            attribute=population_density,
            date=date(2020, 1, 1),
            value=123.5,
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
        static_keys = {
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
            "comments",
            "flyer_urls",
            "bibliography_sources",
            "valid_from",
            "valid_until",
            "created_at",
            "lastmodified_at",
        }
        self.assertTrue(static_keys.issubset(set(serializer.data.keys())))

    def test_required_bin_capacity_field_label(self):
        serializer = CollectionFlatSerializer(self.collection_nuts)
        self.assertEqual(
            serializer.fields["required_bin_capacity"].label,
            "Minimum required specific bin capacity (L/reference unit)",
        )

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
            serializer.data["flyer_urls"],
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

    def test_region_attribute_values_exported_as_dynamic_columns(self):
        serializer = CollectionFlatSerializer(self.collection_nuts)
        data = serializer.data
        self.assertIn("population_2020", data)
        self.assertEqual(data["population_2020"], 123321)
        self.assertIn("population_2020_unit", data)
        self.assertIn("population_density_2020", data)
        self.assertEqual(data["population_density_2020"], 123.5)
        self.assertIn("population_density_2020_unit", data)
        self.assertEqual(data["population_density_2020_unit"], "1/km")

    def test_newline_characters_are_replaced_with_semicolons_in_comments(self):
        self.collection_nuts.description = (
            "This \n contains \r no newline \r\n characters."
        )
        self.collection_nuts.save()
        serializer = CollectionFlatSerializer(self.collection_nuts)
        self.assertNotIn("\n", serializer.data["comments"])
        self.assertNotIn("\r", serializer.data["comments"])


class CollectionFlatSerializerChainAwareStatsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        waste_stream = WasteStream.objects.create(
            name="WS",
            category=WasteCategory.objects.create(name="Cat"),
        )
        frequency = CollectionFrequency.objects.create(name="F")
        nuts = NutsRegion.objects.create(name="Hamburg", country="DE", nuts_id="DE600")
        cls.collection_root = Collection.objects.create(
            name="C0",
            catchment=CollectionCatchment.objects.create(
                name="Catch", region=nuts.region_ptr
            ),
            collector=Collector.objects.create(name="Col"),
            collection_system=CollectionSystem.objects.create(name="Sys"),
            waste_stream=waste_stream,
            frequency=frequency,
            valid_from=date(2020, 1, 1),
            publication_status="published",
        )
        cls.collection_succ = Collection.objects.create(
            name="C1",
            catchment=cls.collection_root.catchment,
            collector=Collector.objects.create(name="Col2"),
            collection_system=CollectionSystem.objects.create(name="Sys2"),
            waste_stream=waste_stream,
            frequency=frequency,
            valid_from=date(2021, 1, 1),
            publication_status="published",
        )
        cls.collection_succ.predecessors.add(cls.collection_root)

        from utils.properties.models import Property, Unit

        cls.prop_specific = Property.objects.create(
            name="specific waste collected", publication_status="published"
        )
        cls.prop_conn = Property.objects.create(
            name="Connection rate", publication_status="published"
        )
        cls.unit = Unit.objects.create(name="u", publication_status="published")
        cls.prop_specific.allowed_units.add(cls.unit)
        cls.prop_conn.allowed_units.add(cls.unit)

        from case_studies.soilcom.models import (
            AggregatedCollectionPropertyValue,
            CollectionPropertyValue,
        )

        CollectionPropertyValue.objects.create(
            collection=cls.collection_succ,
            property=cls.prop_specific,
            unit=cls.unit,
            year=2022,
            average=12.5,
            publication_status="published",
        )

        agg = AggregatedCollectionPropertyValue.objects.create(
            property=cls.prop_conn,
            unit=cls.unit,
            year=2021,
            average=88.1,
            publication_status="published",
        )
        agg.collections.add(cls.collection_root)

    def test_dynamic_columns_include_chain_aware_values(self):
        serializer = CollectionFlatSerializer(self.collection_succ)
        data = serializer.data

        self.assertIn("specific_waste_collected_2022", data)
        self.assertEqual(data["specific_waste_collected_2022"], 12.5)
        self.assertIn("specific_waste_collected_2022_unit", data)
        self.assertEqual(data["specific_waste_collected_2022_unit"], str(self.unit))

        self.assertIn("connection_rate_2021", data)
        self.assertEqual(data["connection_rate_2021"], 88.1)
        self.assertIn("connection_rate_2021_unit", data)
        self.assertEqual(data["connection_rate_2021_unit"], str(self.unit))

        self.assertTrue(data.get("aggregated", False))


class CollectionImportRecordSerializerTestCase(TestCase):
    def test_required_bin_capacity_field_label(self):
        serializer = CollectionImportRecordSerializer()
        self.assertEqual(
            serializer.fields["required_bin_capacity"].label,
            "Minimum required specific bin capacity (L/reference unit)",
        )
