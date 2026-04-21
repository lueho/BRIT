from datetime import date
from decimal import Decimal

from django.db import models
from django.test import TestCase
from django.urls import reverse
from factory.django import mute_signals

from distributions.models import TemporalDistribution, Timestep
from maps.models import LauRegion, NutsRegion, RegionAttributeValue, RegionProperty
from materials.models import MaterialCategory
from utils.properties.models import Unit

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
)
from ..serializers import (
    CollectionFlatSerializer,
    CollectionFrequencyMutationSerializer,
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
        waste_category = WasteCategory.objects.create(name="Test category")

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
            waste_category=waste_category,
            frequency=frequency,
            valid_from=date(2020, 1, 1),
            description="This is a test case.",
        )
        cls.collection.allowed_materials.set([
            cls.allowed_material_1,
            cls.allowed_material_2,
        ])
        cls.collection.forbidden_materials.set([
            cls.forbidden_material_1,
            cls.forbidden_material_2,
        ])
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

    def test_comments_are_normalized_in_representation(self):
        self.collection.description = "First comment ;; Second comment"
        self.collection.save()

        serializer = CollectionModelSerializer(self.collection)

        self.assertEqual(serializer.data["comments"], "First comment\nSecond comment")

    def test_spaced_legacy_comments_are_normalized_in_representation(self):
        self.collection.description = "First comment ; ; Second comment"
        self.collection.save()

        serializer = CollectionModelSerializer(self.collection)

        self.assertEqual(serializer.data["comments"], "First comment\nSecond comment")

    def test_actions_contains_expected_urls(self):
        serializer = CollectionModelSerializer(self.collection)
        actions = serializer.data["actions"]

        self.assertEqual(
            actions["detail_url"],
            reverse("collection-detail", kwargs={"pk": self.collection.pk}),
        )
        self.assertEqual(
            actions["update_url"],
            reverse("collection-update", kwargs={"pk": self.collection.pk}),
        )
        self.assertEqual(
            actions["copy_url"],
            reverse("collection-copy", kwargs={"pk": self.collection.pk}),
        )
        self.assertEqual(
            actions["delete_url"],
            reverse("collection-delete-modal", kwargs={"pk": self.collection.pk}),
        )

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
        waste_category = WasteCategory.objects.create(name="Test Category")

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
        population = RegionProperty.objects.create(name="Population", unit="")
        population_density = RegionProperty.objects.create(
            name="Population density", unit="1/km"
        )
        RegionAttributeValue.objects.create(
            region=nutsregion.region_ptr,
            property=population,
            date=date(2020, 1, 1),
            value=123321,
        )
        RegionAttributeValue.objects.create(
            region=nutsregion.region_ptr,
            property=population_density,
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
            waste_category=waste_category,
            fee_system=FeeSystem.objects.create(name="Test fee system"),
            frequency=frequency,
            valid_from=date(2020, 1, 1),
            description="This is a test case.",
        )
        cls.collection_nuts.allowed_materials.set([
            cls.allowed_material_1,
            cls.allowed_material_2,
        ])
        cls.collection_nuts.forbidden_materials.set([
            cls.forbidden_material_1,
            cls.forbidden_material_2,
        ])
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
            waste_category=waste_category,
            fee_system=FeeSystem.objects.create(
                name="Fixed fee",
            ),
            frequency=frequency,
            description="This is a test case.",
        )
        cls.collection_lau.allowed_materials.set([
            cls.allowed_material_1,
            cls.allowed_material_2,
        ])
        cls.collection_lau.forbidden_materials.set([
            cls.forbidden_material_1,
            cls.forbidden_material_2,
        ])
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
        self.assertEqual(data["population_2020_unit"], "")
        self.assertIn("population_density_2020", data)
        self.assertEqual(data["population_density_2020"], 123.5)
        self.assertIn("population_density_2020_unit", data)
        self.assertEqual(data["population_density_2020_unit"], "1/km")

    def test_region_attribute_values_export_explicit_value_level_unit_when_present(
        self,
    ):
        explicit_unit = Unit.objects.create(name="1/km²", symbol="1/km²")
        density_value = RegionAttributeValue.objects.get(
            property__name="Population density"
        )
        density_value.unit = explicit_unit
        density_value.save(update_fields=["unit"])

        serializer = CollectionFlatSerializer(self.collection_nuts)
        data = serializer.data

        self.assertEqual(data["population_density_2020_unit"], "1/km²")

    def test_newline_characters_are_replaced_with_semicolons_in_comments(self):
        self.collection_nuts.description = (
            "This \n contains \r no newline \r\n characters."
        )
        self.collection_nuts.save()
        serializer = CollectionFlatSerializer(self.collection_nuts)
        self.assertNotIn("\n", serializer.data["comments"])
        self.assertNotIn("\r", serializer.data["comments"])
        self.assertEqual(
            serializer.data["comments"],
            "This; contains; no newline; characters.",
        )

    def test_legacy_double_semicolons_are_flattened_in_comments(self):
        self.collection_nuts.description = "First comment ;; Second comment"
        self.collection_nuts.save()

        serializer = CollectionFlatSerializer(self.collection_nuts)

        self.assertEqual(serializer.data["comments"], "First comment; Second comment")

    def test_spaced_legacy_semicolons_are_flattened_in_comments(self):
        self.collection_nuts.description = "First comment ; ; Second comment"
        self.collection_nuts.save()

        serializer = CollectionFlatSerializer(self.collection_nuts)

        self.assertEqual(serializer.data["comments"], "First comment; Second comment")


