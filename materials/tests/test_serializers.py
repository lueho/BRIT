from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.test import RequestFactory, TestCase
from django.urls import reverse
from factory.django import mute_signals

from bibliography.models import Source
from distributions.models import Timestep
from utils.properties.models import Unit

from ..models import (
    ComponentMeasurement,
    Composition,
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialProperty,
    MaterialPropertyValue,
    Sample,
    SampleSeries,
)
from ..serializers import (
    CompositionDoughnutChartSerializer,
    CompositionModelSerializer,
    MaterialPropertyValueModelSerializer,
    SampleModelSerializer,
    SampleSeriesModelSerializer,
)


class MaterialPropertySerializerTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        prop = MaterialProperty.objects.create(name="Test Property", unit="g/kg")
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
        self.assertNotEqual(data["unit"], self.value.property.unit)


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
            unit="%",
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
            component=MaterialComponent.objects.other(),
            unit=unit,
            average=Decimal("50"),
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
        self.assertEqual(data["shares"][-1]["as_percentage"], "100.0%")


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
