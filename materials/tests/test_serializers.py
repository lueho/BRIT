from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db.models.signals import post_save
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from factory.django import mute_signals

from bibliography.models import Source
from distributions.models import Timestep
from utils.object_management.models import ObjectEditorGrant
from utils.properties.models import Unit

from ..models import (
    ComponentMeasurement,
    Composition,
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialProperty,
    MaterialPropertyValue,
    MeasurementValueQualifier,
    Sample,
    SampleGroup,
    SampleSeries,
)
from ..serializers import (
    ComponentMeasurementReadSerializer,
    ComponentMeasurementWriteSerializer,
    CompositionDoughnutChartSerializer,
    CompositionModelSerializer,
    MaterialPropertyAPISerializer,
    MaterialPropertyValueModelSerializer,
    MaterialPropertyValueReadSerializer,
    SampleAPISerializer,
    SampleFlatSerializer,
    SampleGroupAPISerializer,
    SampleGroupWriteSerializer,
    SampleModelSerializer,
    SampleSeriesModelSerializer,
    SampleWriteSerializer,
)


class ComponentMeasurementWriteSerializerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sample = Sample.objects.create(
            name="Sample", material=Material.objects.create(name="Material")
        )
        cls.group = MaterialComponentGroup.objects.create(name="Group")
        cls.component = MaterialComponent.objects.create(name="Carbon")

    def _data(self, unit):
        return {
            "sample": self.sample.pk,
            "group": self.group.pk,
            "component": self.component.pk,
            "unit": unit.pk,
            "average": "12.0",
        }

    def test_rejects_units_that_are_not_weight_fractions(self):
        serializer = ComponentMeasurementWriteSerializer(
            data=self._data(Unit.objects.create(name="mg/L", symbol="mg/L"))
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("unit", serializer.errors)

    def test_rejects_volume_percent(self):
        unit, _ = Unit.objects.update_or_create(
            name="vol.-%", defaults={"symbol": "volume_percent"}
        )
        serializer = ComponentMeasurementWriteSerializer(data=self._data(unit))
        self.assertFalse(serializer.is_valid())
        self.assertIn("unit", serializer.errors)

    def test_accepts_weight_fraction_units(self):
        serializer = ComponentMeasurementWriteSerializer(
            data=self._data(Unit.objects.create(name="g/kg", symbol="g/kg"))
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)


class MaterialPropertySerializerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        prop = MaterialProperty.objects.create(name="Test Property")
        basis = MaterialComponent.objects.create(name="Dry Matter")
        unit = Unit.objects.create(name="mg/kg")
        MaterialPropertyValue.objects.create(
            property=prop,
            basis_component=basis,
            unit=unit,
            average=Decimal("123.321"),
            standard_deviation=Decimal("0.1337"),
        )

    def setUp(self):
        self.value = MaterialPropertyValue.objects.get(
            standard_deviation=Decimal("0.1337")
        )

    def test_serializer(self):
        request = RequestFactory().get(reverse("home"))
        data = MaterialPropertyValueModelSerializer(
            self.value, context={"request": request}
        ).data
        self.assertIn("id", data)
        self.assertIn("property_name", data)
        self.assertIn("property_url", data)
        self.assertIn("basis_component", data)
        self.assertIn("average", data)
        self.assertIn("standard_deviation", data)
        self.assertIn("unit", data)
        self.assertEqual(data["basis_component"], self.value.basis_component.name)
        self.assertEqual(data["unit"], self.value.unit.name)


class SampleSeriesModelSerializerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        material = Material.objects.create(name="Test Material")
        SampleSeries.objects.create(name="Test Series", material=material)

    def setUp(self):
        self.series = SampleSeries.objects.get(name="Test Series")

    def test_serializer_construction(self):
        data = SampleSeriesModelSerializer(self.series).data
        self.assertIn("id", data)
        self.assertIn("name", data)
        self.assertIn("distributions", data)


class SampleDatetimePrecisionSerializerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.material = Material.objects.create(name="Precision material")
        cls.sample = Sample.objects.create(
            name="Precision sample",
            material=cls.material,
            datetime=datetime(2024, 8, 27, tzinfo=ZoneInfo("Europe/Berlin")),
        )

    def test_read_serializers_expose_stored_precision_including_legacy_blank(self):
        request = RequestFactory().get(reverse("home"))
        for precision in ("", "year", "date", "time"):
            self.sample.datetime_precision = precision
            for serializer_class in (
                SampleModelSerializer,
                SampleFlatSerializer,
                SampleWriteSerializer,
            ):
                with self.subTest(precision=precision, serializer=serializer_class):
                    data = serializer_class(
                        self.sample, context={"request": request}
                    ).data
                    self.assertEqual(data["datetime_precision"], precision)
                    self.assertIsNotNone(data["datetime"])

    def test_create_preserves_explicit_precision_and_timestamp(self):
        for precision in ("year", "date", "time"):
            with self.subTest(precision=precision):
                serializer = SampleWriteSerializer(
                    data={
                        "name": "New sample",
                        "material": self.material.pk,
                        "datetime": "2024-08-27T00:00:00+02:00",
                        "datetime_precision": precision,
                    }
                )
                self.assertTrue(serializer.is_valid(), serializer.errors)
                sample = serializer.save()
                sample.refresh_from_db()
                self.assertEqual(sample.datetime_precision, precision)
                self.assertEqual(sample.datetime, self.sample.datetime)

    @override_settings(TIME_ZONE="UTC", USE_TZ=True)
    def test_offset_year_boundary_preserves_instant_and_uses_server_calendar(self):
        original = "2024-01-01T00:00:00+02:00"
        with timezone.override("Asia/Tokyo"):
            serializer = SampleWriteSerializer(
                data={
                    "name": "Year boundary",
                    "material": self.material.pk,
                    "datetime": original,
                    "datetime_precision": "year",
                }
            )
            self.assertTrue(serializer.is_valid(), serializer.errors)
            sample = serializer.save()
            sample.refresh_from_db()
            self.assertEqual(sample.datetime, datetime.fromisoformat(original))
            self.assertEqual(sample.datetime_precision, "year")
            self.assertEqual(sample.sampling_date_input, "2023")
            self.assertEqual(sample.sampling_date_display, "2023")

    def test_create_without_precision_remains_legacy(self):
        for value in (None, "2024-08-27T00:00:00+02:00", "2024-08-27T14:30:00+02:00"):
            with self.subTest(value=value):
                serializer = SampleWriteSerializer(
                    data={
                        "name": "Legacy",
                        "material": self.material.pk,
                        "datetime": value,
                    }
                )
                self.assertTrue(serializer.is_valid(), serializer.errors)
                sample = serializer.save()
                sample.refresh_from_db()
                self.assertEqual(sample.datetime_precision, "")

    def test_create_rejects_precision_without_datetime(self):
        for precision in ("year", "date", "time"):
            for datetime_data in ({}, {"datetime": None}):
                with self.subTest(precision=precision, datetime_data=datetime_data):
                    serializer = SampleWriteSerializer(
                        data={
                            "name": "Invalid",
                            "material": self.material.pk,
                            "datetime_precision": precision,
                            **datetime_data,
                        }
                    )
                    self.assertFalse(serializer.is_valid())
                    self.assertIn("datetime_precision", serializer.errors)

    def test_invalid_precision_is_rejected(self):
        serializer = SampleWriteSerializer(
            self.sample, data={"datetime_precision": "month"}, partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("datetime_precision", serializer.errors)

    def test_partial_precision_update_uses_existing_datetime(self):
        original_datetime = self.sample.datetime
        serializer = SampleWriteSerializer(
            self.sample, data={"datetime_precision": "time"}, partial=True
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        sample = serializer.save()
        sample.refresh_from_db()
        self.assertEqual(sample.datetime_precision, "time")
        self.assertEqual(sample.datetime, original_datetime)

    def test_partial_precision_update_rejects_missing_existing_datetime(self):
        self.sample.datetime = None
        serializer = SampleWriteSerializer(
            self.sample, data={"datetime_precision": "year"}, partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("datetime_precision", serializer.errors)

    def test_partial_update_preserves_omitted_precision(self):
        for precision in ("", "year", "date", "time"):
            with self.subTest(precision=precision):
                self.sample.datetime_precision = precision
                serializer = SampleWriteSerializer(
                    self.sample,
                    data={"datetime": "2024-08-27T14:30:12.123456+02:00"},
                    partial=True,
                )
                self.assertTrue(serializer.is_valid(), serializer.errors)
                sample = serializer.save()
                sample.refresh_from_db()
                self.assertEqual(sample.datetime_precision, precision)
                self.assertEqual(sample.datetime.microsecond, 123456)

    def test_clearing_datetime_requires_clearing_explicit_precision(self):
        self.sample.datetime_precision = "date"
        serializer = SampleWriteSerializer(
            self.sample, data={"datetime": None}, partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("datetime_precision", serializer.errors)
        serializer = SampleWriteSerializer(
            self.sample, data={"datetime": None, "datetime_precision": ""}, partial=True
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        sample = serializer.save()
        sample.refresh_from_db()
        self.assertIsNone(sample.datetime)
        self.assertEqual(sample.datetime_precision, "")


class SampleSerializerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="sample-serializer-owner",
            password="test123",
        )
        material = Material.objects.create(
            name="Test Material",
            owner=cls.owner,
        )
        series = SampleSeries.objects.create(
            name="Test Series",
            material=material,
            owner=cls.owner,
        )
        sample = Sample.objects.create(
            name="Test Sample",
            material=material,
            series=series,
            timestep=Timestep.objects.default(),
            owner=cls.owner,
        )
        with mute_signals(post_save):
            source = Source.objects.create(title="Test Source")
        sample.sources.add(source)
        property_obj = MaterialProperty.objects.create(
            name="Dry Matter",
            owner=cls.owner,
        )
        unit = Unit.objects.create(name="Percent")
        MaterialPropertyValue.objects.create(
            sample=sample,
            property=property_obj,
            unit=unit,
            average=Decimal("42.0"),
            standard_deviation=Decimal("1.5"),
            owner=cls.owner,
        )

    def setUp(self):
        self.sample = Sample.objects.get(name="Test Sample")

    def test_serializer_construction(self):
        request = RequestFactory().get(
            reverse("sample-detail", kwargs={"pk": self.sample.id})
        )
        data = SampleModelSerializer(self.sample, context={"request": request}).data
        self.assertIn("name", data)
        self.assertEqual(data["name"], "Test Sample")
        self.assertIn("material_name", data)
        self.assertEqual(data["material_name"], "Test Material")
        self.assertIn("material_url", data)
        self.assertIn("series_name", data)
        self.assertEqual(data["series_name"], "Test Series")
        self.assertIn("series_url", data)
        self.assertIn("timestep", data)
        self.assertIn("datetime", data)
        self.assertIn("image", data)
        self.assertIn("compositions", data)
        self.assertIn("properties", data)
        self.assertIn("sources", data)

    def test_serializer_includes_sample_owned_property_values(self):
        request = RequestFactory().get(
            reverse("sample-detail", kwargs={"pk": self.sample.id})
        )
        data = SampleModelSerializer(self.sample, context={"request": request}).data

        self.assertEqual(len(data["properties"]), 1)
        self.assertEqual(
            data["properties"][0]["property_name"],
            "Dry Matter",
        )

    def test_properties_prefetches_sources(self):
        request = RequestFactory().get(
            reverse("sample-detail", kwargs={"pk": self.sample.id})
        )
        first_value = self.sample.property_values.get(property__name="Dry Matter")
        with mute_signals(post_save):
            first_source = Source.objects.create(
                title="First Property Source",
                citation_key="FPS",
            )
            second_source = Source.objects.create(
                title="Second Property Source",
                citation_key="SPS",
            )
        first_value.sources.add(first_source)
        second_property = MaterialProperty.objects.create(
            name="Ash",
            owner=self.owner,
        )
        second_value = MaterialPropertyValue.objects.create(
            sample=self.sample,
            property=second_property,
            unit=first_value.unit,
            average=Decimal("10.0"),
            owner=self.owner,
        )
        second_value.sources.add(second_source)

        serializer = SampleModelSerializer(context={"request": request})
        with self.assertNumQueries(2):
            data = serializer.get_properties(self.sample)

        self.assertEqual(len(data), 2)
        self.assertEqual(
            {source["citation_key"] for prop in data for source in prop["sources"]},
            {"FPS", "SPS"},
        )

    def test_serializer_uses_shared_normalized_compositions(self):
        self.sample.compositions.all().delete()
        unit = Unit.objects.filter(name="%").first()
        if unit is None:
            unit = Unit.objects.create(name="%", symbol="percent")
        elif not unit.symbol:
            unit.symbol = "percent"
            unit.save(update_fields=["symbol"])

        group = MaterialComponentGroup.objects.create(
            name="Chemical Elements",
            owner=self.owner,
        )
        carbon = MaterialComponent.objects.create(name="Carbon", owner=self.owner)
        nitrogen = MaterialComponent.objects.create(
            name="Nitrogen",
            owner=self.owner,
        )
        ComponentMeasurement.objects.create(
            sample=self.sample,
            group=group,
            component=carbon,
            unit=unit,
            average=Decimal("30"),
            owner=self.owner,
        )
        ComponentMeasurement.objects.create(
            sample=self.sample,
            group=group,
            component=nitrogen,
            unit=unit,
            average=Decimal("70"),
            owner=self.owner,
        )

        request = RequestFactory().get(
            reverse("sample-detail", kwargs={"pk": self.sample.id})
        )
        data = SampleModelSerializer(self.sample, context={"request": request}).data

        self.assertEqual(len(data["compositions"]), 1)
        composition = data["compositions"][0]
        self.assertTrue(composition["is_derived"])
        self.assertEqual(composition["origin"], "raw_derived")
        self.assertEqual(
            {share["as_percentage"] for share in composition["shares"]},
            {"30.0%", "70.0%"},
        )


class CompositionSerializerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        material = Material.objects.create(name="Test Material")
        series = SampleSeries.objects.create(name="Test Series", material=material)
        sample = Sample.objects.create(
            name="Test Sample",
            material=material,
            series=series,
            timestep=Timestep.objects.default(),
        )
        group = MaterialComponentGroup.objects.create(name="Test Group")
        cls.composition = Composition.objects.create(
            group=group, sample=sample, fractions_of=MaterialComponent.objects.default()
        )
        unit = Unit.objects.filter(name="%").first() or Unit.objects.create(
            name="%", symbol="percent"
        )
        ComponentMeasurement.objects.create(
            sample=sample,
            group=group,
            component=MaterialComponent.objects.create(name="Test Component"),
            unit=unit,
            average=Decimal("40"),
        )

    def test_serializer_construction(self):
        data = CompositionModelSerializer(self.composition).data
        self.assertIn("group", data)
        self.assertIn("group_name", data)
        self.assertIn("sample", data)
        self.assertIn("fractions_of", data)
        self.assertIn("fractions_of_name", data)
        self.assertIn("shares", data)

    def test_serializer_uses_raw_normalized_composition(self):
        data = CompositionModelSerializer(self.composition).data

        self.assertEqual(
            data["shares"][-1]["component"], MaterialComponent.objects.other().pk
        )
        self.assertEqual(data["shares"][-1]["as_percentage"], "60.0%")


class CompositionDoughnutChartSerializerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        material = Material.objects.create(name="Test Material")
        series = SampleSeries.objects.create(name="Test Series", material=material)
        sample = Sample.objects.create(
            name="Test Sample", material=material, series=series
        )
        group = MaterialComponentGroup.objects.create(name="Test Group")
        cls.composition = Composition.objects.create(
            sample=sample, group=group, fractions_of=MaterialComponent.objects.default()
        )
        component1 = MaterialComponent.objects.create(name="Test Component 1")
        component2 = MaterialComponent.objects.create(name="Test Component 2")
        unit = Unit.objects.filter(name="%").first() or Unit.objects.create(
            name="%", symbol="percent"
        )
        ComponentMeasurement.objects.create(
            sample=sample,
            group=group,
            component=MaterialComponent.objects.other(),
            unit=unit,
            average=Decimal("70"),
        )
        ComponentMeasurement.objects.create(
            sample=sample,
            group=group,
            component=component1,
            unit=unit,
            average=Decimal("10"),
        )
        ComponentMeasurement.objects.create(
            sample=sample,
            group=group,
            component=component2,
            unit=unit,
            average=Decimal("20"),
        )

    def test_serializer_returns_correct_data(self):
        data = CompositionDoughnutChartSerializer(self.composition).data
        self.assertIn("id", data)
        self.assertIn("title", data)
        self.assertIn("unit", data)
        self.assertIn("labels", data)
        self.assertIsInstance(data["labels"], list)
        self.assertListEqual(
            data["labels"], ["Test Component 2", "Test Component 1", "Other"]
        )
        self.assertIn("data", data)
        self.assertIsInstance(data["data"], list)
        self.assertIsInstance(data["data"][0]["data"], list)
        self.assertListEqual(data["data"][0]["data"], [0.2, 0.1, 0.7])


class MeasurementQualifierSerializerTestCase(TestCase):
    METADATA_FIELDS = (
        "display_value",
        "value_qualifier",
        "raw_value",
        "detection_limit",
        "raw_detection_limit",
    )

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="qualifier-serializer-owner", password="test123"
        )
        cls.material = Material.objects.create(
            name="Qualifier material", owner=cls.owner
        )
        cls.sample = Sample.objects.create(
            name="Qualifier sample", material=cls.material, owner=cls.owner
        )
        cls.group = MaterialComponentGroup.objects.create(
            name="Qualifier group", owner=cls.owner
        )
        cls.component = MaterialComponent.objects.create(
            name="Qualifier component", owner=cls.owner
        )
        cls.prop = MaterialProperty.objects.create(
            name="Qualifier property", owner=cls.owner
        )
        cls.unit = Unit.objects.filter(name="%").first() or Unit.objects.create(
            name="%", symbol="percent", owner=cls.owner
        )
        cls.measurement = ComponentMeasurement.objects.create(
            owner=cls.owner,
            sample=cls.sample,
            group=cls.group,
            component=cls.component,
            unit=cls.unit,
            average=Decimal("0.1"),
            raw_value="0.1",
            value_qualifier=MeasurementValueQualifier.LESS_THAN,
            detection_limit=Decimal("6.57"),
            raw_detection_limit="6,57",
        )
        cls.property_value = MaterialPropertyValue.objects.create(
            owner=cls.owner,
            sample=cls.sample,
            property=cls.prop,
            unit=cls.unit,
            average=Decimal("0.1"),
            raw_value="0.1",
            value_qualifier=MeasurementValueQualifier.LESS_THAN,
            detection_limit=Decimal("6.57"),
            raw_detection_limit="6,57",
        )

    def _assert_metadata(self, data):
        for field in self.METADATA_FIELDS:
            self.assertIn(field, data)
        self.assertEqual(data["display_value"], "<0.1")
        self.assertEqual(Decimal(str(data["average"])), Decimal("0.1"))
        self.assertEqual(data["value_qualifier"], "less_than")
        self.assertEqual(data["raw_value"], "0.1")
        self.assertEqual(Decimal(str(data["detection_limit"])), Decimal("6.57"))
        self.assertEqual(data["raw_detection_limit"], "6,57")

    def test_component_measurement_read_serializer_includes_qualifier_metadata(self):
        data = ComponentMeasurementReadSerializer(self.measurement).data

        self._assert_metadata(data)

    def test_property_value_read_serializer_includes_qualifier_metadata(self):
        data = MaterialPropertyValueReadSerializer(self.property_value).data

        self._assert_metadata(data)

    def test_property_value_model_serializer_includes_qualifier_metadata(self):
        request = RequestFactory().get(reverse("home"))
        data = MaterialPropertyValueModelSerializer(
            self.property_value, context={"request": request}
        ).data

        self.assertIn("property_url", data)
        self._assert_metadata(data)

    def test_property_api_serializer_includes_qualifier_metadata(self):
        data = MaterialPropertyAPISerializer(self.property_value).data

        self._assert_metadata(data)

    def test_sample_model_serializer_includes_metadata_in_nested_properties(self):
        request = RequestFactory().get(
            reverse("sample-detail", kwargs={"pk": self.sample.pk})
        )
        data = SampleModelSerializer(self.sample, context={"request": request}).data

        self.assertEqual(len(data["properties"]), 1)
        self._assert_metadata(data["properties"][0])

    def test_sample_api_serializer_includes_metadata_in_nested_properties(self):
        data = SampleAPISerializer(self.sample).data

        self.assertEqual(len(data["properties"]), 1)
        self._assert_metadata(data["properties"][0])

    def test_exact_zero_display_value_stays_numeric(self):
        value = MaterialPropertyValue.objects.create(
            owner=self.owner,
            sample=self.sample,
            property=self.prop,
            unit=self.unit,
            average=Decimal("0"),
        )

        data = MaterialPropertyValueReadSerializer(value).data

        self.assertEqual(data["display_value"], Decimal("0"))
        self.assertEqual(Decimal(str(data["average"])), Decimal("0"))
        self.assertEqual(data["value_qualifier"], "exact")
        self.assertEqual(data["raw_value"], "")
        self.assertIsNone(data["detection_limit"])
        self.assertEqual(data["raw_detection_limit"], "")

    def test_below_detection_limit_without_limit(self):
        measurement = ComponentMeasurement.objects.create(
            owner=self.owner,
            sample=self.sample,
            group=self.group,
            component=self.component,
            unit=self.unit,
            average=Decimal("0"),
            value_qualifier=MeasurementValueQualifier.BELOW_DETECTION_LIMIT,
        )

        data = ComponentMeasurementReadSerializer(measurement).data

        self.assertEqual(data["display_value"], "Below detection limit")
        self.assertIsNone(data["detection_limit"])
        self.assertEqual(data["raw_detection_limit"], "")

    def test_hostile_raw_value_serializes_as_text(self):
        raw = '<img src=x onerror="alert(31337)">'
        measurement = ComponentMeasurement.objects.create(
            owner=self.owner,
            sample=self.sample,
            group=self.group,
            component=self.component,
            unit=self.unit,
            average=Decimal("0.1"),
            raw_value=raw,
            value_qualifier=MeasurementValueQualifier.LESS_THAN,
        )

        data = ComponentMeasurementReadSerializer(measurement).data

        self.assertEqual(data["raw_value"], raw)
        self.assertEqual(data["display_value"], raw)
        self.assertIsInstance(data["display_value"], str)


class SampleGroupAPISerializerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="group-serializer-owner"
        )
        cls.material = Material.objects.create(name="Grouped material", owner=cls.owner)
        cls.sample = Sample.objects.create(
            name="Member sample",
            material=cls.material,
            timestep=Timestep.objects.default(),
            owner=cls.owner,
            publication_status="published",
        )
        cls.group = SampleGroup.objects.create(
            name="Serializer group",
            kind="experiment",
            description="A test group",
            owner=cls.owner,
        )
        cls.sample.sample_groups.add(cls.group)
        with mute_signals(post_save):
            cls.source = Source.objects.create(
                title="Group source",
                owner=cls.owner,
                publication_status="published",
            )
        cls.group.sources.add(cls.source)
        cls.other = get_user_model().objects.create_user(
            username="group-serializer-other"
        )

    def _request(self, user=None):
        request = RequestFactory().get("/")
        request.user = user if user is not None else AnonymousUser()
        return request

    def _add_private_relations(self):
        private_sample = Sample.objects.create(
            name="Private member sample",
            material=self.material,
            owner=self.owner,
            publication_status="private",
        )
        private_sample.sample_groups.add(self.group)
        with mute_signals(post_save):
            private_source = Source.objects.create(
                title="Private group source",
                owner=self.owner,
                publication_status="private",
            )
        self.group.sources.add(private_source)
        return private_sample, private_source

    def test_read_shape(self):
        data = SampleGroupAPISerializer(self.group).data

        self.assertEqual(
            set(data.keys()),
            {"id", "name", "kind", "description", "sources", "samples"},
        )
        self.assertEqual(data["kind"], "experiment")
        self.assertEqual(len(data["samples"]), 1)
        self.assertEqual(
            set(data["samples"][0].keys()),
            {"id", "name", "material", "timestep"},
        )
        self.assertEqual(data["samples"][0]["material"], "Grouped material")

    def test_no_request_returns_only_published_relations(self):
        private_sample, private_source = self._add_private_relations()

        data = SampleGroupAPISerializer(self.group).data

        self.assertEqual(
            [sample["name"] for sample in data["samples"]], ["Member sample"]
        )
        self.assertNotIn(private_sample.name, str(data["samples"]))
        self.assertNotIn(private_source.title, str(data["sources"]))

    def test_anonymous_request_hides_private_relations(self):
        private_sample, private_source = self._add_private_relations()

        data = SampleGroupAPISerializer(
            self.group, context={"request": self._request()}
        ).data

        self.assertNotIn(private_sample.name, str(data["samples"]))
        self.assertNotIn(private_source.title, str(data["sources"]))

    def test_owner_request_sees_private_relations(self):
        private_sample, private_source = self._add_private_relations()

        data = SampleGroupAPISerializer(
            self.group, context={"request": self._request(self.owner)}
        ).data

        self.assertIn(private_sample.name, str(data["samples"]))
        self.assertEqual(len(data["sources"]), 2)

    def test_write_fields(self):
        self.assertEqual(
            list(SampleGroupWriteSerializer.Meta.fields),
            ["id", "name", "kind", "description", "sources", "samples"],
        )

    def test_write_roundtrip(self):
        serializer = SampleGroupWriteSerializer(
            data={"name": "New group", "kind": "analysis", "description": ""}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        group = serializer.save(owner=self.owner)

        self.assertEqual(group.kind, "analysis")
        self.assertFalse(group.samples.exists())

    def test_write_sets_members_and_sources(self):
        serializer = SampleGroupWriteSerializer(
            data={
                "name": "Group with members",
                "kind": "study",
                "samples": [self.sample.pk],
                "sources": [self.source.pk],
            },
            context={"request": self._request(self.owner)},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        group = serializer.save(owner=self.owner)

        self.assertCountEqual(group.samples.all(), [self.sample])
        self.assertCountEqual(group.sources.all(), [self.source])

    def test_write_rejects_inaccessible_private_sample(self):
        foreign_sample = Sample.objects.create(
            name="Foreign sample",
            material=self.material,
            owner=self.other,
            publication_status="private",
        )
        serializer = SampleGroupWriteSerializer(
            data={
                "name": "Bad group",
                "kind": "study",
                "samples": [foreign_sample.pk],
            },
            context={"request": self._request(self.owner)},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("samples", serializer.errors)

    def test_write_rejects_visible_but_not_editable_sample(self):
        foreign_sample = Sample.objects.create(
            name="Foreign published sample",
            material=self.material,
            owner=self.other,
            publication_status="published",
        )
        serializer = SampleGroupWriteSerializer(
            data={
                "name": "Bad group",
                "kind": "study",
                "samples": [foreign_sample.pk],
            },
            context={"request": self._request(self.owner)},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("samples", serializer.errors)

    def test_write_update_preserves_members_editor_cannot_manage(self):
        foreign_sample = Sample.objects.create(
            name="Foreign published sample",
            material=self.material,
            owner=self.other,
            publication_status="published",
        )
        own_sample = Sample.objects.create(
            name="Own sample", material=self.material, owner=self.owner
        )
        foreign_sample.sample_groups.add(self.group)
        serializer = SampleGroupWriteSerializer(
            instance=self.group,
            data={"samples": [own_sample.pk]},
            partial=True,
            context={"request": self._request(self.owner)},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.assertCountEqual(self.group.samples.all(), [own_sample, foreign_sample])

    def test_write_rejects_inaccessible_private_source(self):
        with mute_signals(post_save):
            foreign_source = Source.objects.create(
                title="Foreign source",
                owner=self.other,
                publication_status="private",
            )
        serializer = SampleGroupWriteSerializer(
            data={
                "name": "Bad group",
                "kind": "study",
                "sources": [foreign_source.pk],
            },
            context={"request": self._request(self.owner)},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("sources", serializer.errors)


class SampleGroupMembershipSerializerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="membership-owner")
        cls.other = get_user_model().objects.create_user(username="membership-other")
        cls.material = Material.objects.create(
            name="Membership material", owner=cls.owner
        )
        cls.sample = Sample.objects.create(
            name="Membership sample", material=cls.material, owner=cls.owner
        )
        cls.group = SampleGroup.objects.create(
            name="Accessible group",
            kind="study",
            owner=cls.owner,
            publication_status="published",
        )
        cls.private_group = SampleGroup.objects.create(
            name="Foreign private group",
            kind="other",
            owner=cls.other,
            publication_status="private",
        )
        cls.foreign_published_group = SampleGroup.objects.create(
            name="Foreign published group",
            kind="other",
            owner=cls.other,
            publication_status="published",
        )

    def _request(self, user):
        request = RequestFactory().get("/")
        request.user = user
        return request

    def test_sample_api_serializer_exposes_compact_groups(self):
        self.sample.sample_groups.add(self.group)

        data = SampleAPISerializer(self.sample).data

        self.assertIn("sample_groups", data)
        self.assertEqual(len(data["sample_groups"]), 1)
        self.assertEqual(set(data["sample_groups"][0].keys()), {"id", "name", "kind"})
        self.assertEqual(data["sample_groups"][0]["name"], "Accessible group")

    def test_sample_write_serializer_accepts_group_pks(self):
        serializer = SampleWriteSerializer(
            instance=self.sample,
            data={"sample_groups": [self.group.pk]},
            partial=True,
            context={"request": self._request(self.owner)},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.assertCountEqual(self.sample.sample_groups.all(), [self.group])

    def test_serializer_without_request_hides_private_groups(self):
        self.sample.sample_groups.add(self.group, self.private_group)

        data = SampleAPISerializer(self.sample).data

        names = [group["name"] for group in data["sample_groups"]]
        self.assertIn("Accessible group", names)
        self.assertNotIn("Foreign private group", names)

    def test_anonymous_request_hides_private_groups(self):
        self.sample.sample_groups.add(self.group, self.private_group)
        request = RequestFactory().get("/")
        request.user = AnonymousUser()

        data = SampleAPISerializer(self.sample, context={"request": request}).data

        names = [group["name"] for group in data["sample_groups"]]
        self.assertNotIn("Foreign private group", names)

    def test_sample_write_serializer_rejects_inaccessible_group_pks(self):
        serializer = SampleWriteSerializer(
            instance=self.sample,
            data={"sample_groups": [self.private_group.pk]},
            partial=True,
            context={"request": self._request(self.owner)},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("sample_groups", serializer.errors)

    def test_sample_write_serializer_rejects_visible_but_not_editable_group(self):
        serializer = SampleWriteSerializer(
            instance=self.sample,
            data={"sample_groups": [self.foreign_published_group.pk]},
            partial=True,
            context={"request": self._request(self.owner)},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("sample_groups", serializer.errors)

    def test_sample_write_serializer_preserves_groups_editor_cannot_manage(self):
        self.sample.sample_groups.add(self.foreign_published_group)
        serializer = SampleWriteSerializer(
            instance=self.sample,
            data={"sample_groups": [self.group.pk]},
            partial=True,
            context={"request": self._request(self.owner)},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.assertCountEqual(
            self.sample.sample_groups.all(),
            [self.group, self.foreign_published_group],
        )

    def test_sample_write_serializer_accepts_editor_granted_group(self):
        ObjectEditorGrant.objects.create(
            content_object=self.private_group, editor=self.owner
        )
        serializer = SampleWriteSerializer(
            instance=self.sample,
            data={"sample_groups": [self.private_group.pk]},
            partial=True,
            context={"request": self._request(self.owner)},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