class CollectionImportRecordSerializerTestCase(TestCase):
    def test_required_bin_capacity_field_label(self):
        serializer = CollectionImportRecordSerializer()
        self.assertEqual(
            serializer.fields["required_bin_capacity"].label,
            "Minimum required specific bin capacity (L/reference unit)",
        )

    def test_material_list_fields_are_available_for_bulk_import(self):
        serializer = CollectionImportRecordSerializer()
        self.assertIn("allowed_materials", serializer.fields)
        self.assertIn("forbidden_materials", serializer.fields)
        self.assertIn("review_comment", serializer.fields)


class CollectionFrequencyMutationSerializerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.distribution, _ = TemporalDistribution.objects.get_or_create(
            name="Months of the year"
        )
        cls.timesteps = {
            name: Timestep.objects.get_or_create(
                name=name,
                distribution=cls.distribution,
                defaults={"order": index},
            )[0]
            for index, name in enumerate(
                (
                    "January",
                    "February",
                    "March",
                    "April",
                    "May",
                    "June",
                    "July",
                    "August",
                    "September",
                    "October",
                    "November",
                    "December",
                ),
                start=1,
            )
        }

    def test_accepts_named_schedule_rows_and_derives_counts(self):
        serializer = CollectionFrequencyMutationSerializer(
            data={
                "description": "Nordwestmecklenburg GER seasonal cadence.",
                "rows": [
                    {
                        "distribution": "Months of the year",
                        "first_timestep": "March",
                        "last_timestep": "October",
                        "standard_cadence": "every_two_weeks",
                    },
                    {
                        "distribution": "Months of the year",
                        "first_timestep": "November",
                        "last_timestep": "February",
                        "standard_cadence": "every_four_weeks",
                    },
                ],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

        validated_data = serializer.validated_data
        self.assertEqual(validated_data["frequency_type"], "Seasonal")
        self.assertEqual(
            validated_data["canonical_name"],
            "Seasonal; 1 per 2 weeks from March-October; 1 per 4 weeks from November-February",
        )
        self.assertEqual(validated_data["rows"][0]["distribution"], self.distribution)
        self.assertEqual(
            validated_data["rows"][0]["first_timestep"], self.timesteps["March"]
        )
        self.assertEqual(
            validated_data["rows"][1]["last_timestep"], self.timesteps["February"]
        )
        self.assertEqual(validated_data["rows"][0]["standard"], 17)
        self.assertEqual(validated_data["rows"][1]["standard"], 4)
