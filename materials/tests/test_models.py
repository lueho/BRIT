from decimal import Decimal
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import signals
from django.test import TestCase
from factory.django import mute_signals

from distributions.models import TemporalDistribution, Timestep
from materials.models import (
    ComponentMeasurement,
    Composition,
    Material,
    MaterialCategory,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialProperty,
    MaterialPropertyValue,
    Sample,
    SampleSeries,
)
from utils.properties.models import Unit


class InitialDataTestCase(TestCase):
    def test_base_component_group_is_created_from_migrations(self):
        MaterialComponentGroup.objects.get(name="Total Material")
        self.assertEqual(MaterialComponentGroup.objects.all().count(), 1)

    def test_base_component_is_created_from_migrations(self):
        MaterialComponent.objects.get(name="Fresh Matter (FM)")
        self.assertGreaterEqual(MaterialComponent.objects.count(), 2)

    def test_other_component_is_created_from_migrations(self):
        MaterialComponent.objects.get(name="Other")
        self.assertGreaterEqual(MaterialComponent.objects.count(), 2)


class MaterialComponentGroupTestCase(TestCase):
    def test_get_default_material_component_group(self):
        default = MaterialComponentGroup.objects.default()
        self.assertIsInstance(default, MaterialComponentGroup)
        self.assertEqual(default.name, "Total Material")


class MaterialComponentTestCase(TestCase):
    def test_get_default_material_component_manager_function(self):
        default = MaterialComponent.objects.default()
        self.assertIsInstance(default, MaterialComponent)
        self.assertEqual(default.name, "Fresh Matter (FM)")

    def test_get_other_material_component_manager_function(self):
        default = MaterialComponent.objects.other()
        self.assertIsInstance(default, MaterialComponent)
        self.assertEqual(default.name, "Other")

    def test_canonical_component_defaults_to_self(self):
        component = MaterialComponent.objects.create(name="Organic matter")

        self.assertEqual(component.canonical_component, component)

    def test_canonical_component_follows_comparable_component(self):
        canonical = MaterialComponent.objects.create(name="Organic matter")
        alias = MaterialComponent.objects.create(
            name="Volatile solids",
            comparable_component=canonical,
        )

        self.assertEqual(alias.canonical_component, canonical)


class MaterialPropertyTestCase(TestCase):
    def test_canonical_property_defaults_to_self(self):
        property_obj = MaterialProperty.objects.create(name="Organic matter", unit="%")

        self.assertEqual(property_obj.canonical_property, property_obj)

    def test_canonical_property_follows_comparable_property(self):
        canonical = MaterialProperty.objects.create(name="Organic matter", unit="%")
        alias = MaterialProperty.objects.create(
            name="Volatile solids",
            unit="%",
            comparable_property=canonical,
        )

        self.assertEqual(alias.canonical_property, canonical)


class ModelLabelMetadataTestCase(TestCase):
    def test_irregular_plural_labels_are_explicit(self):
        self.assertEqual(
            MaterialCategory._meta.verbose_name_plural,
            "material categories",
        )
        self.assertEqual(
            MaterialProperty._meta.verbose_name_plural,
            "material properties",
        )
        self.assertEqual(SampleSeries._meta.verbose_name_plural, "sample series")


class MaterialTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        User.objects.create(username="standard_user")
        custom_distribution = TemporalDistribution.objects.create(
            name="Custom Distribution",
        )
        main_step1 = Timestep.objects.create(
            name="Timestep 1", distribution=custom_distribution
        )
        main_step2 = Timestep.objects.create(
            name="Timestep 2", distribution=custom_distribution
        )
        MaterialComponentGroup.objects.create(name="Custom Group")
        MaterialComponent.objects.default()
        MaterialComponent.objects.create(name="Custom Component")

        with mute_signals(signals.post_save):
            material1 = Material.objects.create(name="Test Material 1")
            sample_series = SampleSeries.objects.create(
                material=material1, standard=True
            )
            Sample.objects.create(
                material=material1,
                series=sample_series,
                timestep=Timestep.objects.default(),
            )
            Sample.objects.create(
                material=material1, series=sample_series, timestep=main_step1
            )
            Sample.objects.create(
                material=material1, series=sample_series, timestep=main_step2
            )

    def setUp(self):
        self.user = User.objects.get(username="standard_user")
        self.default_group = MaterialComponentGroup.objects.default()
        self.default_component = MaterialComponent.objects.default()


class BaseMaterialUniquenessTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="material_owner")
        cls.other_owner = User.objects.create_user(username="other_material_owner")

    def test_private_duplicate_names_are_allowed_for_different_owners(self):
        Material.objects.create(owner=self.owner, name="Straw")
        duplicate = Material(owner=self.other_owner, name="Straw")

        duplicate.full_clean()
        duplicate.save()

        self.assertEqual(Material.objects.filter(name="Straw").count(), 2)

    def test_private_name_matching_published_material_fails_validation(self):
        published = Material.objects.create(
            owner=self.owner,
            name="Wood",
            publication_status=Material.STATUS_PUBLISHED,
        )
        private = Material(owner=self.other_owner, name="wood")

        with self.assertRaises(ValidationError) as ctx:
            private.full_clean()

        self.assertIn("name", ctx.exception.message_dict)
        self.assertIn(str(published.pk), ctx.exception.message_dict["name"][0])

    def test_submit_for_review_blocks_published_name_collision(self):
        Material.objects.create(
            owner=self.owner,
            name="Bark",
            publication_status=Material.STATUS_PUBLISHED,
        )
        private = Material.objects.create(owner=self.other_owner, name="bark")

        with self.assertRaises(ValidationError):
            private.submit_for_review()

        private.refresh_from_db()
        self.assertEqual(private.publication_status, Material.STATUS_PRIVATE)

    def test_database_blocks_duplicate_published_name_and_type_case_insensitive(self):
        suffix = uuid4().hex
        owner = User.objects.create_user(username=f"published_owner_{suffix}")
        other_owner = User.objects.create_user(username=f"other_published_{suffix}")
        name = f"Constraint Total Potassium {suffix}"
        Material.objects.create(
            owner=owner,
            name=name,
            publication_status=Material.STATUS_PUBLISHED,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Material.objects.create(
                    owner=other_owner,
                    name=name.lower(),
                    publication_status=Material.STATUS_PUBLISHED,
                )


class SampleSeriesTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        User.objects.create(username="standard_user")
        custom_distribution = TemporalDistribution.objects.create(
            name="Custom Distribution",
        )
        timestep1 = Timestep.objects.create(
            name="Timestep 1", distribution=custom_distribution
        )
        timestep2 = Timestep.objects.create(
            name="Timestep 2", distribution=custom_distribution
        )
        MaterialComponentGroup.objects.create(name="Custom Group")
        MaterialComponent.objects.default()
        MaterialComponent.objects.create(name="Custom Component")

        with mute_signals(signals.post_save):
            material1 = Material.objects.create(name="Test Material 1")
            sample_series = SampleSeries.objects.create(
                material=material1, standard=True
            )
            Sample.objects.create(
                material=material1,
                series=sample_series,
                timestep=Timestep.objects.default(),
            )
            Sample.objects.create(
                material=material1, series=sample_series, timestep=timestep1
            )
            Sample.objects.create(
                material=material1, series=sample_series, timestep=timestep2
            )

    def setUp(self):
        self.user = User.objects.get(username="standard_user")
        self.material1 = Material.objects.get(name="Test Material 1")
        self.sample0 = Sample.objects.get(timestep=Timestep.objects.default())
        self.default_distribution = TemporalDistribution.objects.default()
        self.custom_distribution = TemporalDistribution.objects.get(
            name="Custom Distribution"
        )
        self.default_group = MaterialComponentGroup.objects.default()
        self.custom_group = MaterialComponentGroup.objects.get(name="Custom Group")
        self.default_component = MaterialComponent.objects.default()
        self.custom_component = MaterialComponent.objects.get(name="Custom Component")
        self.sample_series = SampleSeries.objects.create(material=self.material1)

    def test_add_temporal_distribution(self):
        self.sample_series.add_temporal_distribution(self.custom_distribution)
        # the sample series should now have two associated distributions: default and custom
        self.assertEqual(self.sample_series.temporal_distributions.count(), 2)
        # for each timestep in both distributions a sample object should exist
        self.assertEqual(self.sample_series.samples.count(), 3)
        for timestep in self.custom_distribution.timestep_set.all():
            Sample.objects.get(series=self.sample_series, timestep=timestep)

    def test_remove_temporal_distribution(self):
        self.sample_series.add_temporal_distribution(self.custom_distribution)
        self.sample_series.remove_temporal_distribution(self.custom_distribution)
        # now only the default distribution and only the according samples should remain
        self.assertEqual(self.sample_series.temporal_distributions.count(), 1)
        for timestep in self.custom_distribution.timestep_set.all():
            with self.assertRaises(Sample.DoesNotExist):
                Sample.objects.get(series=self.sample_series, timestep=timestep)

    def test_add_component_group(self):
        self.sample_series.add_component_group(self.custom_group)
        for sample in self.sample_series.samples.all():
            Composition.objects.get(sample=sample, group=self.custom_group)

    def test_remove_component_group(self):
        self.sample_series.add_component_group(self.custom_group)
        self.sample_series.remove_component_group(self.custom_group)
        for sample in self.sample_series.samples.all():
            with self.assertRaises(Composition.DoesNotExist):
                Composition.objects.get(sample=sample, group=self.custom_group)

    def test_components_include_raw_component_measurements(self):
        raw_component = MaterialComponent.objects.create(name="Raw Series Component")
        unit = Unit.objects.create(name="Series component percent")
        sample = Sample.objects.create(
            material=self.material1,
            series=self.sample_series,
            timestep=Timestep.objects.default(),
        )
        ComponentMeasurement.objects.create(
            sample=sample,
            group=self.custom_group,
            component=raw_component,
            unit=unit,
            average=Decimal("42.0"),
        )

        self.assertIn(raw_component, self.sample_series.components)

    def test_duplicate_creates_new_instance_with_identical_field_values(self):
        creator = User.objects.create(username="creator")
        duplicate = self.sample_series.duplicate(creator)
        self.assertIsInstance(duplicate, SampleSeries)
        self.assertNotEqual(self.sample_series, duplicate)
        self.assertEqual(duplicate.owner, creator)
        for field in self.sample_series._meta.get_fields():
            if field.concrete and field.name not in [
                "id",
                "owner",
                "created_at",
                "lastmodified_at",
                "temporal_distributions",
            ]:
                self.assertEqual(
                    getattr(duplicate, field.name),
                    getattr(self.sample_series, field.name),
                )
            elif field.name == "samples":
                self.assertTrue(self.sample_series.samples.exists())
                self.assertTrue(duplicate.samples.exists())
                for sample in self.sample_series.samples.all():
                    duplicate.samples.get(
                        owner=creator,
                        timestep=sample.timestep,
                        datetime=sample.datetime,
                    )
            elif field.name == "temporal_distributions":
                self.assertTrue(self.sample_series.temporal_distributions.exists())
                self.assertTrue(duplicate.temporal_distributions.exists())
                self.assertQuerySetEqual(
                    duplicate.temporal_distributions.all().order_by("id"),
                    self.sample_series.temporal_distributions.all().order_by("id"),
                )

    def test_clean_prevents_publishing_empty_series(self):
        """Test that clean() raises ValidationError when trying to publish an empty series."""
        # Temporarily disconnect the auto-creation signal to create a truly empty series
        with mute_signals(signals.post_save):
            empty_series = SampleSeries.objects.create(material=self.material1)

        empty_series.publication_status = SampleSeries.STATUS_PUBLISHED

        with self.assertRaises(ValidationError) as context:
            empty_series.clean()

        self.assertIn(
            "Cannot publish a sample series that contains no samples",
            str(context.exception),
        )

    def test_clean_allows_publishing_series_with_samples(self):
        """Test that clean() allows publishing when series has samples."""
        series_with_sample = SampleSeries.objects.create(material=self.material1)
        Sample.objects.create(
            material=self.material1,
            series=series_with_sample,
            timestep=Timestep.objects.default(),
        )
        series_with_sample.publication_status = SampleSeries.STATUS_PUBLISHED

        # Should not raise any exception
        try:
            series_with_sample.clean()
        except ValidationError:
            self.fail(
                "clean() raised ValidationError unexpectedly for series with samples"
            )

    def test_approve_blocks_empty_series(self):
        """Test that approve() raises ValidationError when trying to approve an empty series."""
        # Temporarily disconnect the auto-creation signal to create a truly empty series
        with mute_signals(signals.post_save):
            empty_series = SampleSeries.objects.create(material=self.material1)

        empty_series.publication_status = SampleSeries.STATUS_REVIEW

        with self.assertRaises(ValidationError) as context:
            empty_series.approve()

        self.assertIn(
            "Cannot approve a sample series that contains no samples",
            str(context.exception),
        )
        # Series should remain in review status
        self.assertEqual(empty_series.publication_status, SampleSeries.STATUS_REVIEW)

    def test_approve_allows_series_with_samples(self):
        """Test that approve() works when series has samples."""
        series_with_sample = SampleSeries.objects.create(material=self.material1)
        series_with_sample.publication_status = SampleSeries.STATUS_REVIEW
        Sample.objects.create(
            material=self.material1,
            series=series_with_sample,
            timestep=Timestep.objects.default(),
        )

        # Should not raise any exception and should approve the series
        try:
            series_with_sample.approve()
        except ValidationError:
            self.fail(
                "approve() raised ValidationError unexpectedly for series with samples"
            )

        self.assertEqual(
            series_with_sample.publication_status, SampleSeries.STATUS_PUBLISHED
        )


class MaterialPropertyValueTestCase(TestCase):
    def test_duplicate_creates_new_instance_with_identical_field_values(self):
        prop = MaterialProperty.objects.create(name="Test Property")
        basis = MaterialComponent.objects.create(name="Dry Matter")
        unit = Unit.objects.create(name="g/kg")
        value = MaterialPropertyValue.objects.create(
            property=prop,
            basis_component=basis,
            unit=unit,
            average=Decimal("27.3"),
            standard_deviation=Decimal("0.1337"),
        )
        creator = User.objects.create(username="creator")
        duplicate = value.duplicate(creator)
        self.assertIsInstance(duplicate, MaterialPropertyValue)
        self.assertNotEqual(duplicate, value)
        self.assertEqual(duplicate.owner, creator)
        self.assertEqual(duplicate.property, value.property)
        self.assertEqual(duplicate.basis_component, value.basis_component)
        self.assertEqual(duplicate.unit, value.unit)
        self.assertEqual(duplicate.average, value.average)
        self.assertEqual(duplicate.standard_deviation, value.standard_deviation)

    def test_display_standard_deviation_is_none_when_missing(self):
        prop = MaterialProperty.objects.create(name="Nitrogen", unit="g/kg")
        unit = Unit.objects.create(name="mg/kg")
        value = MaterialPropertyValue.objects.create(
            property=prop,
            unit=unit,
            average=Decimal("27.3"),
            standard_deviation=None,
        )

        self.assertIsNone(value.display_standard_deviation)

    def test_shared_numeric_measurement_properties_are_available(self):
        prop = MaterialProperty.objects.create(name="Nitrogen", unit="g/kg")
        unit = Unit.objects.create(name="mg/kg")
        value = MaterialPropertyValue.objects.create(
            property=prop,
            unit=unit,
            average=Decimal("27.3"),
            standard_deviation=Decimal("0.1337"),
        )

        self.assertEqual(value.measurement_name, prop.name)
        self.assertEqual(value.measurement_unit_label, unit.name)
        self.assertEqual(value.display_average, value.average)
        self.assertEqual(value.display_standard_deviation, value.standard_deviation)

    def test_related_sample_prefers_direct_sample_fk(self):
        material = Material.objects.create(name="Digestate")
        sample = Sample.objects.create(name="Owned Sample", material=material)
        prop = MaterialProperty.objects.create(name="Nitrogen", unit="g/kg")
        unit = Unit.objects.create(name="mg/kg")
        value = MaterialPropertyValue.objects.create(
            sample=sample,
            property=prop,
            unit=unit,
            average=Decimal("27.3"),
            standard_deviation=Decimal("0.1337"),
        )

        self.assertEqual(value.related_sample, sample)


class ComponentMeasurementTestCase(TestCase):
    def test_display_standard_deviation_is_none_when_missing(self):
        material = Material.objects.create(name="Digestate")
        sample = Sample.objects.create(name="Sample", material=material)
        group = MaterialComponentGroup.objects.create(name="Chemical elements")
        component = MaterialComponent.objects.create(name="Carbon")
        unit = Unit.objects.create(name="%")
        measurement = ComponentMeasurement.objects.create(
            sample=sample,
            group=group,
            component=component,
            unit=unit,
            average=Decimal("42.0"),
            standard_deviation=None,
        )

        self.assertIsNone(measurement.display_standard_deviation)


class SampleTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        MaterialComponentGroup.objects.create(name="Custom Group")
        MaterialComponent.objects.create(name="Custom Component")
        material = Material.objects.create(name="Test Material")

        with mute_signals(signals.post_save):
            series = SampleSeries.objects.create(name="Test Series", material=material)
            Sample.objects.create(
                material=material, series=series, timestep=Timestep.objects.default()
            )

        prop = MaterialProperty.objects.create(name="Test Property", unit="Test Unit")
        MaterialPropertyValue.objects.create(
            property=prop, average=Decimal("12.3"), standard_deviation=Decimal("0.321")
        )

    def setUp(self):
        self.sample = Sample.objects.get(timestep=Timestep.objects.default())
        self.default_group = MaterialComponentGroup.objects.default()
        self.default_component = MaterialComponent.objects.default()
        self.custom_component = MaterialComponent.objects.get(name="Custom Component")
        self.composition = Composition.objects.create(
            group=self.default_group,
            sample=self.sample,
            fractions_of=self.default_component,
        )

    def test_duplicate_creates_new_instance_with_identical_field_values(self):
        creator = User.objects.create(username="creator")
        property_value = MaterialPropertyValue.objects.get(average=Decimal("12.3"))
        property_value.sample = self.sample
        property_value.save(update_fields=["sample"])
        duplicate = self.sample.duplicate(creator)
        self.assertIsInstance(duplicate, Sample)
        self.assertNotEqual(duplicate, self.sample)
        self.assertEqual(duplicate.owner, creator)
        for field in self.sample._meta.get_fields():
            if field.concrete and field.name not in [
                "id",
                "owner",
                "image",
                "created_at",
                "lastmodified_at",
                "sources",
            ]:
                if field.name == "name":
                    self.assertEqual(duplicate.name, f"{self.sample.name} (copy)")
                else:
                    self.assertEqual(
                        getattr(duplicate, field.name), getattr(self.sample, field.name)
                    )
            elif field.name == "compositions":
                self.assertTrue(self.sample.compositions.exists())
                self.assertTrue(duplicate.compositions.exists())
                for composition in self.sample.compositions.all():
                    duplicate.compositions.get(
                        owner=creator,
                        group=composition.group,
                        fractions_of=composition.fractions_of,
                    )

        self.assertTrue(self.sample.property_values.exists())
        self.assertTrue(duplicate.property_values.exists())
        for prop in self.sample.property_values.all():
            duplicate.property_values.get(
                owner=creator,
                property=prop.property,
                average=prop.average,
                standard_deviation=prop.standard_deviation,
            )

    def test_components_include_raw_component_measurements(self):
        raw_component = MaterialComponent.objects.create(name="Raw Sample Component")
        unit = Unit.objects.create(name="Sample component percent")
        ComponentMeasurement.objects.create(
            sample=self.sample,
            group=self.default_group,
            component=raw_component,
            unit=unit,
            average=Decimal("42.0"),
        )

        self.assertIn(raw_component, self.sample.components)


class CompositionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        User.objects.create(username="standard_user")
        custom_distribution = TemporalDistribution.objects.create(
            name="Custom Distribution"
        )
        main_step1 = Timestep.objects.create(
            name="Timestep 1", distribution=custom_distribution
        )
        main_step2 = Timestep.objects.create(
            name="Timestep 2", distribution=custom_distribution
        )
        MaterialComponentGroup.objects.create(
            name="Custom Group",
        )

        MaterialComponent.objects.create(
            name="Custom Component",
        )

        with mute_signals(signals.post_save):
            material1 = Material.objects.create(name="Test Material 1")
            sample_series = SampleSeries.objects.create(
                material=material1, standard=True
            )
            Sample.objects.create(
                material=material1,
                series=sample_series,
                timestep=Timestep.objects.default(),
            )
            Sample.objects.create(
                material=material1, series=sample_series, timestep=main_step1
            )
            Sample.objects.create(
                material=material1, series=sample_series, timestep=main_step2
            )

    def setUp(self):
        self.user = User.objects.get(username="standard_user")
        self.material1 = Material.objects.get(name="Test Material 1")
        self.sample0 = Sample.objects.get(timestep=Timestep.objects.default())
        self.default_distribution = TemporalDistribution.objects.default()
        self.custom_distribution = TemporalDistribution.objects.get(
            name="Custom Distribution"
        )
        self.default_group = MaterialComponentGroup.objects.default()
        self.custom_group = MaterialComponentGroup.objects.get(name="Custom Group")
        self.default_component = MaterialComponent.objects.default()
        self.custom_component = MaterialComponent.objects.get(name="Custom Component")
        self.composition = Composition.objects.create(
            owner=self.user,
            group=self.default_group,
            sample=self.sample0,
            fractions_of=self.default_component,
        )

    def test_composition_create_with_signal(self):
        self.assertEqual(self.composition.timestep, Timestep.objects.default())
        self.assertEqual(self.composition.owner, self.user)

    def test_duplicate_creates_new_instance_with_identical_field_values(self):
        creator = User.objects.create(username="creator")
        duplicate = self.composition.duplicate(creator)
        self.assertIsInstance(duplicate, Composition)
        self.assertNotEqual(self.composition, duplicate)
        self.assertEqual(duplicate.owner, creator)
        for field in self.composition._meta.get_fields():
            if field.concrete and field.name not in [
                "id",
                "owner",
                "created_at",
                "lastmodified_at",
            ]:
                self.assertEqual(
                    getattr(duplicate, field.name),
                    getattr(self.composition, field.name),
                )

    def test_add_next_order_value(self):
        self.assertEqual(self.composition.order, 100)
        second_composition = Composition.objects.create(
            owner=self.user,
            group=self.default_group,
            sample=self.sample0,
            fractions_of=self.default_component,
        )
        self.assertEqual(second_composition.order, 110)

    def test_order_up(self):
        self.assertEqual(self.composition.order, 100)
        second_composition = Composition.objects.create(
            owner=self.user,
            group=self.default_group,
            sample=self.sample0,
            fractions_of=self.default_component,
        )
        self.assertGreater(second_composition.order, self.composition.order)
        self.composition.order_up()
        second_composition.refresh_from_db()
        self.composition.refresh_from_db()
        self.assertLess(second_composition.order, self.composition.order)

    def test_order_up_does_nothing_if_table_is_already_last(self):
        self.assertEqual(self.composition.order, 100)
        self.composition.order_up()
        self.composition.refresh_from_db()
        self.assertEqual(self.composition.order, 100)

    def test_order_down(self):
        self.assertEqual(self.composition.order, 100)
        second_composition = Composition.objects.create(
            owner=self.user,
            group=self.default_group,
            sample=self.sample0,
            fractions_of=self.default_component,
        )
        self.assertGreater(second_composition.order, self.composition.order)
        second_composition.order_down()
        second_composition.refresh_from_db()
        self.composition.refresh_from_db()
        self.assertLess(second_composition.order, self.composition.order)

    def test_order_down_does_nothing_if_table_is_already_first(self):
        self.assertEqual(self.composition.order, 100)
        self.composition.order_down()
        self.composition.refresh_from_db()
        self.assertEqual(self.composition.order, 100)
