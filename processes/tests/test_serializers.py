"""Serializer tests for the processes module."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase
from django.urls import reverse

from bibliography.models import Author, Licence, Source, SourceAuthor
from materials.models import Material
from utils.properties.models import Unit

from ..models import (
    Process,
    ProcessCategory,
    ProcessMaterial,
    ProcessOperatingParameter,
)
from ..serializers import (
    ProcessCategorySerializer,
    ProcessDetailSerializer,
    ProcessListSerializer,
    ProcessMaterialAPISerializer,
    ProcessOperatingParameterSerializer,
)


class ProcessCategorySerializerTestCase(TestCase):
    """Test ProcessCategory serializer."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create(username="test_user")
        cls.category = ProcessCategory.objects.create(
            name="Thermochemical",
            description="Test description",
            owner=cls.owner,
            publication_status="published",
        )

    def test_serialize_category(self):
        """Serializer should serialize category correctly."""
        serializer = ProcessCategorySerializer(self.category)
        data = serializer.data

        self.assertEqual(data["name"], "Thermochemical")
        self.assertEqual(data["description"], "Test description")
        self.assertEqual(data["publication_status"], "published")

    def test_deserialize_category(self):
        """Serializer should deserialize valid data."""
        data = {"name": "New Category", "description": "New description"}
        serializer = ProcessCategorySerializer(data=data)

        # Note: owner field is read-only and set in the view
        self.assertTrue(serializer.is_valid())


class ProcessMaterialSerializerTestCase(TestCase):
    """Test ProcessMaterial serializer."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create(username="test_user")
        cls.process = Process.objects.create(name="Test Process", owner=cls.owner)
        cls.material = Material.objects.create(
            name="Wood Chips", owner=cls.owner, publication_status="published"
        )
        cls.unit = Unit.objects.create(name="kg", owner=cls.owner)

        cls.process_material = ProcessMaterial.objects.create(
            process=cls.process,
            material=cls.material,
            role=ProcessMaterial.Role.INPUT,
            quantity_value=Decimal("10.5"),
            quantity_unit=cls.unit,
        )

    def test_serialize_process_material(self):
        """Serializer should serialize process material correctly."""
        serializer = ProcessMaterialAPISerializer(self.process_material)
        data = serializer.data

        self.assertEqual(data["role"], ProcessMaterial.Role.INPUT)
        self.assertEqual(data["role_display"], "Input")
        self.assertEqual(float(data["quantity_value"]), 10.5)

    def test_deserialize_process_material_with_ids(self):
        """Write fields material_id and quantity_unit_id should accept valid PKs."""
        data = {
            "material_id": self.material.pk,
            "role": ProcessMaterial.Role.OUTPUT,
            "quantity_value": "5.0",
            "quantity_unit_id": self.unit.pk,
        }
        serializer = ProcessMaterialAPISerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)


class ProcessOperatingParameterSerializerTestCase(TestCase):
    """Test ProcessOperatingParameter serializer."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create(username="test_user")
        cls.process = Process.objects.create(name="Test Process", owner=cls.owner)
        cls.unit = Unit.objects.create(name="°C", owner=cls.owner)

        cls.parameter = ProcessOperatingParameter.objects.create(
            process=cls.process,
            parameter=ProcessOperatingParameter.Parameter.TEMPERATURE,
            value_min=Decimal("100"),
            value_max=Decimal("200"),
            unit=cls.unit,
        )

    def test_serialize_parameter(self):
        """Serializer should serialize parameter correctly."""
        serializer = ProcessOperatingParameterSerializer(self.parameter)
        data = serializer.data

        self.assertEqual(
            data["parameter"], ProcessOperatingParameter.Parameter.TEMPERATURE
        )
        self.assertEqual(data["parameter_display"], "Temperature")
        self.assertEqual(float(data["value_min"]), 100)
        self.assertEqual(float(data["value_max"]), 200)

    def test_deserialize_parameter_with_unit_id(self):
        """Write field unit_id should accept a valid PK."""
        data = {
            "parameter": ProcessOperatingParameter.Parameter.PRESSURE,
            "value_min": "1.0",
            "value_max": "10.0",
            "unit_id": self.unit.pk,
        }
        serializer = ProcessOperatingParameterSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)


