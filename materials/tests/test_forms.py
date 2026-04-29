from django.contrib.auth.models import Permission, User
from django.http import QueryDict
from django.test import RequestFactory, TestCase
from django_tomselect.app_settings import TomSelectConfig
from django_tomselect.forms import TomSelectModelChoiceField

from utils.forms import CreateEnabledTomSelectModelMultipleChoiceField
from utils.properties.models import Unit

from ..forms import (
    AddCompositionModalForm,
    ComponentMeasurementModelForm,
    ComponentModelForm,
    MaterialPropertyModelForm,
    MaterialPropertyValueModelForm,
    SampleModelForm,
)
from ..models import (
    Material,
    MaterialCategory,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialProperty,
    Sample,
    SampleSeries,
    get_sample_substrate_category_name,
)


class AddComponentGroupModalModelFormTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        Material.objects.create(name="Test Material")
        MaterialComponentGroup.objects.create(name="Test Group 1")
        MaterialComponentGroup.objects.create(name="Test Group 2")

    def setUp(self):
        self.material = Material.objects.get(name="Test Material")
        self.group1 = MaterialComponentGroup.objects.get(name="Test Group 1")
        self.group2 = MaterialComponentGroup.objects.get(name="Test Group 2")

    def test_initial_group_queryset_has_only_unused_groups(self):
        sample_series = SampleSeries.objects.create(material=self.material)
        sample_series.add_component_group(self.group1)
        form = AddCompositionModalForm(instance=sample_series)
        self.assertQuerySetEqual(
            form.fields["group"].queryset.order_by("id"),
            MaterialComponentGroup.objects.filter(name="Test Group 2").order_by("id"),
        )

    def test_initial_fractions_of_queryset_has_only_used_components(self):
        sample_series = SampleSeries.objects.create(material=self.material)
        form = AddCompositionModalForm(instance=sample_series)
        self.assertQuerySetEqual(
            form.fields["fractions_of"].queryset.order_by("id"),
            MaterialComponent.objects.filter(
                id=MaterialComponent.objects.default().id
            ).order_by("id"),
        )


class ComponentModelFormTestCase(TestCase):
    def test_form_includes_comparable_component_field(self):
        form = ComponentModelForm()

        self.assertIn("comparable_component", form.fields)
        self.assertIsInstance(
            form.fields["comparable_component"],
            TomSelectModelChoiceField,
        )


class MaterialPropertyModelFormTestCase(TestCase):
    def test_form_includes_comparable_property_field(self):
        form = MaterialPropertyModelForm()

        self.assertIn("comparable_property", form.fields)
        self.assertIsInstance(
            form.fields["comparable_property"],
            TomSelectModelChoiceField,
        )


class MaterialPropertyValueModelFormTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.allowed_unit = Unit.objects.create(name="mg/L")
        cls.disallowed_unit = Unit.objects.create(name="g/L")
        cls.default_basis = MaterialComponent.objects.create(name="Dry Matter")
        cls.property = MaterialProperty.objects.create(name="Nitrogen", unit="g/L")
        cls.property.allowed_units.add(cls.allowed_unit)
        cls.property.default_basis_component = cls.default_basis
        cls.property.save(update_fields=["default_basis_component"])

    def test_fk_fields_use_tomselect_autocomplete_fields(self):
        form = MaterialPropertyValueModelForm()

        self.assertIsInstance(form.fields["property"], TomSelectModelChoiceField)
        self.assertIsInstance(form.fields["basis_component"], TomSelectModelChoiceField)
        self.assertIsInstance(form.fields["unit"], TomSelectModelChoiceField)
        self.assertIsInstance(
            form.fields["analytical_method"], TomSelectModelChoiceField
        )

    def test_form_includes_unit_field(self):
        form = MaterialPropertyValueModelForm()
        self.assertIn("unit", form.fields)

    def test_form_includes_basis_component_field(self):
        form = MaterialPropertyValueModelForm()
        self.assertIn("basis_component", form.fields)

    def test_numeric_measurement_fields_use_any_step(self):
        form = MaterialPropertyValueModelForm()

        self.assertEqual(form.fields["average"].widget.attrs.get("step"), "any")
        self.assertEqual(
            form.fields["standard_deviation"].widget.attrs.get("step"), "any"
        )

    def test_standard_deviation_is_optional(self):
        form = MaterialPropertyValueModelForm()

        self.assertFalse(form.fields["standard_deviation"].required)

    def test_standard_deviation_input_is_not_rendered_as_required(self):
        form = MaterialPropertyValueModelForm()

        self.assertNotIn(
            "required",
            str(form["standard_deviation"]),
        )

    def test_form_defaults_unit_from_property_symbol_match(self):
        property_obj = MaterialProperty.objects.create(name="Phosphorus", unit="kg/m³")
        expected_unit = Unit.objects.create(
            name="Kilogram per cubic metre",
            symbol="kg/m³",
        )

        data = QueryDict("", mutable=True)
        data.update(
            {
                "property": property_obj.pk,
                "average": "12.3",
                "standard_deviation": "0.5",
            }
        )
        form = MaterialPropertyValueModelForm(data=data)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["unit"], expected_unit)

    def test_form_rejects_unit_not_in_allowed_units(self):
        data = QueryDict("", mutable=True)
        data.update(
            {
                "property": self.property.pk,
                "unit": self.disallowed_unit.pk,
                "average": "12.3",
                "standard_deviation": "0.5",
            }
        )
        form = MaterialPropertyValueModelForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("unit", form.errors)

    def test_form_defaults_basis_component_from_property(self):
        data = QueryDict("", mutable=True)
        data.update(
            {
                "property": self.property.pk,
                "unit": self.allowed_unit.pk,
                "average": "12.3",
                "standard_deviation": "0.5",
            }
        )
        form = MaterialPropertyValueModelForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["basis_component"], self.property.default_basis_component
        )


