from datetime import datetime

from django.contrib.auth.models import Permission, User
from django.http import QueryDict
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
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

    def test_comparable_component_choices_exclude_materials(self):
        material = Material.objects.create(name="Not a component")
        component = MaterialComponent.objects.create(name="Actual component")

        queryset = ComponentModelForm().fields["comparable_component"].queryset

        self.assertIn(component, queryset)
        self.assertNotIn(material.pk, queryset.values_list("pk", flat=True))


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

    def test_unit_choices_are_limited_to_weight_fraction_units(self):
        percent, _ = Unit.objects.get_or_create(
            name="%", defaults={"symbol": "percent"}
        )
        g_per_kg = Unit.objects.create(name="g/kg", symbol="g/kg")
        mg_per_l = Unit.objects.create(name="mg/L", symbol="mg/L")
        volume_percent, _ = Unit.objects.update_or_create(
            name="vol.-%", defaults={"symbol": "volume_percent"}
        )

        queryset = ComponentMeasurementModelForm().fields["unit"].queryset

        self.assertIn(percent, queryset)
        self.assertIn(g_per_kg, queryset)
        self.assertNotIn(mg_per_l, queryset)
        self.assertNotIn(volume_percent, queryset)


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

        cls.substrate_material = Material.objects.create(
            name="Food waste mix", owner=cls.owner, publication_status="published"
        )
        cls.substrate_material.categories.add(cls.substrate_category)

        cls.non_substrate_material = Material.objects.create(name="Amino Acids")
        cls.non_substrate_material.categories.add(cls.other_category)

    def setUp(self):
        self.factory = RequestFactory()

    def _build_request(self, user):
        request = self.factory.get("/")
        request.user = user
        return request

    def _sampling_form(self, value, instance=None):
        data = QueryDict(mutable=True)
        data.update(
            {
                "name": "Dated sample",
                "material": str(self.substrate_material.pk),
                "standalone": "on",
                "datetime": value,
            }
        )
        return SampleModelForm(
            data=data,
            instance=instance or Sample(owner=self.owner),
            request=self._build_request(self.owner),
        )

    @override_settings(TIME_ZONE="Europe/Berlin", USE_TZ=True)
    def test_sampling_date_input_preserves_supplied_precision_in_default_timezone(self):
        cases = (
            ("2024", "year", datetime(2024, 1, 1)),
            ("2024-08-27", "date", datetime(2024, 8, 27)),
            ("2024-08-27 14:30", "time", datetime(2024, 8, 27, 14, 30)),
            ("2024-08-27T00:00", "time", datetime(2024, 8, 27)),
            ("2024-08-27 14:30:15", "time", datetime(2024, 8, 27, 14, 30, 15)),
        )
        with timezone.override("America/Los_Angeles"):
            for value, precision, expected in cases:
                with self.subTest(value=value):
                    form = self._sampling_form(value)
                    self.assertTrue(form.is_valid(), form.errors)
                    sample = form.save()
                    sample.refresh_from_db()
                    self.assertEqual(sample.datetime_precision, precision)
                    self.assertEqual(
                        sample.datetime,
                        timezone.make_aware(expected, timezone.get_default_timezone()),
                    )
                    edit_form = SampleModelForm(instance=sample)
                    round_trip = self._sampling_form(
                        edit_form.initial["datetime"], sample
                    )
                    self.assertTrue(round_trip.is_valid(), round_trip.errors)
                    self.assertEqual(round_trip.save().datetime_precision, precision)

    def test_sampling_date_rejects_invalid_or_ambiguous_input(self):
        for value in ("2024-08", "27/08/2024", "2024-02-30", "0000", "unknown"):
            with self.subTest(value=value):
                form = self._sampling_form(value)
                self.assertFalse(form.is_valid())
                self.assertIn("datetime", form.errors)

    def test_unchanged_sampling_date_preserves_legacy_timestamp(self):
        for value in (datetime(2024, 8, 27), datetime(2024, 8, 27, 14, 30, 12, 123456)):
            with self.subTest(value=value):
                sample = Sample.objects.create(
                    owner=self.owner,
                    material=self.substrate_material,
                    datetime=timezone.make_aware(
                        value, timezone.get_default_timezone()
                    ),
                )
                original_datetime = sample.datetime
                form = self._sampling_form(
                    SampleModelForm(instance=sample).initial["datetime"], sample
                )
                self.assertTrue(form.is_valid(), form.errors)
                saved = form.save()
                saved.refresh_from_db()
                self.assertEqual(saved.datetime, original_datetime)
                self.assertEqual(saved.datetime_precision, "")

    def test_sampling_date_can_be_cleared(self):
        sample = Sample.objects.create(
            owner=self.owner,
            material=self.substrate_material,
            datetime=timezone.make_aware(datetime(2024, 1, 1)),
            datetime_precision="year",
        )
        form = self._sampling_form("", sample)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        saved.refresh_from_db()
        self.assertIsNone(saved.datetime)
        self.assertEqual(saved.datetime_precision, "")

    def test_supplied_initial_sampling_datetime_is_not_overridden(self):
        sample = Sample(
            owner=self.owner,
            material=self.substrate_material,
            datetime=timezone.make_aware(datetime(2024, 1, 1)),
            datetime_precision="year",
        )
        for value in ("2025-08-27", "", datetime(2025, 8, 27, 14, 30)):
            with self.subTest(value=value):
                form = SampleModelForm(instance=sample, initial={"datetime": value})
                self.assertEqual(form.initial["datetime"], value)

    def test_distinguishes_sampling_and_analysis_time(self):
        form = SampleModelForm(request=self._build_request(self.owner))

        self.assertEqual(form.fields["datetime"].label, "Sampling date/time")
        self.assertIn("analysis_date", form.fields)
        self.assertEqual(form.fields["analysis_date"].label, "Analysis date/time")
        self.assertEqual(
            form.fields["analysis_date"].widget.input_type, "datetime-local"
        )
        self.assertIn("analysis_laboratory", form.fields)

    def test_sampling_and_analysis_widgets_render_existing_values_in_iso_format(self):
        sample = Sample.objects.create(
            name="Timed sample",
            material=self.substrate_material,
            owner=self.owner,
            datetime=timezone.make_aware(datetime(2024, 3, 5, 9, 30)),
            analysis_date=timezone.make_aware(datetime(2024, 4, 12, 14, 0)),
        )
        form = SampleModelForm(instance=sample, request=self._build_request(self.owner))

        self.assertIn('value="2024-03-05 09:30"', str(form["datetime"]))
        self.assertIn('value="2024-04-12T14:00"', str(form["analysis_date"]))

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
