from decimal import ROUND_HALF_UP, Decimal

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.forms import inlineformset_factory
from django.http import QueryDict
from django.test import RequestFactory, TestCase
from django_tomselect.app_settings import TomSelectConfig
from django_tomselect.forms import TomSelectModelChoiceField

from distributions.models import Timestep
from utils.forms import CreateEnabledTomSelectModelMultipleChoiceField
from utils.properties.models import Unit

from ..forms import (
    AddComponentModalForm,
    AddCompositionModalForm,
    ComponentMeasurementModelForm,
    ComponentModelForm,
    MaterialPropertyModelForm,
    MaterialPropertyValueModelForm,
    SampleModelForm,
    WeightShareInlineFormset,
    WeightShareModelForm,
)
from ..models import (
    Composition,
    Material,
    MaterialCategory,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialProperty,
    Sample,
    SampleSeries,
    WeightShare,
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


class AddComponentModalModelFormTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        material = Material.objects.create(name="Test Material")
        sample_series = SampleSeries.objects.create(
            material=material,
            name="Test Series",
        )
        sample = Sample.objects.get(
            series=sample_series, timestep=Timestep.objects.default()
        )
        component_group = MaterialComponentGroup.objects.create(name="Test Group")
        Composition.objects.create(
            sample=sample,
            group=component_group,
            fractions_of=MaterialComponent.objects.default(),
        )

        MaterialComponent.objects.create(name="Test Component 1")

        MaterialComponent.objects.create(name="Test Component 2")

    def setUp(self):
        self.component_group = MaterialComponentGroup.objects.get(name="Test Group")
        self.sample = Sample.objects.get(
            series__name="Test Series", timestep=Timestep.objects.default()
        )
        self.composition = Composition.objects.get(
            sample=self.sample, group=self.component_group
        )
        self.component1 = MaterialComponent.objects.get(name="Test Component 1")
        self.component2 = MaterialComponent.objects.get(name="Test Component 2")

    def test_initial_component_queryset_contains_only_unused_components(self):
        self.composition.add_component(
            self.component1, average=0.5, standard_deviation=0.02
        )
        self.composition.add_component(
            MaterialComponent.objects.other(), average=0.5, standard_deviation=0.1337
        )
        form = AddComponentModalForm(instance=self.composition)
        component_queryset = form.fields["component"].queryset

        self.assertIn(self.component2, component_queryset)
        self.assertNotIn(self.component1, component_queryset)
        self.assertNotIn(MaterialComponent.objects.other(), component_queryset)


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


class CompositionUpdateFormTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create_user(username="owner")
        User.objects.create_user(username="outsider")
        member = User.objects.create_user(username="member")

        members_group = Group.objects.create(name="members")
        composition_ct = ContentType.objects.get_for_model(Composition)
        change_composition_permission, _ = Permission.objects.get_or_create(
            codename="change_composition",
            content_type=composition_ct,
            defaults={"name": "Can change composition"},
        )
        weightshare_ct = ContentType.objects.get_for_model(WeightShare)
        change_weightshare_permission, _ = Permission.objects.get_or_create(
            codename="change_weightshare",
            content_type=weightshare_ct,
            defaults={"name": "Can change weight share"},
        )
        members_group.permissions.add(
            change_composition_permission, change_weightshare_permission
        )
        member.groups.add(members_group)

        material = Material.objects.create(owner=owner, name="Test Material")

        group = MaterialComponentGroup.objects.create(owner=owner, name="Test Group")

        sample = Sample.objects.create(
            owner=owner, material=material, name="Test Sample"
        )

        composition = Composition.objects.create(
            owner=owner,
            group=group,
            sample=sample,
            fractions_of=MaterialComponent.objects.default(),
        )

        for i in range(5):
            component = MaterialComponent.objects.create(
                owner=owner, name=f"Test Component {i}"
            )
            WeightShare.objects.create(
                owner=owner,
                component=component,
                composition=composition,
                average=Decimal("0.2000000000"),
                standard_deviation=Decimal("0.0500000000"),
            )

    def setUp(self):
        self.owner = User.objects.get(username="owner")
        self.outsider = User.objects.get(username="outsider")
        self.member = User.objects.get(username="member")
        self.composition = Composition.objects.get(group__name="Test Group")
        self.material = Material.objects.get(name="Test Material")

    def test_initial_values_are_displayed_as_percentages(self):
        """
        Test that the formset initializes 'average' and 'standard_deviation'
        fields with percentage values displaying at least one decimal place.
        """
        FormSet = inlineformset_factory(
            Composition,
            WeightShare,
            form=WeightShareModelForm,
            formset=WeightShareInlineFormset,
            extra=0,
        )
        formset = FormSet(instance=self.composition)
        averages_sum = Decimal("0.0")

        for form in formset:
            if not form.instance.pk:
                continue  # Skip forms not linked to existing WeightShare instances

            component_id = form["component"].value()
            component = MaterialComponent.objects.get(id=component_id)
            share = WeightShare.objects.get(component=component)

            form_average = Decimal(form["average"].value())
            form_std_dev = Decimal(form["standard_deviation"].value())

            expected_average = (share.average * Decimal("100")).quantize(
                Decimal(".1"), rounding=ROUND_HALF_UP
            )
            expected_std_dev = (share.standard_deviation * Decimal("100")).quantize(
                Decimal(".1"), rounding=ROUND_HALF_UP
            )

            self.assertEqual(form_average, expected_average)
            self.assertEqual(form_std_dev, expected_std_dev)

            averages_sum += form_average

        self.assertEqual(averages_sum, Decimal("100.0"))

    def test_input_percentages_are_stored_as_fractions_of_one(self):
        """
        Test that submitting the form with percentage values correctly converts
        them to decimal values and stores them as fractions of one.
        """
        FormSet = inlineformset_factory(
            Composition,
            WeightShare,
            form=WeightShareModelForm,
            formset=WeightShareInlineFormset,
            extra=0,
        )
        components = MaterialComponent.objects.exclude(
            name__in=("Fresh Matter (FM)", "Other")
        ).values_list("id", flat=True)[:2]

        new_composition = Composition.objects.create(
            owner=self.owner,
            group=self.composition.group,
            sample=self.composition.sample,
            fractions_of=self.composition.fractions_of,
        )

        data = {
            "shares-TOTAL_FORMS": "2",
            "shares-INITIAL_FORMS": "0",
            "shares-MIN_NUM_FORMS": "0",
            "shares-MAX_NUM_FORMS": "1000",
            "shares-0-id": "",
            "shares-0-component": f"{components[0]}",
            "shares-0-average": "45.5",
            "shares-0-standard_deviation": "1.5",
            "shares-1-id": "",
            "shares-1-component": f"{components[1]}",
            "shares-1-average": "54.5",
            "shares-1-standard_deviation": "1.5",
        }
        formset = FormSet(data=data, instance=new_composition)
        self.assertTrue(formset.is_valid())
        formset.instance.owner = self.owner
        formset.save()

        self.assertEqual(
            WeightShare.objects.get(
                component=components[0], composition=new_composition
            ).average,
            Decimal("0.4550000000"),
        )
        self.assertEqual(
            WeightShare.objects.get(
                component=components[0], composition=new_composition
            ).standard_deviation,
            Decimal("0.0150000000"),
        )
        self.assertEqual(
            WeightShare.objects.get(
                component=components[1], composition=new_composition
            ).average,
            Decimal("0.5450000000"),
        )
        self.assertEqual(
            WeightShare.objects.get(
                component=components[1], composition=new_composition
            ).standard_deviation,
            Decimal("0.0150000000"),
        )

    def test_form_valid_if_averages_sum_up_to_100_percent(self):
        """
        Test that the formset is valid if the sum of averages equals 100%.
        """
        FormSet = inlineformset_factory(
            Composition,
            WeightShare,
            form=WeightShareModelForm,
            formset=WeightShareInlineFormset,
            extra=0,
        )
        components = MaterialComponent.objects.exclude(
            name="Fresh Matter (FM)"
        ).values_list("id", flat=True)[:2]
        data = {
            "shares-TOTAL_FORMS": "2",
            "shares-INITIAL_FORMS": "0",
            "shares-MIN_NUM_FORMS": "0",
            "shares-MAX_NUM_FORMS": "1000",
            "shares-0-id": "",
            "shares-0-component": f"{components[0]}",
            "shares-0-average": "45.5",  # 45.5%
            "shares-0-standard_deviation": "1.5",  # 1.5%
            "shares-1-id": "",
            "shares-1-component": f"{components[1]}",
            "shares-1-average": "54.5",  # 54.5%
            "shares-1-standard_deviation": "1.5",  # 1.5%
        }
        formset = FormSet(data=data, instance=self.composition)
        self.assertTrue(formset.is_valid())

        formset.instance.owner = self.owner
        formset.save()

        for share in WeightShare.objects.filter(composition=self.composition):
            self.assertGreaterEqual(share.average, Decimal("0.0"))
            self.assertLessEqual(share.average, Decimal("1.0"))
            self.assertGreaterEqual(share.standard_deviation, Decimal("0.0"))
            self.assertLessEqual(share.standard_deviation, Decimal("1.0"))

    def test_form_invalid_if_averages_dont_sum_up_to_100_percent(self):
        """
        Test that the formset is invalid if the sum of averages does not equal 100%.
        """
        FormSet = inlineformset_factory(
            Composition,
            WeightShare,
            form=WeightShareModelForm,
            formset=WeightShareInlineFormset,
            extra=0,
        )
        components = MaterialComponent.objects.exclude(
            name="Fresh Matter (FM)"
        ).values_list("id", flat=True)[:2]
        data = {
            "shares-TOTAL_FORMS": "2",
            "shares-INITIAL_FORMS": "0",
            "shares-MIN_NUM_FORMS": "0",
            "shares-MAX_NUM_FORMS": "1000",
            "shares-0-id": "",
            "shares-0-component": f"{components[0]}",
            "shares-0-average": "100",
            "shares-0-standard_deviation": "0.01",
            "shares-1-id": "",
            "shares-1-component": f"{components[1]}",
            "shares-1-average": "100",
            "shares-1-standard_deviation": "0.01",
        }
        formset = FormSet(data=data, instance=self.composition)
        self.assertFalse(formset.is_valid())
        self.assertIn(
            "Weight shares of components must sum up to 100%.",
            formset.non_form_errors(),
        )

        # Verify that the invalid data was not saved
        saved_shares = WeightShare.objects.filter(composition=self.composition)
        for share in saved_shares:
            self.assertLessEqual(share.average, Decimal("1.0"))
            self.assertGreaterEqual(share.average, Decimal("0.0"))
            self.assertLessEqual(share.standard_deviation, Decimal("1.0"))
            self.assertGreaterEqual(share.standard_deviation, Decimal("0.0"))

    def test_form_fields_render_percentage_suffix(self):
        """
        Test that the form fields have the '%' symbol in their labels.
        Since the '%' is in the label, not appended to the input, check the label text.
        """
        FormSet = inlineformset_factory(
            Composition,
            WeightShare,
            form=WeightShareModelForm,
            formset=WeightShareInlineFormset,
            extra=0,
        )
        formset = FormSet(instance=self.composition)
        for form in formset:
            # Check that the label contains '%'
            average_label = form.fields["average"].label
            standard_deviation_label = form.fields["standard_deviation"].label
            self.assertIn("%", average_label)
            self.assertIn("%", standard_deviation_label)


class WeightShareModelFormTest(TestCase):
    def setUp(self):
        self.group = MaterialComponentGroup.objects.create(name="Test Group")
        self.material = Material.objects.create(name="Test Material")
        self.series = SampleSeries.objects.create(
            material=self.material, name="Test Series"
        )
        self.sample = Sample.objects.create(
            name="Test Sample", material=self.material, series=self.series
        )
        self.composition = Composition.objects.create(
            name="Test Composition", sample=self.sample, group=self.group
        )

        self.component1 = MaterialComponent.objects.create(name="Component 1")
        self.component2 = MaterialComponent.objects.create(name="Component 2")

        WeightShare.objects.create(
            composition=self.composition,
            component=self.component1,
            average=Decimal("0.2000000000"),
            standard_deviation=Decimal("0.0500000000"),
        )
        WeightShare.objects.create(
            composition=self.composition,
            component=self.component2,
            average=Decimal("0.8000000000"),
            standard_deviation=Decimal("0.1500000000"),
        )

    def test_initial_values_are_displayed_as_percentages_with_one_decimal(self):
        """
        Test that the formset initializes 'average' and 'standard_deviation'
        fields with percentage values displaying at least one decimal place.
        """
        FormSet = inlineformset_factory(
            Composition,
            WeightShare,
            form=WeightShareModelForm,
            formset=WeightShareInlineFormset,
            extra=0,
        )
        formset = FormSet(instance=self.composition)
        averages_sum = Decimal("0.0")

        for form in formset:
            component_id = form["component"].value()
            component = MaterialComponent.objects.get(id=component_id)
            share = WeightShare.objects.get(component=component)

            form_average = Decimal(form["average"].value())
            form_std_dev = Decimal(form["standard_deviation"].value())

            expected_average = (share.average * Decimal("100")).quantize(
                Decimal(".1"), rounding=ROUND_HALF_UP
            )
            expected_std_dev = (share.standard_deviation * Decimal("100")).quantize(
                Decimal(".1"), rounding=ROUND_HALF_UP
            )

            self.assertEqual(form_average, expected_average)
            self.assertEqual(form_std_dev, expected_std_dev)

            averages_sum += form_average

        self.assertEqual(averages_sum, Decimal("100.0"))

    def test_form_fields_render_percentage_suffix(self):
        """
        Test that the rendered form fields include a '%' suffix.
        """
        FormSet = inlineformset_factory(
            Composition,
            WeightShare,
            form=WeightShareModelForm,
            formset=WeightShareInlineFormset,
            extra=0,
        )
        formset = FormSet(instance=self.composition)
        for form in formset:
            rendered_form = form.as_p()
            self.assertIn("%", rendered_form)

    def test_form_submission_converts_percentages_to_decimals_with_one_decimal_minimum(
        self,
    ):
        """
        Test that submitting the form with percentage values correctly converts
        them to decimal values with at least one decimal place.
        """
        form_data = {
            "shares-TOTAL_FORMS": "2",
            "shares-INITIAL_FORMS": "2",
            "shares-MIN_NUM_FORMS": "0",
            "shares-MAX_NUM_FORMS": "1000",
            "shares-0-id": str(WeightShare.objects.get(component=self.component1).id),
            "shares-0-component": str(self.component1.id),
            "shares-0-average": "25.0",
            "shares-0-standard_deviation": "5.0",
            "shares-1-id": str(WeightShare.objects.get(component=self.component2).id),
            "shares-1-component": str(self.component2.id),
            "shares-1-average": "75.0",
            "shares-1-standard_deviation": "15.0",
        }

        FormSet = inlineformset_factory(
            Composition,
            WeightShare,
            form=WeightShareModelForm,
            formset=WeightShareInlineFormset,
            extra=0,
        )
        formset = FormSet(data=form_data, instance=self.composition)

        self.assertTrue(formset.is_valid())
        formset.save()

        updated_share1 = WeightShare.objects.get(component=self.component1)
        updated_share2 = WeightShare.objects.get(component=self.component2)

        self.assertEqual(updated_share1.average, Decimal("0.2500000000"))
        self.assertEqual(updated_share1.standard_deviation, Decimal("0.0500000000"))

        self.assertEqual(updated_share2.average, Decimal("0.7500000000"))
        self.assertEqual(updated_share2.standard_deviation, Decimal("0.1500000000"))