class ProcessListSerializerTestCase(TestCase):
    """Test ProcessListSerializer."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create(username="test_user")
        cls.category = ProcessCategory.objects.create(
            name="Thermochemical",
            owner=cls.owner,
            publication_status="published",
        )
        cls.author_1 = Author.objects.create(
            first_names="Ada",
            last_names="Lovelace",
            owner=cls.owner,
            publication_status="published",
        )
        cls.author_2 = Author.objects.create(
            first_names="Grace",
            last_names="Hopper",
            owner=cls.owner,
            publication_status="published",
        )

        cls.process = Process.objects.create(
            name="Pyrolysis",
            short_description="Test description",
            mechanism="Thermal Decomposition",
            owner=cls.owner,
            publication_status="published",
        )
        cls.process.categories.add(cls.category)
        cls.process.authors.add(cls.author_1, cls.author_2)

    def test_serialize_process_list(self):
        """List serializer should include basic process info."""
        serializer = ProcessListSerializer(self.process)
        data = serializer.data

        self.assertEqual(data["name"], "Pyrolysis")
        self.assertEqual(data["short_description"], "Test description")
        self.assertEqual(data["mechanism"], "Thermal Decomposition")
        self.assertEqual(data["owner_name"], "test_user")
        self.assertEqual(len(data["categories"]), 1)
        self.assertEqual(data["authors"], [self.author_1.pk, self.author_2.pk])


class ProcessDetailSerializerTestCase(TestCase):
    """Test ProcessDetailSerializer."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create(username="test_user")
        cls.category = ProcessCategory.objects.create(
            name="Thermochemical",
            owner=cls.owner,
            publication_status="published",
        )
        cls.author_1 = Author.objects.create(
            first_names="Ada",
            last_names="Lovelace",
            owner=cls.owner,
            publication_status="published",
        )
        cls.author_2 = Author.objects.create(
            first_names="Grace",
            last_names="Hopper",
            owner=cls.owner,
            publication_status="published",
        )

        cls.process = Process.objects.create(
            name="Pyrolysis",
            short_description="Test description",
            mechanism="Thermal Decomposition",
            description="Detailed description",
            owner=cls.owner,
            publication_status="published",
        )
        cls.process.categories.add(cls.category)
        cls.process.authors.add(cls.author_1, cls.author_2)

        # Add materials
        cls.material_in = Material.objects.create(
            name="Wood Chips", owner=cls.owner, publication_status="published"
        )
        cls.material_out = Material.objects.create(
            name="Bio-oil", owner=cls.owner, publication_status="published"
        )

        ProcessMaterial.objects.create(
            process=cls.process,
            material=cls.material_in,
            role=ProcessMaterial.Role.INPUT,
        )
        ProcessMaterial.objects.create(
            process=cls.process,
            material=cls.material_out,
            role=ProcessMaterial.Role.OUTPUT,
        )

    def test_serialize_process_detail(self):
        """Detail serializer should include all process information."""
        serializer = ProcessDetailSerializer(self.process)
        data = serializer.data

        self.assertEqual(data["name"], "Pyrolysis")
        self.assertEqual(data["description"], "Detailed description")
        self.assertEqual(data["authors"], [self.author_1.pk, self.author_2.pk])
        self.assertEqual(len(data["input_materials"]), 1)
        self.assertEqual(len(data["output_materials"]), 1)
        self.assertEqual(data["input_materials"][0]["name"], "Wood Chips")
        self.assertEqual(data["output_materials"][0]["name"], "Bio-oil")


