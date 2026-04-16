from decimal import Decimal

from django.test import TestCase

from utils.properties.models import Unit

from ..filters import SampleFilter
from ..models import (
    ComponentMeasurement,
    Material,
    MaterialCategory,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialProperty,
    MaterialPropertyValue,
    Sample,
    get_sample_substrate_category_name,
)


class SampleFilterTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        substrate_category_name = get_sample_substrate_category_name()
        cls.complex_substrate_category, _ = MaterialCategory.objects.get_or_create(
            name=substrate_category_name,
        )
        cls.other_category, _ = MaterialCategory.objects.get_or_create(
            name="Simple component"
        )

        cls.substrate_material = Material.objects.create(name="Food waste mix")
        cls.substrate_material.categories.add(cls.complex_substrate_category)

        cls.non_substrate_material = Material.objects.create(name="Amino Acids")
        cls.non_substrate_material.categories.add(cls.other_category)

        cls.sample_substrate = Sample.objects.create(
            name="Sample A",
            material=cls.substrate_material,
        )
        cls.sample_non_substrate = Sample.objects.create(
            name="Sample B",
            material=cls.non_substrate_material,
        )

        cls.parameter_n = MaterialProperty.objects.create(name="Nitrogen")
        cls.parameter_k = MaterialProperty.objects.create(name="Potassium")
        cls.organic_matter_property = MaterialProperty.objects.create(
            name="Organic matter",
            unit="%",
        )
        cls.volatile_solids_property = MaterialProperty.objects.create(
            name="Volatile solids",
            unit="%",
            comparable_property=cls.organic_matter_property,
        )

        n_value = MaterialPropertyValue.objects.create(
            property=cls.parameter_n,
            average=Decimal("10"),
            standard_deviation=Decimal("0"),
        )
        k_value = MaterialPropertyValue.objects.create(
            property=cls.parameter_k,
            average=Decimal("20"),
            standard_deviation=Decimal("0"),
        )
        cls.sample_substrate.properties.add(n_value)
        cls.sample_non_substrate.properties.add(k_value)
        cls.sample_equivalent = Sample.objects.create(
            name="Sample C",
            material=cls.substrate_material,
        )
        cls.sample_substrate.properties.add(
            MaterialPropertyValue.objects.create(
                property=cls.organic_matter_property,
                average=Decimal("55"),
                standard_deviation=Decimal("0"),
            )
        )
        cls.sample_equivalent.properties.add(
            MaterialPropertyValue.objects.create(
                property=cls.volatile_solids_property,
                average=Decimal("60"),
                standard_deviation=Decimal("0"),
            )
        )

        cls.raw_parameter_group = MaterialComponentGroup.objects.create(
            name="Organic fraction",
        )
        cls.organic_matter = MaterialComponent.objects.create(name="Organic matter")
        cls.volatile_solids = MaterialComponent.objects.create(
            name="Volatile solids",
            comparable_component=cls.organic_matter,
        )
        unit_percent = Unit.objects.filter(name="%").first()
        if unit_percent is None:
            unit_percent = Unit.objects.create(name="%")
        ComponentMeasurement.objects.create(
            sample=cls.sample_substrate,
            group=cls.raw_parameter_group,
            component=cls.organic_matter,
            unit=unit_percent,
            average=Decimal("55"),
            standard_deviation=Decimal("0"),
        )
        ComponentMeasurement.objects.create(
            sample=cls.sample_equivalent,
            group=cls.raw_parameter_group,
            component=cls.volatile_solids,
            unit=unit_percent,
            average=Decimal("60"),
            standard_deviation=Decimal("0"),
        )

    def test_filter_form_has_no_formtags(self):
        filtr = SampleFilter(queryset=Sample.objects.all())
        self.assertFalse(filtr.form.helper.form_tag)

    def test_filter_form_contains_substrate_material_and_parameter_fields(self):
        filtr = SampleFilter(queryset=Sample.objects.all())

        self.assertIn("substrate_material", filtr.form.fields)
        self.assertIn("parameter", filtr.form.fields)
        self.assertIn("raw_parameter", filtr.form.fields)
        self.assertEqual(
            filtr.form.fields["substrate_material"].label,
            "Substrate material",
        )
        self.assertEqual(filtr.form.fields["parameter"].label, "Parameter")
        self.assertEqual(filtr.form.fields["raw_parameter"].label, "Raw parameter")

    def test_parameter_filter_matches_sample_owned_property_values(self):
        sample_owned = Sample.objects.create(
            name="Sample D",
            material=self.substrate_material,
        )
        MaterialPropertyValue.objects.create(
            sample=sample_owned,
            property=self.parameter_n,
            average=Decimal("15"),
            standard_deviation=Decimal("0"),
        )

        filtr = SampleFilter(
            data={"parameter": self.parameter_n.pk},
            queryset=Sample.objects.all(),
        )

        self.assertIn(sample_owned, filtr.qs)

    def test_substrate_material_queryset_only_contains_complex_substrates(self):
        filtr = SampleFilter(queryset=Sample.objects.all())

        substrate_queryset = filtr.filters["substrate_material"].queryset
        self.assertIn(self.substrate_material, substrate_queryset)
        self.assertNotIn(self.non_substrate_material, substrate_queryset)

    def test_substrate_material_filter_filters_samples(self):
        filtr = SampleFilter(
            data={"substrate_material": str(self.substrate_material.pk)},
            queryset=Sample.objects.all(),
        )

        self.assertCountEqual(
            list(filtr.qs),
            [self.sample_substrate, self.sample_equivalent],
        )

    def test_parameter_filter_filters_samples(self):
        filtr = SampleFilter(
            data={"parameter": str(self.parameter_n.pk)},
            queryset=Sample.objects.all(),
        )

        self.assertEqual(list(filtr.qs), [self.sample_substrate])

    def test_parameter_filter_matches_equivalent_properties(self):
        filtr = SampleFilter(
            data={"parameter": str(self.organic_matter_property.pk)},
            queryset=Sample.objects.all(),
        )

        self.assertCountEqual(
            list(filtr.qs),
            [self.sample_substrate, self.sample_equivalent],
        )

    def test_parameter_filter_resolves_alias_to_canonical_property(self):
        filtr = SampleFilter(
            data={"parameter": str(self.volatile_solids_property.pk)},
            queryset=Sample.objects.all(),
        )

        self.assertCountEqual(
            list(filtr.qs),
            [self.sample_substrate, self.sample_equivalent],
        )

    def test_raw_parameter_filter_matches_equivalent_components(self):
        filtr = SampleFilter(
            data={"raw_parameter": str(self.organic_matter.pk)},
            queryset=Sample.objects.all(),
        )

        self.assertCountEqual(
            list(filtr.qs),
            [self.sample_substrate, self.sample_equivalent],
        )

    def test_raw_parameter_filter_resolves_alias_to_canonical_component(self):
        filtr = SampleFilter(
            data={"raw_parameter": str(self.volatile_solids.pk)},
            queryset=Sample.objects.all(),
        )

        self.assertCountEqual(
            list(filtr.qs),
            [self.sample_substrate, self.sample_equivalent],
        )

    def test_missing_substrate_category_is_created(self):
        substrate_category_name = get_sample_substrate_category_name()
        MaterialCategory.objects.filter(name=substrate_category_name).delete()

        SampleFilter(queryset=Sample.objects.all())

        self.assertTrue(
            MaterialCategory.objects.filter(name=substrate_category_name).exists()
        )
