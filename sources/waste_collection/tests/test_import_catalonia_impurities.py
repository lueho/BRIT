import csv
from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from maps.models import LauRegion
from sources.waste_collection.models import (
    Collection,
    CollectionCatchment,
    CollectionPropertyValue,
    CollectionSystem,
    WasteCategory,
)
from utils.properties.models import Property, Unit


class ImportCataloniaImpuritiesCommandTests(TestCase):
    headers = (
        "codi",
        "Catchment",
        "Waste_Category",
        "Collection_system_2024",
        "Impurities_percentage_2024",
        "Sources",
    )

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="catalonia-importer")
        cls.biowaste, _ = WasteCategory.objects.get_or_create(name="Biowaste")
        cls.residual, _ = WasteCategory.objects.get_or_create(name="Residual waste")
        cls.bring_point, _ = CollectionSystem.objects.get_or_create(name="Bring point")
        cls.impurity_property, _ = Property.objects.get_or_create(
            name="biowaste impurity rate"
        )
        cls.percent, _ = Unit.objects.get_or_create(name="%")
        cls.impurity_property.allowed_units.add(cls.percent)

    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

    def create_collection(self, lau_id="08001", name="Abrera"):
        lau = LauRegion.objects.create(
            name=name,
            lau_name=name,
            lau_id=lau_id,
            cntr_code="ES",
            year=2024,
        )
        catchment = CollectionCatchment.objects.create(
            name=f"{name} ({lau_id})",
            region=lau.region_ptr,
            owner=self.owner,
            publication_status="review",
        )
        return Collection.objects.create(
            name=f"{name} Biowaste collection",
            catchment=catchment,
            collection_system=self.bring_point,
            waste_category=self.biowaste,
            valid_from=date(2024, 1, 1),
            owner=self.owner,
            publication_status="review",
        )

    def write_csv(self, rows, encoding="cp1252"):
        path = Path(self.temporary_directory.name) / "catalonia.tsv"
        with path.open("w", encoding=encoding, newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.headers, delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)
        return path

    def row(self, **overrides):
        row = {
            "codi": "80018",
            "Catchment": "Abrera",
            "Waste_Category": "Biowaste",
            "Collection_system_2024": "Bring point",
            "Impurities_percentage_2024": "13.86",
            "Sources": "https://example.com/informe-gestió.pdf",
        }
        row.update(overrides)
        return row

    def run_command(self, path, **options):
        stdout = StringIO()
        call_command(
            "import_catalonia_impurities",
            str(path),
            owner=self.owner.username,
            stdout=stdout,
            **options,
        )
        return stdout.getvalue()

    def test_imports_cp1252_tsv_and_maps_catalan_code_to_lau(self):
        collection = self.create_collection()
        path = self.write_csv([self.row()])

        output = self.run_command(path)

        value = CollectionPropertyValue.objects.get(
            collection=collection,
            property=self.impurity_property,
            year=2024,
            is_derived=False,
        )
        self.assertEqual(value.average, 13.86)
        self.assertEqual(value.unit, self.percent)
        self.assertEqual(value.publication_status, "review")
        self.assertIsNotNone(value.submitted_at)
        self.assertEqual(
            list(value.sources.values_list("url", flat=True)),
            ["https://example.com/informe-gesti%C3%B3.pdf"],
        )
        self.assertEqual(value.sources.get().publication_status, "review")
        self.assertIn("1 created", output)

    def test_updates_existing_value_and_preserves_existing_source(self):
        collection = self.create_collection()
        value = CollectionPropertyValue.objects.create(
            name="Old impurity value",
            collection=collection,
            property=self.impurity_property,
            unit=self.percent,
            year=2024,
            average=6.8,
            owner=self.owner,
            publication_status="review",
        )
        path = self.write_csv([self.row(Impurities_percentage_2024="6.86")])

        output = self.run_command(path)

        value.refresh_from_db()
        self.assertEqual(value.average, 6.86)
        self.assertEqual(value.sources.count(), 1)
        self.assertIn("1 updated", output)

    def test_repairs_source_url_with_missing_initial_h_and_reports_it(self):
        collection = self.create_collection()
        path = self.write_csv([self.row(Sources="ttps://example.com/report.pdf")])

        output = self.run_command(path)

        value = CollectionPropertyValue.objects.get(collection=collection)
        self.assertEqual(
            list(value.sources.values_list("url", flat=True)),
            ["https://example.com/report.pdf"],
        )
        self.assertIn("corrected source URL", output)

    def test_dry_run_reports_changes_and_rolls_them_back(self):
        self.create_collection()
        path = self.write_csv([self.row()])

        output = self.run_command(path, dry_run=True)

        self.assertFalse(CollectionPropertyValue.objects.exists())
        self.assertIn("DRY RUN", output)
        self.assertIn("1 created", output)

    def test_ignores_non_biowaste_and_blank_impurity_rows(self):
        self.create_collection()
        path = self.write_csv(
            [
                self.row(Waste_Category="Residual waste"),
                self.row(Impurities_percentage_2024=""),
            ]
        )

        output = self.run_command(path)

        self.assertFalse(CollectionPropertyValue.objects.exists())
        self.assertIn("0 eligible rows", output)

    def test_mapping_error_rolls_back_all_rows(self):
        self.create_collection()
        path = self.write_csv(
            [self.row(), self.row(codi="999999", Catchment="Missing municipality")]
        )

        with self.assertRaisesMessage(
            CommandError, "No active 2024 Biowaste collection"
        ):
            self.run_command(path)

        self.assertFalse(CollectionPropertyValue.objects.exists())
