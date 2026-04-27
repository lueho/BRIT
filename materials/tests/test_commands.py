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
