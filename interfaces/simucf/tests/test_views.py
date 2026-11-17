from decimal import Decimal

from django.urls import reverse

from materials.models import (
    ComponentMeasurement,
    Composition,
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    Sample,
    SampleSeries,
)
from utils.properties.models import Unit
from utils.tests.testcases import ViewWithPermissionsTestCase

from ..models import InputMaterial


class SimuCFModelFormViewTestCase(ViewWithPermissionsTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name="Test Material")
        series = SampleSeries.objects.create(name="Test Series", material=material)
        sample = Sample.objects.create(
            name="Test Sample",
            material=material,
            series=series,
            publication_status="published",
        )
        cls.sample_pk = sample.pk
        group = MaterialComponentGroup.objects.create(name="Biochemical Composition")
        composition = Composition.objects.create(group=group, sample=sample)
        component_names = [
            "Carbohydrates",
            "Amino Acids",
            "Starches",
            "Hemicellulose",
            "Fats",
            "Waxes",
            "Proteins",
            "Cellulose",
            "Lignin",
        ]
        percent_unit = Unit.objects.filter(name="%").first() or Unit.objects.create(
            name="%", symbol="percent"
        )
        for name in component_names:
            component = MaterialComponent.objects.create(name=name)
            ComponentMeasurement.objects.create(
                sample=composition.sample,
                group=composition.group,
                component=component,
                unit=percent_unit,
                average=Decimal("70"),
            )

        private_sample = Sample.objects.create(
            name="Private Test Sample",
            material=material,
            series=series,
            owner=cls.owner,
            publication_status="private",
        )
        private_composition = Composition.objects.create(
            group=group, sample=private_sample
        )
        ComponentMeasurement.objects.create(
            sample=private_sample,
            group=private_composition.group,
            component=MaterialComponent.objects.get(name="Carbohydrates"),
            unit=percent_unit,
            average=Decimal("70"),
        )
        cls.private_input_material_pk = private_sample.pk

        cls.input_material = InputMaterial.objects.get(pk=cls.sample_pk)

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse("simucf-form"))
        self.assertEqual(200, response.status_code)

    def test_get_returns_file(self):
        data = {
            "input_material": self.input_material.id,
            "amount": 100,
            "length_of_treatment": 30,
        }
        response = self.client.post(reverse("simucf-form"), data=data)
        self.assertEqual(
            response.get("Content-Disposition"),
            'attachment; filename="simucf-input.txt"',
        )

    def test_private_input_material_is_hidden_and_rejected_for_anonymous_user(self):
        url = reverse("simucf-form")
        get_response = self.client.get(url)
        self.assertNotContains(get_response, "Private Test Sample")

        post_response = self.client.post(
            url,
            data={
                "input_material": self.private_input_material_pk,
                "amount": 100,
                "length_of_treatment": 30,
            },
        )

        self.assertEqual(post_response.status_code, 200)
        self.assertTrue(post_response.context["form"].errors)
        self.assertNotIn("Content-Disposition", post_response)