class ComponentMeasurementModelFormTestCase(TestCase):
    def test_standard_deviation_is_optional(self):
        form = ComponentMeasurementModelForm()

        self.assertFalse(form.fields["standard_deviation"].required)

    def test_standard_deviation_input_is_not_rendered_as_required(self):
        form = ComponentMeasurementModelForm()

        self.assertNotIn(
            "required",
            str(form["standard_deviation"]),
        )


class SampleModelFormTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner")
        cls.owner.user_permissions.add(Permission.objects.get(codename="add_material"))
        substrate_category_name = get_sample_substrate_category_name()
        cls.substrate_category, _ = MaterialCategory.objects.get_or_create(
            name=substrate_category_name,
        )
        cls.other_category, _ = MaterialCategory.objects.get_or_create(
            name="Simple component"
        )

        cls.substrate_material = Material.objects.create(name="Food waste mix")
        cls.substrate_material.categories.add(cls.substrate_category)

        cls.non_substrate_material = Material.objects.create(name="Amino Acids")
        cls.non_substrate_material.categories.add(cls.other_category)

    def setUp(self):
        self.factory = RequestFactory()

    def _build_request(self, user):
        request = self.factory.get("/")
        request.user = user
        return request

    def test_material_field_uses_substrate_autocomplete(self):
        form = SampleModelForm(request=self._build_request(self.owner))

        self.assertEqual(
            form.fields["material"].widget.url,
            "sample-substrate-material-autocomplete",
        )
        self.assertEqual(form.fields["material"].label, "Substrate")

    def test_material_field_sets_help_text_and_quick_create_url(self):
        form = SampleModelForm(request=self._build_request(self.owner))

        self.assertEqual(
            form.fields["material"].help_text,
            "Select an existing substrate. If it is not listed, type a new name and press Enter to create it automatically.",
        )
        self.assertEqual(
            form.fields["material"].widget.attrs["data-tomselect-create-url"],
            "/materials/materials/substrates/quick-create/",
        )
        self.assertEqual(
            form.fields["material"].widget.attrs["data-tomselect-create-payload-key"],
            "name",
        )
        self.assertIn("js/tomselect_inline_create.min.js", str(form.media))

    def test_create_enabled_multiple_choice_field_includes_inline_create_media(self):
        field = CreateEnabledTomSelectModelMultipleChoiceField(
            config=TomSelectConfig(url="sampleseries-autocomplete", create=True),
            required=False,
        )

        self.assertIn("js/tomselect_inline_create.min.js", str(field.widget.media))

    def test_material_queryset_only_contains_substrate_materials(self):
        form = SampleModelForm(request=self._build_request(self.owner))
        material_queryset = form.fields["material"].queryset

        self.assertIn(self.substrate_material, material_queryset)
        self.assertNotIn(self.non_substrate_material, material_queryset)

    def test_material_queryset_preserves_existing_material_on_edit(self):
        sample = Sample.objects.create(
            owner=self.owner, material=self.non_substrate_material
        )

        form = SampleModelForm(
            instance=sample,
            request=self._build_request(self.owner),
        )
        material_queryset = form.fields["material"].queryset

        self.assertIn(self.substrate_material, material_queryset)
        self.assertIn(self.non_substrate_material, material_queryset)
