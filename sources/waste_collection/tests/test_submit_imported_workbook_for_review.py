from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile

import openpyxl
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from bibliography.models import Source
from sources.waste_collection.models import (
    Collection,
    CollectionCatchment,
    CollectionPropertyValue,
    CollectionSystem,
    WasteCategory,
    WasteFlyer,
)
from utils.object_management.models import ReviewAction
from utils.properties.models import Property, Unit

User = get_user_model()


@override_settings(AUTO_ENQUEUE_URL_CHECKS=False)
class SubmitImportedWorkbookForReviewCommandTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="tobi")
        cls.other_owner = User.objects.create_user(username="other-owner")
        cls.catchment = CollectionCatchment.objects.create(name="Thueringen Catchment")
        cls.collection_system = CollectionSystem.objects.create(name="Brown Bin")
        cls.waste_category = WasteCategory.objects.create(name="Biowaste")
        cls.property, _ = Property.objects.get_or_create(
            id=1,
            defaults={"name": "Specific waste collected"},
        )
        cls.unit, _ = Unit.objects.get_or_create(name="kg/(cap.*a)")

    def setUp(self):
        self.workbook_path = self._create_workbook()

    def tearDown(self):
        if self.workbook_path.exists():
            self.workbook_path.unlink()

    def _create_workbook(self) -> Path:
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(
            [
                "Catchment",
                "Collection System",
                "Waste Category",
                "Valid from",
                "Allowed Materials",
                "Forbidden Materials",
                "Weblinks",
                "Sources_new",
                "Specific Waste Collected 2020",
                "Specific Waste Collected 2020 Unit",
            ]
        )
        sheet.append(
            [
                self.catchment.name,
                self.collection_system.name,
                self.waste_category.name,
                date(2024, 1, 1),
                "",
                "",
                "https://thueringen.example.org/imported-flyer.pdf",
                "Thüringen Imported Note",
                12.3,
                self.unit.name,
            ]
        )

        handle = NamedTemporaryFile(suffix=".xlsx", delete=False)
        handle.close()
        workbook.save(handle.name)
        return Path(handle.name)

    def _create_matching_collection(self, owner):
        return Collection.objects.create(
            owner=owner,
            publication_status="private",
            catchment=self.catchment,
            collection_system=self.collection_system,
            waste_category=self.waste_category,
            valid_from=date(2024, 1, 1),
        )

    def test_command_submits_only_matching_tobi_owned_import_objects(self):
        collection = self._create_matching_collection(self.owner)
        imported_source = Source.objects.create(
            owner=self.owner,
            publication_status="private",
            type="custom",
            title="Thüringen Imported Note",
        )
        extra_source = Source.objects.create(
            owner=self.owner,
            publication_status="private",
            type="custom",
            title="Not In Workbook",
        )
        imported_flyer = WasteFlyer.objects.create(
            owner=self.owner,
            publication_status="private",
            title="thueringen.example.org",
            url="https://thueringen.example.org/imported-flyer.pdf",
        )
        extra_flyer = WasteFlyer.objects.create(
            owner=self.owner,
            publication_status="private",
            title="thueringen.example.org",
            url="https://thueringen.example.org/not-imported.pdf",
        )
        collection.sources.add(imported_source, extra_source)
        collection.flyers.add(imported_flyer, extra_flyer)

        cpv = CollectionPropertyValue.objects.create(
            name="Thueringen CPV",
            owner=self.owner,
            publication_status="private",
            collection=collection,
            property=self.property,
            unit=self.unit,
            year=2020,
            average=12.3,
        )

        other_collection = self._create_matching_collection(self.other_owner)
        other_cpv = CollectionPropertyValue.objects.create(
            name="Other Owner CPV",
            owner=self.other_owner,
            publication_status="private",
            collection=other_collection,
            property=self.property,
            unit=self.unit,
            year=2020,
            average=12.3,
        )

        stdout = StringIO()
        call_command(
            "submit_imported_workbook_for_review",
            file=str(self.workbook_path),
            owner=self.owner.username,
            stdout=stdout,
        )

        collection.refresh_from_db()
        imported_source.refresh_from_db()
        extra_source.refresh_from_db()
        imported_flyer.refresh_from_db()
        extra_flyer.refresh_from_db()
        cpv.refresh_from_db()
        other_collection.refresh_from_db()
        other_cpv.refresh_from_db()

        self.assertEqual(collection.publication_status, "review")
        self.assertEqual(imported_source.publication_status, "review")
        self.assertEqual(imported_flyer.publication_status, "review")
        self.assertEqual(cpv.publication_status, "review")

        self.assertEqual(extra_source.publication_status, "private")
        self.assertEqual(extra_flyer.publication_status, "private")
        self.assertEqual(other_collection.publication_status, "private")
        self.assertEqual(other_cpv.publication_status, "private")

        self.assertTrue(
            ReviewAction.for_object(collection)
            .filter(action=ReviewAction.ACTION_SUBMITTED)
            .exists()
        )
        self.assertTrue(
            ReviewAction.for_object(imported_source)
            .filter(action=ReviewAction.ACTION_SUBMITTED)
            .exists()
        )
        self.assertTrue(
            ReviewAction.for_object(imported_flyer)
            .filter(action=ReviewAction.ACTION_SUBMITTED)
            .exists()
        )
        self.assertTrue(
            ReviewAction.for_object(cpv)
            .filter(action=ReviewAction.ACTION_SUBMITTED)
            .exists()
        )
        self.assertFalse(
            ReviewAction.for_object(extra_source)
            .filter(action=ReviewAction.ACTION_SUBMITTED)
            .exists()
        )
        self.assertFalse(
            ReviewAction.for_object(extra_flyer)
            .filter(action=ReviewAction.ACTION_SUBMITTED)
            .exists()
        )

        self.assertIn("Collections matched:      1", stdout.getvalue())
