import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from utils.properties.models import Unit

from ..models import (
    ComponentMeasurement,
    Composition,
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    Sample,
    SampleSeries,
    WeightShare,
)


class CompositionNormalizationMismatchReportCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="composition-report-owner",
            password="test123",
        )
        cls.material = Material.objects.create(
            name="Report Material",
            type="material",
            owner=cls.owner,
        )
        cls.series = SampleSeries.objects.create(
            name="Report Series",
            material=cls.material,
            owner=cls.owner,
        )
        cls.percent_unit = Unit.objects.filter(name="%").first()
        if cls.percent_unit is None:
            cls.percent_unit = Unit.objects.create(name="%", symbol="percent")
        elif not cls.percent_unit.symbol:
            cls.percent_unit.symbol = "percent"
            cls.percent_unit.save(update_fields=["symbol"])

    def test_command_reports_raw_persisted_mismatches(self):
        sample = self._create_sample_with_compositions(
            sample_name="Mismatched Sample",
            persisted_values=(Decimal("0.2"), Decimal("0.8")),
            raw_values=(Decimal("70"), Decimal("30")),
        )

        out = io.StringIO()
        call_command("report_composition_normalization_mismatches", stdout=out)

        output = out.getvalue()
        self.assertIn("samples_examined: 1", output)
        self.assertIn("samples_with_mismatches: 1", output)
        self.assertIn("groups_with_mismatches: 1", output)
        self.assertIn("Mismatched raw-derived groups:", output)
        self.assertIn(f"sample #{sample.pk} Mismatched Sample", output)
        self.assertIn("group #", output)

    def test_command_summary_only_omits_detail_rows(self):
        sample = self._create_sample_with_compositions(
            sample_name="Summary Mismatch",
            persisted_values=(Decimal("0.2"), Decimal("0.8")),
            raw_values=(Decimal("70"), Decimal("30")),
        )

        out = io.StringIO()
        call_command(
            "report_composition_normalization_mismatches",
            summary_only=True,
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("groups_with_mismatches: 1", output)
        self.assertNotIn(f"sample #{sample.pk} Summary Mismatch", output)

    def test_command_can_fail_on_mismatch(self):
        self._create_sample_with_compositions(
            sample_name="Failing Mismatch",
            persisted_values=(Decimal("0.2"), Decimal("0.8")),
            raw_values=(Decimal("70"), Decimal("30")),
        )

        out = io.StringIO()
        with self.assertRaisesMessage(
            CommandError,
            "1 composition groups differ from saved normalized values.",
        ):
            call_command(
                "report_composition_normalization_mismatches",
                fail_on_mismatch=True,
                stdout=out,
            )

    def test_command_can_limit_to_sample_id(self):
        mismatched_sample = self._create_sample_with_compositions(
            sample_name="Limited Mismatch",
            persisted_values=(Decimal("0.2"), Decimal("0.8")),
            raw_values=(Decimal("70"), Decimal("30")),
        )
        matched_sample = self._create_sample_with_compositions(
            sample_name="Limited Match",
            persisted_values=(Decimal("0.7"), Decimal("0.3")),
            raw_values=(Decimal("70"), Decimal("30")),
        )

        out = io.StringIO()
        call_command(
            "report_composition_normalization_mismatches",
            sample_id=[matched_sample.pk],
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("samples_examined: 1", output)
        self.assertIn("groups_with_mismatches: 0", output)
        self.assertNotIn(f"sample #{mismatched_sample.pk} Limited Mismatch", output)

    def _create_sample_with_compositions(
        self,
        *,
        sample_name,
        persisted_values,
        raw_values,
    ):
        sample = Sample.objects.create(
            name=sample_name,
            material=self.material,
            series=self.series,
            publication_status="published",
            owner=self.owner,
        )
        sample.compositions.all().delete()
        group = MaterialComponentGroup.objects.create(
            name=f"{sample_name} Group",
            publication_status="published",
            owner=self.owner,
        )
        first_component = MaterialComponent.objects.create(
            name=f"{sample_name} First Component",
            publication_status="published",
            owner=self.owner,
        )
        second_component = MaterialComponent.objects.create(
            name=f"{sample_name} Second Component",
            publication_status="published",
            owner=self.owner,
        )
        composition = Composition.objects.create(
            sample=sample,
            group=group,
            fractions_of=MaterialComponent.objects.default(),
            owner=self.owner,
        )
        WeightShare.objects.create(
            composition=composition,
            component=first_component,
            average=persisted_values[0],
            standard_deviation=Decimal("0.0"),
            owner=self.owner,
        )
        WeightShare.objects.create(
            composition=composition,
            component=second_component,
            average=persisted_values[1],
            standard_deviation=Decimal("0.0"),
            owner=self.owner,
        )
        ComponentMeasurement.objects.create(
            sample=sample,
            group=group,
            component=first_component,
            unit=self.percent_unit,
            average=raw_values[0],
            owner=self.owner,
        )
        ComponentMeasurement.objects.create(
            sample=sample,
            group=group,
            component=second_component,
            unit=self.percent_unit,
            average=raw_values[1],
            owner=self.owner,
        )
        return sample


class WeightShareBackfillCandidateReportCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(
            username="weightshare-backfill-owner",
            password="test123",
        )
        cls.material = Material.objects.create(
            name="Backfill Material",
            type="material",
            owner=cls.owner,
        )
        cls.series = SampleSeries.objects.create(
            name="Backfill Series",
            material=cls.material,
            owner=cls.owner,
        )
        cls.percent_unit = Unit.objects.filter(name="%").first()
        if cls.percent_unit is None:
            cls.percent_unit = Unit.objects.create(name="%", symbol="percent")
        elif not cls.percent_unit.symbol:
            cls.percent_unit.symbol = "percent"
            cls.percent_unit.save(update_fields=["symbol"])

    def test_command_reports_saved_groups_without_raw_measurements(self):
        candidate_sample = self._create_sample_with_saved_shares(
            sample_name="Candidate Sample",
        )
        raw_sample = self._create_sample_with_saved_shares(
            sample_name="Raw Covered Sample",
            add_raw_measurements=True,
        )

        out = io.StringIO()
        call_command(
            "report_weightshare_backfill_candidates",
            sample_id=[candidate_sample.pk, raw_sample.pk],
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("samples_examined: 2", output)
        self.assertIn("samples_with_backfill_candidates: 1", output)
        self.assertIn("groups_with_backfill_candidates: 1", output)
        self.assertIn("saved_weightshares_to_backfill: 2", output)
        self.assertIn("component_measurements_created: 0", output)
        self.assertIn("Saved normalized groups without raw measurements:", output)
        self.assertIn(f"sample #{candidate_sample.pk} Candidate Sample", output)
        self.assertNotIn(f"sample #{raw_sample.pk} Raw Covered Sample", output)
        self.assertEqual(candidate_sample.component_measurements.count(), 0)

    def test_command_apply_creates_component_measurements_from_saved_shares(self):
        sample = self._create_sample_with_saved_shares(sample_name="Apply Candidate")

        out = io.StringIO()
        call_command(
            "report_weightshare_backfill_candidates",
            sample_id=[sample.pk],
            apply=True,
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("component_measurements_created: 2", output)
        measurements = sample.component_measurements.order_by("component__name")
        self.assertEqual(measurements.count(), 2)
        self.assertEqual(measurements[0].average, Decimal("70.0000000000"))
        self.assertEqual(measurements[0].standard_deviation, Decimal("0E-10"))
        self.assertEqual(measurements[0].unit, self.percent_unit)
        self.assertEqual(
            measurements[0].basis_component,
            MaterialComponent.objects.default(),
        )
        self.assertEqual(measurements[0].owner, self.owner)
        self.assertEqual(measurements[1].average, Decimal("30.0000000000"))

    def test_command_apply_skips_groups_that_already_have_raw_measurements(self):
        sample = self._create_sample_with_saved_shares(
            sample_name="Apply Raw Covered",
            add_raw_measurements=True,
        )

        out = io.StringIO()
        call_command(
            "report_weightshare_backfill_candidates",
            sample_id=[sample.pk],
            apply=True,
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("component_measurements_created: 0", output)
        self.assertEqual(sample.component_measurements.count(), 1)

    def test_command_summary_only_omits_detail_rows(self):
        sample = self._create_sample_with_saved_shares(sample_name="Summary Candidate")

        out = io.StringIO()
        call_command(
            "report_weightshare_backfill_candidates",
            sample_id=[sample.pk],
            summary_only=True,
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("groups_with_backfill_candidates: 1", output)
        self.assertNotIn(f"sample #{sample.pk} Summary Candidate", output)

    def test_command_can_limit_to_sample_id(self):
        candidate_sample = self._create_sample_with_saved_shares(
            sample_name="Limited Candidate",
        )
        raw_sample = self._create_sample_with_saved_shares(
            sample_name="Limited Raw Covered",
            add_raw_measurements=True,
        )

        out = io.StringIO()
        call_command(
            "report_weightshare_backfill_candidates",
            sample_id=[raw_sample.pk],
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("samples_examined: 1", output)
        self.assertIn("groups_with_backfill_candidates: 0", output)
        self.assertNotIn(f"sample #{candidate_sample.pk} Limited Candidate", output)

    def test_command_can_fail_on_candidates(self):
        sample = self._create_sample_with_saved_shares(sample_name="Failing Candidate")

        out = io.StringIO()
        with self.assertRaisesMessage(
            CommandError,
            "1 composition groups need raw measurement backfill.",
        ):
            call_command(
                "report_weightshare_backfill_candidates",
                sample_id=[sample.pk],
                fail_on_candidates=True,
                stdout=out,
            )

    def _create_sample_with_saved_shares(
        self,
        *,
        sample_name,
        add_raw_measurements=False,
    ):
        sample = Sample.objects.create(
            name=sample_name,
            material=self.material,
            series=self.series,
            publication_status="published",
            owner=self.owner,
        )
        sample.compositions.all().delete()
        group = MaterialComponentGroup.objects.create(
            name=f"{sample_name} Group",
            publication_status="published",
            owner=self.owner,
        )
        first_component = MaterialComponent.objects.create(
            name=f"{sample_name} First Component",
            publication_status="published",
            owner=self.owner,
        )
        second_component = MaterialComponent.objects.create(
            name=f"{sample_name} Second Component",
            publication_status="published",
            owner=self.owner,
        )
        composition = Composition.objects.create(
            sample=sample,
            group=group,
            fractions_of=MaterialComponent.objects.default(),
            owner=self.owner,
        )
        WeightShare.objects.create(
            composition=composition,
            component=first_component,
            average=Decimal("0.7"),
            standard_deviation=Decimal("0.0"),
            owner=self.owner,
        )
        WeightShare.objects.create(
            composition=composition,
            component=second_component,
            average=Decimal("0.3"),
            standard_deviation=Decimal("0.0"),
            owner=self.owner,
        )
        if add_raw_measurements:
            ComponentMeasurement.objects.create(
                sample=sample,
                group=group,
                component=first_component,
                unit=self.percent_unit,
                average=Decimal("70"),
                owner=self.owner,
            )
        return sample
