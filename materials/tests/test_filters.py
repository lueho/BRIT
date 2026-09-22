from datetime import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from utils.properties.models import Unit

from ..filters import (
    MaterialComponentGroupListFilter,
    MaterialComponentListFilter,
    MaterialListFilter,
    MaterialPropertyListFilter,
    SampleFilter,
    SampleGroupFilter,
    SampleSeriesFilter,
)
from ..models import (
    AnalyticalMethod,
    ComponentMeasurement,
    Composition,
    Material,
    MaterialCategory,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialProperty,
    MaterialPropertyValue,
    Sample,
    SampleGroup,
    SampleSeries,
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
        )
        cls.volatile_solids_property = MaterialProperty.objects.create(
            name="Volatile solids",
            comparable_property=cls.organic_matter_property,
        )

        n_value = MaterialPropertyValue.objects.create(
            property=cls.parameter_n,
            average=Decimal("10"),
            standard_deviation=Decimal("0"),
        )
        MaterialPropertyValue.objects.create(
            sample=cls.sample_non_substrate,
            property=cls.parameter_k,
            average=Decimal("20"),
            standard_deviation=Decimal("0"),
        )
        n_value.sample = cls.sample_substrate
        n_value.save(update_fields=["sample"])
        cls.sample_equivalent = Sample.objects.create(
            name="Sample C",
            material=cls.substrate_material,
        )
        MaterialPropertyValue.objects.create(
            sample=cls.sample_substrate,
            property=cls.organic_matter_property,
            average=Decimal("55"),
            standard_deviation=Decimal("0"),
        )
        MaterialPropertyValue.objects.create(
            sample=cls.sample_equivalent,
            property=cls.volatile_solids_property,
            average=Decimal("60"),
            standard_deviation=Decimal("0"),
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

    def test_filter_form_uses_semantic_measurement_labels_and_guidance(self):
        filtr = SampleFilter(queryset=Sample.objects.all())

        self.assertIn("substrate_material", filtr.form.fields)
        self.assertIn("parameter", filtr.form.fields)
        self.assertIn("raw_parameter", filtr.form.fields)
        self.assertEqual(
            filtr.form.fields["substrate_material"].label,
            "Substrate material",
        )
        self.assertEqual(filtr.form.fields["parameter"].label, "Material property")
        self.assertEqual(
            filtr.form.fields["parameter"].help_text,
            "Filter by non-mass characteristics, such as pH or calorific value.",
        )
        self.assertEqual(
            filtr.form.fields["raw_parameter"].label,
            "Composition component",
        )
        self.assertEqual(
            filtr.form.fields["raw_parameter"].help_text,
            "Filter by a component mass fraction used in material-flow analysis, such as nitrogen.",
        )

    def test_sample_date_filter_uses_sample_datetime_with_date_picker(self):
        sample_taken_in_range = Sample.objects.create(
            name="Sample taken in range",
            material=self.substrate_material,
            datetime=timezone.make_aware(datetime(2024, 5, 15, 10, 30)),
        )
        sample_taken_outside_range = Sample.objects.create(
            name="Sample taken outside range",
            material=self.substrate_material,
            datetime=timezone.make_aware(datetime(2023, 5, 15, 10, 30)),
        )

        filtr = SampleFilter(
            data={
                "sample_date_after": "2024-05-01",
                "sample_date_before": "2024-05-31",
            },
            queryset=Sample.objects.all(),
        )

        self.assertEqual(filtr.form.fields["sample_date"].label, "Sample date")
        self.assertEqual(
            filtr.form.fields["sample_date"].widget.suffixes, ["after", "before"]
        )
        self.assertEqual(filtr.form.fields["sample_date"].widget.attrs["type"], "date")
        self.assertEqual(list(filtr.qs), [sample_taken_in_range])
        self.assertNotIn(sample_taken_outside_range, filtr.qs)

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

    def test_substrate_material_queryset_contains_complex_or_sampled_materials(self):
        filtr = SampleFilter(queryset=Sample.objects.all())

        substrate_queryset = filtr.filters["substrate_material"].queryset
        self.assertIn(self.substrate_material, substrate_queryset)
        self.assertIn(self.non_substrate_material, substrate_queryset)

    def test_substrate_material_filter_accepts_material_with_samples_outside_substrate_category(
        self,
    ):
        material = Material.objects.create(name="Sampled non-substrate material")
        sample = Sample.objects.create(
            name="Published sampled non-substrate",
            material=material,
            publication_status="published",
        )

        filtr = SampleFilter(
            data={"substrate_material": material.pk, "scope": "published"},
            queryset=Sample.objects.all(),
        )

        self.assertTrue(filtr.form.is_valid())
        self.assertIn(sample, filtr.qs)

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

    def test_component_group_filter_returns_samples_with_measurements_or_compositions_in_group(
        self,
    ):
        composition_sample = Sample.objects.create(
            name="Sample with composition",
            material=self.substrate_material,
        )
        Composition.objects.create(
            owner=composition_sample.owner,
            sample=composition_sample,
            group=self.raw_parameter_group,
            fractions_of=self.organic_matter,
        )

        filtr = SampleFilter(
            data={"component_group": str(self.raw_parameter_group.pk)},
            queryset=Sample.objects.all(),
        )

        self.assertCountEqual(
            list(filtr.qs),
            [self.sample_substrate, self.sample_equivalent, composition_sample],
        )

    def test_missing_substrate_category_is_created(self):
        substrate_category_name = get_sample_substrate_category_name()
        MaterialCategory.objects.filter(name=substrate_category_name).delete()

        SampleFilter(queryset=Sample.objects.all())

        self.assertTrue(
            MaterialCategory.objects.filter(name=substrate_category_name).exists()
        )

    def test_filter_form_contains_free_text_search_field(self):
        filtr = SampleFilter(queryset=Sample.objects.all())

        self.assertIn("q", filtr.form.fields)
        self.assertEqual(filtr.form.fields["q"].label, "Search")

    def test_q_matches_sample_name(self):
        filtr = SampleFilter(
            data={"q": "Sample B"},
            queryset=Sample.objects.all(),
        )

        self.assertEqual(list(filtr.qs), [self.sample_non_substrate])

    def test_q_matches_related_material_name(self):
        filtr = SampleFilter(
            data={"q": "Food"},
            queryset=Sample.objects.all(),
        )

        self.assertCountEqual(
            list(filtr.qs),
            [self.sample_substrate, self.sample_equivalent],
        )

    def test_q_combines_with_other_filters(self):
        filtr = SampleFilter(
            data={
                "q": "Sample",
                "substrate_material": str(self.substrate_material.pk),
            },
            queryset=Sample.objects.all(),
        )

        self.assertCountEqual(
            list(filtr.qs),
            [self.sample_substrate, self.sample_equivalent],
        )

    def test_q_blank_value_returns_all_samples(self):
        filtr = SampleFilter(
            data={"q": "   "},
            queryset=Sample.objects.all(),
        )

        self.assertCountEqual(list(filtr.qs), list(Sample.objects.all()))

    def test_q_no_match_returns_empty(self):
        filtr = SampleFilter(
            data={"q": "no-such-sample"},
            queryset=Sample.objects.all(),
        )

        self.assertEqual(list(filtr.qs), [])


class SampleGroupFilterTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.material_a = Material.objects.create(name="Group Filter Material A")
        cls.material_b = Material.objects.create(name="Group Filter Material B")
        cls.sample_a = Sample.objects.create(
            name="Grouped sample A", material=cls.material_a
        )
        cls.sample_b = Sample.objects.create(
            name="Grouped sample B", material=cls.material_b
        )
        cls.sample_unrelated = Sample.objects.create(
            name="Ungrouped sample", material=cls.material_a
        )
        cls.group = SampleGroup.objects.create(
            name="Experiment group", kind="experiment"
        )
        cls.other_group = SampleGroup.objects.create(name="Study group", kind="study")
        cls.sample_a.sample_groups.add(cls.group)
        cls.sample_b.sample_groups.add(cls.group)
        cls.sample_unrelated.sample_groups.add(cls.other_group)

    def test_sample_group_filter_returns_members_across_materials(self):
        filtr = SampleFilter(
            data={"sample_group": str(self.group.pk)},
            queryset=Sample.objects.all(),
        )

        self.assertCountEqual(list(filtr.qs), [self.sample_a, self.sample_b])

    def test_sample_group_filter_excludes_other_groups(self):
        filtr = SampleFilter(
            data={"sample_group": str(self.other_group.pk)},
            queryset=Sample.objects.all(),
        )

        self.assertEqual(list(filtr.qs), [self.sample_unrelated])

    def test_group_list_kind_filter(self):
        filtr = SampleGroupFilter(
            data={"kind": "experiment"}, queryset=SampleGroup.objects.all()
        )

        self.assertEqual(list(filtr.qs), [self.group])


class RelatedListFilterTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = MaterialCategory.objects.create(name="Target category")
        cls.other_category = MaterialCategory.objects.create(name="Other category")
        cls.basis_component = MaterialComponent.objects.create(
            name="Basis component",
            publication_status="published",
        )
        cls.target_component = MaterialComponent.objects.create(
            name="Target component",
            publication_status="published",
            basis_component=cls.basis_component,
            comparable_component=cls.basis_component,
        )
        cls.other_component = MaterialComponent.objects.create(
            name="Other component",
            publication_status="published",
        )
        cls.target_component.categories.add(cls.category)
        cls.group = MaterialComponentGroup.objects.create(
            name="Target group",
            publication_status="published",
        )
        cls.other_group = MaterialComponentGroup.objects.create(
            name="Other group",
            publication_status="published",
        )
        cls.material = Material.objects.create(
            name="Target material",
            publication_status="published",
        )
        cls.other_material = Material.objects.create(
            name="Other material",
            publication_status="published",
        )
        cls.series = SampleSeries.objects.create(
            name="Target series",
            material=cls.material,
            publication_status="published",
        )
        cls.other_series = SampleSeries.objects.create(
            name="Other series",
            material=cls.other_material,
            publication_status="published",
        )
        cls.sample = Sample.objects.create(
            name="Target sample",
            material=cls.material,
            series=cls.series,
            publication_status="published",
        )
        cls.other_sample = Sample.objects.create(
            name="Other sample",
            material=cls.other_material,
            series=cls.other_series,
            publication_status="published",
        )
        unit = Unit.objects.filter(name="%").first()
        if unit is None:
            unit = Unit.objects.create(name="%")
        ComponentMeasurement.objects.create(
            sample=cls.sample,
            group=cls.group,
            component=cls.target_component,
            unit=unit,
            average=Decimal("1"),
            publication_status="published",
        )
        ComponentMeasurement.objects.create(
            sample=cls.other_sample,
            group=cls.other_group,
            component=cls.other_component,
            unit=unit,
            average=Decimal("2"),
            publication_status="published",
        )
        cls.property = MaterialProperty.objects.create(
            name="Target property",
            publication_status="published",
        )
        cls.other_property = MaterialProperty.objects.create(
            name="Other property",
            publication_status="published",
        )
        cls.method = AnalyticalMethod.objects.create(
            name="Target method",
            publication_status="published",
        )
        cls.other_method = AnalyticalMethod.objects.create(
            name="Other method",
            publication_status="published",
        )
        MaterialPropertyValue.objects.create(
            sample=cls.sample,
            property=cls.property,
            analytical_method=cls.method,
            average=Decimal("1"),
            publication_status="published",
        )
        MaterialPropertyValue.objects.create(
            sample=cls.other_sample,
            property=cls.other_property,
            analytical_method=cls.other_method,
            average=Decimal("2"),
            publication_status="published",
        )

    def test_component_category_filter_matches_related_components(self):
        filtr = MaterialComponentListFilter(
            data={"category": self.category.pk},
            queryset=MaterialComponent.objects.all(),
        )

        self.assertIn(self.target_component, filtr.qs)
        self.assertNotIn(self.other_component, filtr.qs)

    def test_component_basis_filter_matches_related_components(self):
        filtr = MaterialComponentListFilter(
            data={"basis_component": self.basis_component.pk},
            queryset=MaterialComponent.objects.all(),
        )

        self.assertIn(self.target_component, filtr.qs)
        self.assertNotIn(self.other_component, filtr.qs)

    def test_component_comparable_filter_matches_related_components(self):
        filtr = MaterialComponentListFilter(
            data={"comparable_component": self.basis_component.pk},
            queryset=MaterialComponent.objects.all(),
        )

        self.assertIn(self.target_component, filtr.qs)
        self.assertNotIn(self.other_component, filtr.qs)

    def test_component_group_filter_matches_related_components(self):
        filtr = MaterialComponentListFilter(
            data={"component_group": self.group.pk},
            queryset=MaterialComponent.objects.all(),
        )

        self.assertIn(self.target_component, filtr.qs)
        self.assertNotIn(self.other_component, filtr.qs)

    def test_component_group_filter_matches_measured_component(self):
        filtr = MaterialComponentGroupListFilter(
            data={"component": self.target_component.pk},
            queryset=MaterialComponentGroup.objects.all(),
        )

        self.assertIn(self.group, filtr.qs)
        self.assertNotIn(self.other_group, filtr.qs)

    def test_property_filter_matches_comparable_property(self):
        comparable = MaterialProperty.objects.create(
            name="Comparable property",
            publication_status="published",
            comparable_property=self.property,
        )
        filtr = MaterialPropertyListFilter(
            data={"comparable_property": self.property.pk},
            queryset=MaterialProperty.objects.all(),
        )

        self.assertIn(comparable, filtr.qs)
        self.assertNotIn(self.other_property, filtr.qs)

    def test_sample_analytical_method_filter_matches_related_samples(self):
        filtr = SampleFilter(
            data={"analytical_method": self.method.pk},
            queryset=Sample.objects.all(),
        )

        self.assertIn(self.sample, filtr.qs)
        self.assertNotIn(self.other_sample, filtr.qs)

    def test_sample_series_filter_matches_related_samples(self):
        filtr = SampleFilter(
            data={"series": self.series.pk},
            queryset=Sample.objects.all(),
        )

        self.assertIn(self.sample, filtr.qs)
        self.assertNotIn(self.other_sample, filtr.qs)

    def test_sample_series_filter_matches_material_by_primary_key(self):
        filtr = SampleSeriesFilter(
            data={"material": self.material.pk},
            queryset=SampleSeries.objects.all(),
        )

        self.assertIn(self.series, filtr.qs)
        self.assertNotIn(self.other_series, filtr.qs)


class MaterialListFilterFreeTextSearchTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.compost = Material.objects.create(
            name="Compost Mix",
            description="rich organic blend",
        )
        cls.sludge = Material.objects.create(
            name="Sewage Cake",
            abbreviation="SWC",
        )

    def test_filter_form_contains_free_text_search_field(self):
        filtr = MaterialListFilter(queryset=Material.objects.all())

        self.assertIn("q", filtr.form.fields)

    def test_q_matches_description(self):
        filtr = MaterialListFilter(
            data={"q": "organic"},
            queryset=Material.objects.all(),
        )

        self.assertIn(self.compost, filtr.qs)
        self.assertNotIn(self.sludge, filtr.qs)

    def test_q_matches_abbreviation(self):
        filtr = MaterialListFilter(
            data={"q": "SWC"},
            queryset=Material.objects.all(),
        )

        self.assertIn(self.sludge, filtr.qs)
        self.assertNotIn(self.compost, filtr.qs)

    def test_q_blank_value_does_not_filter(self):
        filtr = MaterialListFilter(
            data={"q": "   "},
            queryset=Material.objects.all(),
        )

        self.assertIn(self.compost, filtr.qs)
        self.assertIn(self.sludge, filtr.qs)

    def test_q_no_match_excludes_both(self):
        filtr = MaterialListFilter(
            data={"q": "no-such-material"},
            queryset=Material.objects.all(),
        )

        self.assertNotIn(self.compost, filtr.qs)
        self.assertNotIn(self.sludge, filtr.qs)