class ProcessSourceReferenceContextTestCase(TestCase):
    """get_sources must propagate request context so nested Source refs scope."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("psc-owner")
        cls.outsider = User.objects.create_user("psc-outsider")
        cls.foreign = User.objects.create_user("psc-foreign")
        for u in (cls.owner, cls.outsider, cls.foreign):
            u.groups.clear()
        cls.licence = Licence.objects.create(
            name="psc-lic", owner=cls.owner, publication_status="private"
        )
        cls.a_pub = Author.objects.create(
            last_names="PubA", owner=cls.owner, publication_status="published"
        )
        cls.a_own = Author.objects.create(
            last_names="OwnB", owner=cls.owner, publication_status="private"
        )
        cls.a_for = Author.objects.create(
            last_names="ForC", owner=cls.foreign, publication_status="private"
        )
        cls.source = Source.objects.create(
            title="ProcessEvidence",
            year="2024",
            citation_key="PINNEDKEY",
            owner=cls.owner,
            publication_status="published",
            licence=cls.licence,
        )
        SourceAuthor.objects.create(source=cls.source, author=cls.a_pub, position=1)
        SourceAuthor.objects.create(source=cls.source, author=cls.a_own, position=2)
        SourceAuthor.objects.create(source=cls.source, author=cls.a_for, position=3)
        cls.foreign_source = Source.objects.create(
            title="ForeignSrc",
            owner=cls.foreign,
            publication_status="private",
            year="2024",
        )
        cls.process = Process.objects.create(
            name="ContextProcess",
            owner=cls.owner,
            publication_status="published",
        )
        cls.process.sources.add(cls.source)
        cls.process.sources.add(cls.foreign_source)

    def _ctx(self, user):
        req = RequestFactory().get("/x/")
        req.user = user
        return {"request": req}

    def _source_entry(self, data):
        return next(s for s in data["sources"] if s["id"] == self.source.pk)

    def test_owner_context_propagates(self):
        for ser_cls in (ProcessListSerializer, ProcessDetailSerializer):
            with self.subTest(ser=ser_cls.__name__):
                data = ser_cls(self.process, context=self._ctx(self.owner)).data
                self.assertEqual([s["id"] for s in data["sources"]], [self.source.pk])
                entry = self._source_entry(data)
                ids = [a["id"] for a in entry["authors"]]
                self.assertEqual(ids, [self.a_pub.pk, self.a_own.pk])
                self.assertEqual(entry["licence"]["id"], self.licence.pk)
                self.assertEqual(entry["licence"]["name"], "psc-lic")

    def test_anon_outsider_and_no_context_scope(self):
        for label, ctx in (
            ("anon", self._ctx(AnonymousUser())),
            ("outsider", self._ctx(self.outsider)),
            ("none", {}),
        ):
            for ser_cls in (ProcessListSerializer, ProcessDetailSerializer):
                with self.subTest(label=label, ser=ser_cls.__name__):
                    data = ser_cls(self.process, context=ctx).data
                    self.assertEqual(
                        [s["id"] for s in data["sources"]], [self.source.pk]
                    )
                    entry = self._source_entry(data)
                    self.assertEqual(
                        [a["id"] for a in entry["authors"]], [self.a_pub.pk]
                    )
                    self.assertIsNone(entry["licence"])

    def test_http_owner_list_and_detail(self):
        self.client.force_login(self.owner)
        for url in (
            reverse("processes:api-process-list"),
            reverse("processes:api-process-detail", kwargs={"pk": self.process.pk}),
        ):
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            if isinstance(body, list):
                entry = next(p for p in body if p["id"] == self.process.pk)
            else:
                entry = body
            self.assertEqual([s["id"] for s in entry["sources"]], [self.source.pk])
            src = self._source_entry(entry)
            self.assertEqual(
                [a["id"] for a in src["authors"]], [self.a_pub.pk, self.a_own.pk]
            )
            self.assertEqual(src["licence"]["id"], self.licence.pk)

    def test_http_anonymous_list_and_detail(self):
        for url in (
            reverse("processes:api-process-list"),
            reverse("processes:api-process-detail", kwargs={"pk": self.process.pk}),
        ):
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200)
            body = resp.json()
            if isinstance(body, list):
                entry = next(p for p in body if p["id"] == self.process.pk)
            else:
                entry = body
            src = self._source_entry(entry)
            self.assertEqual([a["id"] for a in src["authors"]], [self.a_pub.pk])
            self.assertIsNone(src["licence"])
            self.assertNotIn(
                self.foreign_source.pk, [s["id"] for s in entry["sources"]]
            )
