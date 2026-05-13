"""Tests for sources.waste_collection.importers."""

from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile

import openpyxl
from django.contrib.auth import get_user_model
from django.db.models import signals
from django.test import TestCase, override_settings
from factory.django import mute_signals

from bibliography.models import Source
from maps.models import LauRegion, Region, RegionAttributeValue, RegionProperty
from materials.models import Material

from ..derived_values import get_derived_property_config, get_derived_value_config
from ..importers import CollectionImporter
from ..management.commands.import_de_2024_improved_standalone import _load_records
from ..models import (
    Collection,
    CollectionCatchment,
    CollectionFrequency,
    CollectionPropertyValue,
    CollectionSystem,
    Collector,
    WasteCategory,
    WasteFlyer,
)
from utils.properties.models import Property, Unit
from .test_views import (
    CollectionImporterBinConfigurationTestCase,  # noqa: F401
)


class CollectionImporterMaterialIdentityTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(username="importer-material-owner")
        cls.other_owner = user_model.objects.create_user(
            username="existing-collection-owner"
        )
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
            "bin_configuration": None,
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
            "sources": [],
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
        self.assertEqual(stats_second["unchanged"], 1)
        self.assertEqual(stats_second["skipped"], 0)
        self.assertEqual(Collection.objects.filter(owner=self.owner).count(), 1)

    def test_reimport_preserves_existing_collection_owner(self):
        collection = Collection.objects.create(
            name="Existing importer collection",
            owner=self.other_owner,
            publication_status="private",
            catchment=self.catchment,
            collection_system=self.collection_system,
            waste_category=self.waste_category,
            valid_from=date(2024, 1, 1),
        )
        collection.allowed_materials.set([self.allowed_1, self.allowed_2])
        collection.forbidden_materials.set([self.forbidden_1])

        importer = CollectionImporter(owner=self.owner, publication_status="private")
        stats = importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_2.name, self.allowed_1.name],
                    forbidden_materials=[self.forbidden_1.name],
                )
                | {"description": "Updated by import"}
            ]
        )

        collection.refresh_from_db()
        self.assertEqual(stats["created"], 0)
        self.assertEqual(stats["updated"], 1)
        self.assertEqual(collection.owner, self.other_owner)
        self.assertEqual(collection.description, "Updated by import")
        self.assertEqual(Collection.objects.filter(owner=self.owner).count(), 0)

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

    def test_new_version_links_predecessor_even_when_materials_change(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")

        predecessor_stats = importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_1.name, self.allowed_2.name],
                    forbidden_materials=[self.forbidden_1.name],
                    valid_from=date(2023, 1, 1),
                )
            ]
        )
        self.assertEqual(predecessor_stats["created"], 1)

        stats = importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_1.name, self.allowed_3.name],
                    forbidden_materials=[],
                    valid_from=date(2024, 1, 1),
                )
            ]
        )

        predecessor = Collection.objects.get(
            owner=self.owner, valid_from=date(2023, 1, 1)
        )
        successor = Collection.objects.get(
            owner=self.owner, valid_from=date(2024, 1, 1)
        )
        predecessor.refresh_from_db()

        self.assertEqual(stats["created"], 1)
        self.assertEqual(stats["predecessor_links"], 1)
        self.assertEqual(list(successor.predecessors.all()), [predecessor])
        self.assertEqual(predecessor.valid_until, date(2023, 12, 31))
        self.assertEqual(
            set(successor.allowed_materials.values_list("name", flat=True)),
            {self.allowed_1.name, self.allowed_3.name},
        )
        self.assertEqual(successor.forbidden_materials.count(), 0)

    def test_reimport_reuses_custom_source_notes(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")

        stats_first = importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_1.name, self.allowed_2.name],
                    forbidden_materials=[self.forbidden_1.name],
                )
                | {"sources": ["Private correspondence with district office"]}
            ]
        )

        self.assertEqual(stats_first["sources_created"], 1)
        collection = Collection.objects.get(
            owner=self.owner, valid_from=date(2024, 1, 1)
        )
        self.assertEqual(
            list(collection.sources.values_list("title", flat=True)),
            ["Private correspondence with district office"],
        )
        self.assertTrue(
            Source.objects.filter(
                owner=self.owner,
                type="custom",
                title="Private correspondence with district office",
            ).exists()
        )

        stats_second = importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_2.name, self.allowed_1.name],
                    forbidden_materials=[self.forbidden_1.name],
                )
                | {"sources": ["Private correspondence with district office"]}
            ]
        )

        collection.refresh_from_db()
        self.assertEqual(stats_second["created"], 0)
        self.assertEqual(stats_second["sources_created"], 0)
        self.assertEqual(collection.sources.count(), 1)

    def test_reimport_syncs_collection_source_notes_exactly(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")

        importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_1.name, self.allowed_2.name],
                    forbidden_materials=[self.forbidden_1.name],
                )
                | {
                    "sources": [
                        "Private correspondence with district office",
                        "Municipal waste guide",
                    ]
                }
            ]
        )

        stats = importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_2.name, self.allowed_1.name],
                    forbidden_materials=[self.forbidden_1.name],
                )
                | {"sources": ["Municipal waste guide"]}
            ]
        )

        collection = Collection.objects.get(
            owner=self.owner, valid_from=date(2024, 1, 1)
        )
        self.assertEqual(stats["updated"], 1)
        self.assertEqual(stats["unchanged"], 0)
        self.assertIn("sources updated", stats["changes"][0])
        self.assertEqual(
            set(collection.sources.values_list("title", flat=True)),
            {"Municipal waste guide"},
        )

    def test_source_url_is_reclassified_as_waste_flyer(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")
        url = "https://example.org/flyer"

        stats = importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_1.name, self.allowed_2.name],
                    forbidden_materials=[self.forbidden_1.name],
                )
                | {"sources": [url]}
            ]
        )

        collection = Collection.objects.get(
            owner=self.owner, valid_from=date(2024, 1, 1)
        )
        self.assertEqual(stats["sources_created"], 0)
        self.assertEqual(stats["flyers_created"], 1)
        self.assertEqual(collection.sources.count(), 0)
        self.assertEqual(
            list(collection.flyers.values_list("url", flat=True)),
            [url],
        )
        self.assertFalse(
            Source.objects.filter(owner=self.owner, type="custom", title=url).exists()
        )

    def test_source_entry_splits_url_and_free_text_note(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")
        url = "https://example.org/flyer"
        note = "Private correspondence with district office"

        stats = importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_1.name, self.allowed_2.name],
                    forbidden_materials=[self.forbidden_1.name],
                )
                | {"sources": [f"{url}, {note}"]}
            ]
        )

        collection = Collection.objects.get(
            owner=self.owner, valid_from=date(2024, 1, 1)
        )
        self.assertEqual(stats["sources_created"], 1)
        self.assertEqual(stats["flyers_created"], 1)
        self.assertEqual(
            list(collection.sources.values_list("title", flat=True)),
            [note],
        )
        self.assertEqual(
            list(collection.flyers.values_list("url", flat=True)),
            [url],
        )

    def test_reimport_reuses_existing_duplicate_custom_source_title(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")
        title = "Private correspondence with district office"

        first_source = Source.objects.create(
            owner=self.owner,
            type="custom",
            title=title,
            publication_status="private",
        )
        Source.objects.create(
            owner=self.owner,
            type="custom",
            title=title,
            publication_status="private",
        )

        stats = importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_1.name, self.allowed_2.name],
                    forbidden_materials=[self.forbidden_1.name],
                )
                | {"sources": [title]}
            ]
        )

        collection = Collection.objects.get(
            owner=self.owner, valid_from=date(2024, 1, 1)
        )
        self.assertEqual(stats["created"], 1)
        self.assertEqual(stats["sources_created"], 0)
        self.assertEqual(
            list(collection.sources.values_list("id", flat=True)),
            [first_source.id],
        )

    def test_reimport_reuses_existing_duplicate_flyer_url(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")
        url = "https://duplicate-flyer.example.org"

        with mute_signals(signals.post_save):
            first_flyer = WasteFlyer.objects.create(url=url)
            WasteFlyer.objects.create(url=url)

        stats = importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_1.name, self.allowed_2.name],
                    forbidden_materials=[self.forbidden_1.name],
                )
                | {"flyer_urls": [url]}
            ]
        )

        collection = Collection.objects.get(
            owner=self.owner, valid_from=date(2024, 1, 1)
        )
        self.assertEqual(stats["created"], 1)
        self.assertEqual(stats["flyers_created"], 0)
        self.assertEqual(
            list(collection.flyers.values_list("id", flat=True)),
            [first_flyer.id],
        )

    def test_reimport_syncs_collection_flyers_exactly(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")
        first_url = "https://example.org/flyer-a"
        second_url = "https://example.org/flyer-b"

        importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_1.name, self.allowed_2.name],
                    forbidden_materials=[self.forbidden_1.name],
                )
                | {"flyer_urls": [first_url, second_url]}
            ]
        )

        stats = importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_2.name, self.allowed_1.name],
                    forbidden_materials=[self.forbidden_1.name],
                )
                | {"flyer_urls": [second_url]}
            ]
        )

        collection = Collection.objects.get(
            owner=self.owner, valid_from=date(2024, 1, 1)
        )
        self.assertEqual(stats["updated"], 1)
        self.assertEqual(stats["unchanged"], 0)
        self.assertIn("flyers updated", stats["changes"][0])
        self.assertEqual(
            set(collection.flyers.values_list("url", flat=True)),
            {second_url},
        )

    def test_combined_lookup_codes_fall_back_to_collector_catchment(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")
        collector = Collector.objects.create(
            name="Importer Collector",
            owner=self.owner,
            catchment=self.catchment,
        )

        stats = importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_1.name],
                    forbidden_materials=[],
                )
                | {
                    "nuts_or_lau_id": "DEG02, DEG0L",
                    "catchment_name": "",
                    "collector_name": collector.name,
                }
            ]
        )

        collection = Collection.objects.get(
            owner=self.owner, valid_from=date(2024, 1, 1)
        )
        self.assertEqual(stats["created"], 1)
        self.assertEqual(collection.catchment, self.catchment)
        self.assertEqual(stats["warnings"], [])

    def test_combined_lookup_codes_fall_back_to_predecessor_catchment(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")
        predecessor_catchment = CollectionCatchment.objects.create(
            name="Importer Predecessor Catch"
        )
        collector = Collector.objects.create(
            name="Importer Predecessor Collector",
            owner=self.owner,
        )
        predecessor = Collection.objects.create(
            name="Importer predecessor",
            owner=self.owner,
            publication_status="private",
            catchment=predecessor_catchment,
            collector=collector,
            collection_system=self.collection_system,
            waste_category=self.waste_category,
            valid_from=date(2023, 1, 1),
        )
        predecessor.allowed_materials.set([self.allowed_1])

        stats = importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_1.name],
                    forbidden_materials=[],
                )
                | {
                    "nuts_or_lau_id": "DEG0I, DEG0K",
                    "catchment_name": "",
                    "collector_name": collector.name,
                }
            ]
        )

        collection = Collection.objects.get(
            owner=self.owner, valid_from=date(2024, 1, 1)
        )
        self.assertEqual(stats["created"], 1)
        self.assertEqual(stats["predecessor_links"], 1)
        self.assertEqual(collection.catchment, predecessor_catchment)
        self.assertEqual(list(collection.predecessors.all()), [predecessor])
        self.assertEqual(stats["warnings"], [])

    def test_combined_lookup_fallback_uses_predecessor_catchment_when_materials_change(
        self,
    ):
        importer = CollectionImporter(owner=self.owner, publication_status="private")
        predecessor_catchment = CollectionCatchment.objects.create(
            name="Importer Predecessor Catch Changed Materials"
        )
        collector = Collector.objects.create(
            name="Importer Changed Material Collector",
            owner=self.owner,
        )
        predecessor = Collection.objects.create(
            name="Importer predecessor changed materials",
            owner=self.owner,
            publication_status="private",
            catchment=predecessor_catchment,
            collector=collector,
            collection_system=self.collection_system,
            waste_category=self.waste_category,
            valid_from=date(2023, 1, 1),
        )
        predecessor.allowed_materials.set([self.allowed_2])
        predecessor.forbidden_materials.set([self.forbidden_1])

        stats = importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_1.name],
                    forbidden_materials=[],
                )
                | {
                    "nuts_or_lau_id": "DEG0I, DEG0K",
                    "catchment_name": "",
                    "collector_name": collector.name,
                }
            ]
        )

        collection = Collection.objects.get(
            owner=self.owner, valid_from=date(2024, 1, 1)
        )
        self.assertEqual(stats["created"], 1)
        self.assertEqual(stats["predecessor_links"], 1)
        self.assertEqual(collection.catchment, predecessor_catchment)
        self.assertEqual(list(collection.predecessors.all()), [predecessor])
        self.assertEqual(stats["warnings"], [])

    def test_named_catchment_lookup_is_case_insensitive(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")

        stats = importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_1.name],
                    forbidden_materials=[],
                )
                | {
                    "catchment_name": self.catchment.name.upper(),
                }
            ]
        )

        collection = Collection.objects.get(
            owner=self.owner, valid_from=date(2024, 1, 1)
        )
        self.assertEqual(stats["created"], 1)
        self.assertEqual(collection.catchment, self.catchment)
        self.assertEqual(stats["warnings"], [])

    def test_missing_named_catchment_falls_back_to_collector_catchment(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")
        collector = Collector.objects.create(
            name="Importer Named Fallback Collector",
            owner=self.owner,
            catchment=self.catchment,
        )

        stats = importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_1.name],
                    forbidden_materials=[],
                )
                | {
                    "catchment_name": "Unknown imported catchment name",
                    "collector_name": collector.name,
                }
            ]
        )

        collection = Collection.objects.get(
            owner=self.owner, valid_from=date(2024, 1, 1)
        )
        self.assertEqual(stats["created"], 1)
        self.assertEqual(collection.catchment, self.catchment)
        self.assertEqual(stats["warnings"], [])

    def test_missing_named_catchment_falls_back_to_predecessor_catchment(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")
        predecessor_catchment = CollectionCatchment.objects.create(
            name="Importer Named Fallback Predecessor Catch"
        )
        collector = Collector.objects.create(
            name="Importer Named Fallback Predecessor Collector",
            owner=self.owner,
        )
        predecessor = Collection.objects.create(
            name="Importer named fallback predecessor",
            owner=self.owner,
            publication_status="private",
            catchment=predecessor_catchment,
            collector=collector,
            collection_system=self.collection_system,
            waste_category=self.waste_category,
            valid_from=date(2023, 1, 1),
        )
        predecessor.allowed_materials.set([self.allowed_1])

        stats = importer.run(
            [
                self._record(
                    allowed_materials=[self.allowed_1.name],
                    forbidden_materials=[],
                )
                | {
                    "catchment_name": "Unknown imported catchment name",
                    "collector_name": collector.name,
                }
            ]
        )

        collection = Collection.objects.get(
            owner=self.owner, valid_from=date(2024, 1, 1)
        )
        self.assertEqual(stats["created"], 1)
        self.assertEqual(stats["predecessor_links"], 1)
        self.assertEqual(collection.catchment, predecessor_catchment)
        self.assertEqual(list(collection.predecessors.all()), [predecessor])
        self.assertEqual(stats["warnings"], [])


class CollectionImporterCountryScopedLauLookupTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(username="importer-country-owner")
        cls.collection_system = CollectionSystem.objects.create(
            name="Importer Country System"
        )
        cls.waste_category = WasteCategory.objects.create(name="Importer Country Cat")
        cls.belgian_lau = LauRegion.objects.create(
            country="BE",
            cntr_code="BE",
            lau_id="25120",
            lau_name="Orp-Jauche",
        )
        cls.spanish_lau = LauRegion.objects.create(
            country="ES",
            cntr_code="ES",
            lau_id="25120",
            lau_name="Catalonia Municipality",
        )
        cls.belgian_catchment = CollectionCatchment.objects.create(
            name="Belgian Colliding Catchment",
            region=cls.belgian_lau.region_ptr,
            type="lau",
        )
        cls.spanish_catchment = CollectionCatchment.objects.create(
            name="Spanish Colliding Catchment",
            region=cls.spanish_lau.region_ptr,
            type="lau",
        )

    def _record(self, **overrides):
        return {
            "nuts_or_lau_id": "25120",
            "country_code": None,
            "catchment_name": "",
            "collection_system": self.collection_system.name,
            "waste_category": self.waste_category.name,
            "bin_configuration": None,
            "established": None,
            "valid_from": date(2024, 1, 1),
            "valid_until": None,
            "collector_name": None,
            "fee_system": None,
            "frequency": None,
            "connection_type": None,
            "min_bin_size": None,
            "required_bin_capacity": None,
            "required_bin_capacity_reference": None,
            "allowed_materials": [],
            "forbidden_materials": [],
            "sources": [],
            "description": "",
            "property_values": [],
            "flyer_urls": [],
        } | overrides

    def test_country_scoped_lau_lookup_prefers_matching_country(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")

        stats = importer.run([self._record(country_code="ES")])

        collection = Collection.objects.get(owner=self.owner)
        self.assertEqual(stats["created"], 1)
        self.assertEqual(stats["warnings"], [])
        self.assertEqual(collection.catchment, self.spanish_catchment)

    def test_ambiguous_lau_without_country_code_warns_and_skips(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")

        stats = importer.run([self._record()])

        self.assertEqual(stats["created"], 0)
        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(Collection.objects.filter(owner=self.owner).count(), 0)
        self.assertEqual(
            stats["warnings"],
            [
                "record[0]: LAU id '25120' is ambiguous across countries — provide country_code."
            ],
        )


class CollectionImporterCreateCollectorsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(username="importer-create-collector")
        cls.catchment = CollectionCatchment.objects.create(
            name="Importer Create Collector Catchment"
        )
        cls.collection_system = CollectionSystem.objects.create(
            name="Importer Create Collector System"
        )
        cls.waste_category = WasteCategory.objects.create(
            name="Importer Create Collector Category"
        )

    def _record(self):
        return {
            "nuts_or_lau_id": None,
            "country_code": None,
            "catchment_name": self.catchment.name,
            "collection_system": self.collection_system.name,
            "waste_category": self.waste_category.name,
            "bin_configuration": None,
            "established": None,
            "valid_from": date(2024, 1, 1),
            "valid_until": None,
            "collector_name": "Ajuntament de Cardona",
            "fee_system": None,
            "frequency": None,
            "connection_type": None,
            "min_bin_size": None,
            "required_bin_capacity": None,
            "required_bin_capacity_reference": None,
            "allowed_materials": [],
            "forbidden_materials": [],
            "sources": [],
            "description": "",
            "property_values": [],
            "flyer_urls": [],
        }

    def test_create_collectors_creates_missing_named_collector_when_enabled(self):
        importer = CollectionImporter(
            owner=self.owner,
            publication_status="private",
            create_collectors=True,
        )

        stats = importer.run([self._record()])

        collection = Collection.objects.get(owner=self.owner)
        self.assertEqual(stats["created"], 1)
        self.assertEqual(stats["collectors_created"], 1)
        self.assertEqual(collection.collector.name, "Ajuntament de Cardona")


@override_settings(
    WASTE_COLLECTION_SPECIFIC_WASTE_PROPERTY_NAME="specific waste collected [importer raw cpv test]",
    WASTE_COLLECTION_TOTAL_WASTE_PROPERTY_NAME="total waste collected [importer raw cpv test]",
    WASTE_COLLECTION_SPECIFIC_WASTE_UNIT_NAME="kg/(cap.*a) [importer raw cpv test]",
    WASTE_COLLECTION_TOTAL_WASTE_UNIT_NAME="Mg/a [importer raw cpv test]",
    WASTE_COLLECTION_POPULATION_ATTRIBUTE_NAME="Population [importer raw cpv test]",
)
class CollectionImporterRawCpvPrecedenceTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(username="importer-raw-cpv-owner")
        cls.region = Region.objects.create(name="Importer Raw CPV Region", country="ES")
        cls.catchment = CollectionCatchment.objects.create(
            name="Importer Raw CPV Catchment",
            region=cls.region,
        )
        cls.collection_system = CollectionSystem.objects.create(
            name="Importer Raw CPV System"
        )
        cls.waste_category = WasteCategory.objects.create(name="Importer Raw CPV Cat")
        cls.specific_unit = Unit.objects.create(
            name="kg/(cap.*a) [importer raw cpv test]"
        )
        cls.total_unit = Unit.objects.create(name="Mg/a [importer raw cpv test]")
        cls.population_attribute = RegionProperty.objects.create(
            name="Population [importer raw cpv test]",
            unit="cap",
        )
        RegionAttributeValue.objects.create(
            region=cls.region,
            property=cls.population_attribute,
            value=1000,
            date=date(2024, 1, 1),
        )
        cls.specific_property = Property.objects.create(
            name="specific waste collected [importer raw cpv test]",
            unit="kg/(cap.*a) [importer raw cpv test]",
        )
        cls.total_property = Property.objects.create(
            name="total waste collected [importer raw cpv test]",
            unit="Mg/a [importer raw cpv test]",
        )

    def setUp(self):
        get_derived_property_config.cache_clear()
        get_derived_value_config.cache_clear()

    def _record(self):
        return {
            "nuts_or_lau_id": None,
            "country_code": None,
            "catchment_name": self.catchment.name,
            "collection_system": self.collection_system.name,
            "waste_category": self.waste_category.name,
            "bin_configuration": None,
            "established": None,
            "valid_from": date(2024, 1, 1),
            "valid_until": None,
            "collector_name": None,
            "fee_system": None,
            "frequency": None,
            "connection_type": None,
            "min_bin_size": None,
            "required_bin_capacity": None,
            "required_bin_capacity_reference": None,
            "allowed_materials": [],
            "forbidden_materials": [],
            "sources": [],
            "description": "",
            "property_values": [
                {
                    "property_id": self.specific_property.id,
                    "unit_name": self.specific_unit.name,
                    "year": 2024,
                    "average": 100.0,
                    "flyer_urls": [],
                },
                {
                    "property_id": self.total_property.id,
                    "unit_name": self.total_unit.name,
                    "year": 2024,
                    "average": 100.0,
                    "flyer_urls": [],
                },
            ],
            "flyer_urls": [],
        }

    def test_import_keeps_workbook_specific_and_total_as_raw_values(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")

        stats = importer.run([self._record()])

        collection = Collection.objects.get(owner=self.owner)
        specific_rows = CollectionPropertyValue.objects.filter(
            collection=collection,
            property=self.specific_property,
            year=2024,
        )
        total_rows = CollectionPropertyValue.objects.filter(
            collection=collection,
            property=self.total_property,
            year=2024,
        )
        self.assertEqual(stats["cpv_created"], 2)
        self.assertEqual(stats["cpv_unchanged"], 0)
        self.assertEqual(specific_rows.count(), 1)
        self.assertEqual(total_rows.count(), 1)
        self.assertFalse(specific_rows.first().is_derived)
        self.assertFalse(total_rows.first().is_derived)
        self.assertEqual(specific_rows.first().average, 100.0)
        self.assertEqual(total_rows.first().average, 100.0)


class CollectionImporterFrequencyResolutionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(username="importer-frequency-owner")
        cls.catchment = CollectionCatchment.objects.create(
            name="Importer Frequency Catch"
        )
        cls.collection_system = CollectionSystem.objects.create(
            name="Importer Frequency System"
        )
        cls.waste_category = WasteCategory.objects.create(
            name="Importer Frequency Category"
        )
        cls.fixed_frequency = CollectionFrequency.objects.create(
            name="Fixed; 26 per year (1 per 2 weeks)",
            type="Fixed",
            owner=cls.owner,
        )
        cls.fixed_simple_frequency = CollectionFrequency.objects.create(
            name="Fixed; 52 per year",
            type="Fixed",
            owner=cls.owner,
        )
        cls.fixed_flexible_frequency = CollectionFrequency.objects.create(
            name=(
                "Fixed-Flexible; Standard: 26 per year (1 per 2 weeks); "
                "Optional: 52 per year (1 per week)"
            ),
            type="Fixed-Flexible",
            owner=cls.owner,
        )
        cls.seasonal_frequency = CollectionFrequency.objects.create(
            name=(
                "Seasonal; 19 per year (1 per 2 weeks from March - November, "
                "0 from December - February)"
            ),
            type="Seasonal",
            owner=cls.owner,
        )

    def _record(self, frequency_name):
        return {
            "nuts_or_lau_id": None,
            "catchment_name": self.catchment.name,
            "collection_system": self.collection_system.name,
            "waste_category": self.waste_category.name,
            "bin_configuration": None,
            "established": None,
            "valid_from": date(2024, 1, 1),
            "valid_until": None,
            "collector_name": None,
            "fee_system": None,
            "frequency": frequency_name,
            "connection_type": None,
            "min_bin_size": None,
            "required_bin_capacity": None,
            "required_bin_capacity_reference": None,
            "allowed_materials": [],
            "forbidden_materials": [],
            "sources": [],
            "description": "",
            "property_values": [],
            "flyer_urls": [],
        }

    def test_resolve_frequency_exact_match_does_not_warn(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")
        importer._load_lookups()
        stats = {"warnings": []}

        frequency = importer._resolve_frequency(
            self._record(self.fixed_frequency.name),
            label="record[0]",
            stats=stats,
        )

        self.assertEqual(frequency, self.fixed_frequency)
        self.assertEqual(stats["warnings"], [])

    def test_resolve_frequency_canonicalizes_fixed_flexible_variant(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")
        importer._load_lookups()
        stats = {"warnings": []}

        frequency = importer._resolve_frequency(
            self._record(
                "Fixed-Flexible; Standard: 26 per year (1 per 2 weeks), "
                "52 per year (1 per week)"
            ),
            label="record[1]",
            stats=stats,
        )

        self.assertEqual(frequency, self.fixed_flexible_frequency)
        self.assertEqual(
            stats["warnings"],
            [
                "record[1]: CollectionFrequency 'Fixed-Flexible; Standard: 26 per year (1 per 2 weeks), 52 per year (1 per week)' not found — normalized to 'Fixed-Flexible; Standard: 26 per year (1 per 2 weeks); Optional: 52 per year (1 per week)'."
            ],
        )

    def test_resolve_frequency_creates_missing_simple_fixed_frequency(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")
        importer._load_lookups()
        stats = {"warnings": []}

        frequency = importer._resolve_frequency(
            self._record("Fixed; 9 per year"),
            label="record[2]",
            stats=stats,
        )

        self.assertIsNotNone(frequency)
        self.assertEqual(frequency.name, "Fixed; 9 per year")
        self.assertEqual(frequency.type, "Fixed")
        self.assertTrue(
            CollectionFrequency.objects.filter(name="Fixed; 9 per year").exists()
        )
        self.assertEqual(stats["warnings"], [])

    def test_resolve_frequency_silently_canonicalizes_simple_fixed_variant(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")
        importer._load_lookups()
        stats = {"warnings": []}

        frequency = importer._resolve_frequency(
            self._record("Fixed; 52 per year (1 per 2 week)"),
            label="record[2a]",
            stats=stats,
        )

        self.assertEqual(frequency, self.fixed_simple_frequency)
        self.assertEqual(stats["warnings"], [])

    def test_resolve_frequency_translates_misleading_bw_seasonal_label(self):
        importer = CollectionImporter(owner=self.owner, publication_status="private")
        importer._load_lookups()
        stats = {"warnings": []}

        frequency = importer._resolve_frequency(
            self._record(
                "Fixed-Seasonal; 39 per year (1 per 2 weeks from March - November)"
            ),
            label="record[3]",
            stats=stats,
        )

        self.assertEqual(frequency, self.seasonal_frequency)
        self.assertEqual(
            stats["warnings"],
            [
                "record[3]: CollectionFrequency 'Fixed-Seasonal; 39 per year (1 per 2 weeks from March - November)' not found — normalized to 'Seasonal; 19 per year (1 per 2 weeks from March - November, 0 from December - February)'."
            ],
        )


class ImprovedWorkbookLoadRecordsTestCase(TestCase):
    def _create_workbook(self, rows: list[list]) -> Path:
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(
            [
                "Catchment",
                "NUTS/LAU Id",
                "Collector",
                "Collection System",
                "Waste Category",
                "Valid from",
                "Valid until",
            ]
        )
        for row in rows:
            sheet.append(row)

        handle = NamedTemporaryFile(suffix=".xlsx", delete=False)
        handle.close()
        workbook.save(handle.name)
        return Path(handle.name)

    def test_load_records_accepts_iso_string_dates(self):
        workbook_path = self._create_workbook(
            [
                [
                    "Koblenz, Kreisfreie Stadt (DEB11)",
                    "DEB11",
                    "Kommunaler Servicebetrieb Koblenz",
                    "Door to door",
                    "Biowaste",
                    "2024-01-01",
                    "2024-12-31",
                ]
            ]
        )
        self.addCleanup(workbook_path.unlink)

        records, warnings, row_count = _load_records(workbook_path)

        self.assertEqual(row_count, 1)
        self.assertEqual(warnings, [])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["valid_from"], "2024-01-01")
        self.assertEqual(records[0]["valid_until"], "2024-12-31")
