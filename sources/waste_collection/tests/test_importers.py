"""Tests for sources.waste_collection.importers."""

from datetime import date

from django.contrib.auth import get_user_model
from django.db.models import signals
from django.test import TestCase
from factory.django import mute_signals

from bibliography.models import Source
from materials.models import Material

from ..importers import CollectionImporter
from ..models import (
    Collection,
    CollectionCatchment,
    CollectionFrequency,
    CollectionSystem,
    Collector,
    WasteCategory,
    WasteFlyer,
)
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
            "sorting_method": None,
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
