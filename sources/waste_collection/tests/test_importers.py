"""Tests for sources.waste_collection.importers."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from materials.models import Material

from ..importers import CollectionImporter
from ..models import Collection, CollectionCatchment, CollectionSystem, WasteCategory
from .test_views import (
    CollectionImporterSortingMethodTestCase,  # noqa: F401
)


class CollectionImporterMaterialIdentityTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(username="importer-material-owner")
        cls.catchment = CollectionCatchment.objects.create(
            name="Importer Material Catch"
        )
        cls.collection_system = CollectionSystem.objects.create(
            name="Importer Material System"
        )
        cls.waste_category = WasteCategory.objects.create(name="Importer Material Cat")

        cls.allowed_1 = Material.objects.create(name="Importer Allowed 1")
        cls.allowed_2 = Material.objects.create(name="Importer Allowed 2")
        cls.allowed_3 = Material.objects.create(name="Importer Allowed 3")
        cls.forbidden_1 = Material.objects.create(name="Importer Forbidden 1")

    def _record(
        self,
        *,
        allowed_materials,
        forbidden_materials,
        valid_from=date(2024, 1, 1),
    ):
        return {
            "nuts_or_lau_id": None,
            "catchment_name": self.catchment.name,
            "collection_system": self.collection_system.name,
            "waste_category": self.waste_category.name,
            "sorting_method": None,
            "established": None,
            "valid_from": valid_from,
            "valid_until": None,
            "collector_name": None,
            "fee_system": None,
            "frequency": None,
            "connection_type": None,
            "min_bin_size": None,
            "required_bin_capacity": None,
            "required_bin_capacity_reference": None,
            "allowed_materials": allowed_materials,
            "forbidden_materials": forbidden_materials,
            "description": "",
            "property_values": [],
            "flyer_urls": [],
        }

    def test_reimport_with_same_material_set_does_not_create_duplicate_collection(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")

        stats_first = importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_1.name, self.allowed_2.name],
                    forbidden_materials=[self.forbidden_1.name],
                )
            ]
        )
        self.assertEqual(stats_first["created"], 1)

        stats_second = importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_2.name, self.allowed_1.name],
                    forbidden_materials=[self.forbidden_1.name],
                )
            ]
        )

        self.assertEqual(stats_second["created"], 0)
        self.assertEqual(Collection.objects.filter(owner=self.owner).count(), 1)

    def test_different_material_set_creates_new_collection(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")

        importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_1.name, self.allowed_2.name],
                    forbidden_materials=[self.forbidden_1.name],
                )
            ]
        )
        stats_second = importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_1.name, self.allowed_3.name],
                    forbidden_materials=[self.forbidden_1.name],
                )
            ]
        )

        self.assertEqual(stats_second["created"], 1)
        self.assertEqual(Collection.objects.filter(owner=self.owner).count(), 2)
