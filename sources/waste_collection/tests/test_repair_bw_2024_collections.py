from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile

import openpyxl
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from bibliography.models import Source
from sources.waste_collection.management.commands.import_bw_2024_collections import _COL
from sources.waste_collection.models import (
    Collection,
    CollectionCatchment,
    CollectionSystem,
    WasteCategory,
    WasteFlyer,
)

User = get_user_model()


@override_settings(AUTO_ENQUEUE_URL_CHECKS=False)
class RepairBW2024CollectionsCommandTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="bw-repair-owner")
        cls.catchment = CollectionCatchment.objects.create(name="BW Repair Catchment")
        cls.other_catchment = CollectionCatchment.objects.create(
            name="BW Repair Catchment Two"
        )
        cls.collection_system = CollectionSystem.objects.create(name="Door to door")
        cls.waste_category = WasteCategory.objects.create(name="Biowaste")

    def setUp(self):
        self.workbook_path = self._create_workbook(
            [
                self._make_bw_row(
                    catchment_name=self.catchment.name,
                    source_note="Workbook note",
                    flyer_url="https://example.org/workbook-flyer.pdf",
                ),
                self._make_bw_row(
                    catchment_name=self.other_catchment.name,
                    valid_from=date(2024, 10, 1),
                    source_note="Second row note",
                    flyer_url="https://example.org/second-row.pdf",
                ),
            ]
        )

    def tearDown(self):
        if self.workbook_path.exists():
            self.workbook_path.unlink()

    def _make_bw_row(
        self,
        *,
        catchment_name: str,
        valid_from: date = date(2024, 1, 1),
        source_note: str = "",
        flyer_url: str = "",
    ) -> list:
        row = [None] * 43
        row[_COL["catchment_name"]] = catchment_name
        row[_COL["collection_system"]] = self.collection_system.name
        row[_COL["waste_category"]] = self.waste_category.name
        row[_COL["valid_from"]] = valid_from
        if flyer_url:
            row[_COL["sources"]] = flyer_url
        if source_note:
            row[_COL["sources_new"]] = source_note
        return row

    def _create_workbook(self, data_rows: list[list]) -> Path:
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append([f"Column {index}" for index in range(43)])
        for row in data_rows:
            sheet.append(row)

        handle = NamedTemporaryFile(suffix=".xlsx", delete=False)
        handle.close()
        workbook.save(handle.name)
        return Path(handle.name)

    def test_command_repairs_existing_collection_source_and_flyer_links(self):
        collection = Collection.objects.create(
            owner=self.owner,
            publication_status="private",
            catchment=self.catchment,
            collection_system=self.collection_system,
            waste_category=self.waste_category,
            valid_from=date(2024, 1, 1),
        )
        stale_source = Source.objects.create(
            owner=self.owner,
            publication_status="private",
            type="custom",
            title="Stale note",
        )
        stale_flyer = WasteFlyer.objects.create(
            owner=self.owner,
            publication_status="private",
            title="example.org",
            url="https://example.org/stale-flyer.pdf",
        )
        collection.sources.add(stale_source)
        collection.flyers.add(stale_flyer)

        stdout = StringIO()
        call_command(
            "repair_bw_2024_collections",
            file=str(self.workbook_path),
            owner=self.owner.username,
            stdout=stdout,
        )

        collection.refresh_from_db()
        self.assertEqual(
            set(collection.sources.values_list("title", flat=True)),
            {"Workbook note"},
        )
        self.assertEqual(
            set(collection.flyers.values_list("url", flat=True)),
            {"https://example.org/workbook-flyer.pdf"},
        )
        self.assertIn("Collections updated:  1", stdout.getvalue())

    def test_command_can_target_specific_excel_rows_in_dry_run(self):
        stdout = StringIO()
        call_command(
            "repair_bw_2024_collections",
            file=str(self.workbook_path),
            owner=self.owner.username,
            excel_row=[3],
            dry_run=True,
            stdout=stdout,
        )

        self.assertEqual(Collection.objects.filter(owner=self.owner).count(), 0)
        output = stdout.getvalue()
        self.assertIn("Targeting Excel row(s): 3", output)
        self.assertIn("Loaded 1 valid record(s)", output)
        self.assertIn("Collections created:  1", output)
