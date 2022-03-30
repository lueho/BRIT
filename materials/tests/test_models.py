from django.contrib.auth.models import User
from django.db.models import signals
from django.test import TestCase
from django.urls import reverse
from factory.django import mute_signals

from distributions.models import TemporalDistribution, Timestep
from materials.models import (
    Material,
    MaterialComponentGroup,
    MaterialComponent,
    SampleSeries,
    MaterialProperty,
    MaterialPropertyValue,
    Sample,
    Composition,
    WeightShare,
    get_default_component,
    get_default_component_pk
)
from users.models import get_default_owner


class InitialDataTestCase(TestCase):

    def test_base_component_group_is_created_from_migrations(self):
        MaterialComponentGroup.objects.get(name='Total Material')
        self.assertEqual(MaterialComponentGroup.objects.all().count(), 1)

    def test_base_component_is_created_from_migrations(self):
        MaterialComponent.objects.get(name='Fresh Matter (FM)')
        self.assertEqual(MaterialComponent.objects.all().count(), 2)

    def test_other_component_is_created_from_migrations(self):
        MaterialComponent.objects.get(name='Other')
        self.assertEqual(MaterialComponent.objects.all().count(), 2)


class MaterialComponentGroupTestCase(TestCase):

    def test_get_default_material_component_group(self):
        default = MaterialComponentGroup.objects.default()
        self.assertIsInstance(default, MaterialComponentGroup)
        self.assertEqual(default.name, 'Total Material')


class MaterialComponentTestCase(TestCase):

    def test_get_default_material_component_manager_function(self):
        default = MaterialComponent.objects.default()
        self.assertIsInstance(default, MaterialComponent)
        self.assertEqual(default.name, 'Fresh Matter (FM)')

    def test_get_default_material_component_function(self):
        default_component = get_default_component()
        self.assertIsInstance(default_component, MaterialComponent)
        self.assertEqual(default_component.name, 'Fresh Matter (FM)')

    def test_get_default_material_component_pk(self):
        default_component_pk = get_default_component_pk()
        self.assertIsInstance(default_component_pk, int)
        self.assertEqual(default_component_pk, get_default_component().pk)

    def test_get_other_material_component_manager_function(self):
        default = MaterialComponent.objects.other()
        self.assertIsInstance(default, MaterialComponent)
        self.assertEqual(default.name, 'Other')


class MaterialTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='standard_user')
        custom_distribution = TemporalDistribution.objects.create(
            name='Custom Distribution',
            owner=owner
        )
        main_step1 = Timestep.objects.create(
            name='Timestep 1',
            owner=owner,
            distribution=custom_distribution
        )
        main_step2 = Timestep.objects.create(
            name='Timestep 2',
            owner=owner,
            distribution=custom_distribution
        )
        MaterialComponentGroup.objects.create(
            name='Custom Group',
            owner=owner
        )
        MaterialComponent.objects.default()
        MaterialComponent.objects.create(
            name='Custom Component',
            owner=owner
        )

        with mute_signals(signals.post_save):
            material1 = Material.objects.create(
                name='Test Material 1',
                owner=owner,
            )
            sample_series = SampleSeries.objects.create(
                owner=owner,
                material=material1,
                standard=True
            )
            Sample.objects.create(
                owner=owner,
                series=sample_series,
                timestep=Timestep.objects.default()
            )
            Sample.objects.create(
                owner=owner,
                series=sample_series,
                timestep=main_step1
            )
            Sample.objects.create(
                owner=owner,
                series=sample_series,
                timestep=main_step2
            )

    def setUp(self):
        self.user = User.objects.get(username='standard_user')
        self.default_group = MaterialComponentGroup.objects.default()
        self.default_component = MaterialComponent.objects.default()

    def test_true_is_not_false(self):
        self.assertTrue(True)


class SampleSeriesTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='standard_user')
        custom_distribution = TemporalDistribution.objects.create(
            name='Custom Distribution',
            owner=owner
        )
        timestep1 = Timestep.objects.create(
            name='Timestep 1',
            owner=owner,
            distribution=custom_distribution
        )
        timestep2 = Timestep.objects.create(
            name='Timestep 2',
            owner=owner,
            distribution=custom_distribution
        )
        MaterialComponentGroup.objects.create(
            name='Custom Group',
            owner=owner
        )
        MaterialComponent.objects.default()
        MaterialComponent.objects.create(
            name='Custom Component',
            owner=owner
        )

        with mute_signals(signals.post_save):
            material1 = Material.objects.create(
                name='Test Material 1',
                owner=owner,
            )
            sample_series = SampleSeries.objects.create(
                owner=owner,
                material=material1,
                standard=True
            )
            Sample.objects.create(
                owner=owner,
                series=sample_series,
                timestep=Timestep.objects.default()
            )
            Sample.objects.create(
                owner=owner,
                series=sample_series,
                timestep=timestep1
            )
            Sample.objects.create(
                owner=owner,
                series=sample_series,
                timestep=timestep2
            )

    def setUp(self):
        self.user = User.objects.get(username='standard_user')
        self.owner = get_default_owner()
        self.material1 = Material.objects.get(name='Test Material 1')
        self.sample0 = Sample.objects.get(timestep=Timestep.objects.default())
        self.default_distribution = TemporalDistribution.objects.default()
        self.custom_distribution = TemporalDistribution.objects.get(name='Custom Distribution')
        self.default_group = MaterialComponentGroup.objects.default()
        self.custom_group = MaterialComponentGroup.objects.get(name='Custom Group')
        self.default_component = MaterialComponent.objects.default()
        self.custom_component = MaterialComponent.objects.get(name='Custom Component')
        self.sample_series = SampleSeries.objects.create(
            owner=get_default_owner(),
            material=self.material1,
        )

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

    def test_add_component(self):
        self.sample_series.add_component_group(self.custom_group)
        self.sample_series.add_temporal_distribution(self.custom_distribution)
        self.sample_series.add_component(self.custom_component, self.custom_group)

        for sample in self.sample_series.samples.all():
            for composition in sample.compositions.filter(group=self.custom_group):
                WeightShare.objects.get(
                    composition=composition,
                    component=self.custom_component
                )

    def test_remove_component(self):
        self.sample_series.add_component_group(self.custom_group)
        self.sample_series.add_component(self.custom_component, self.custom_group)
        self.sample_series.add_temporal_distribution(self.custom_distribution)
        self.sample_series.remove_component(self.custom_component, self.custom_group)

        for sample in self.sample_series.samples.all():
            for composition in sample.compositions.filter(group=self.custom_group):
                with self.assertRaises(WeightShare.DoesNotExist):
                    WeightShare.objects.get(
                        composition=composition,
                        component=self.custom_component
                    )

    def test_duplicate_creates_new_instance_with_identical_field_values(self):
        creator = User.objects.create(username='creator')
        duplicate = self.sample_series.duplicate(creator)
        self.assertIsInstance(duplicate, SampleSeries)
        self.assertNotEqual(self.sample_series, duplicate)
        self.assertEqual(duplicate.owner, creator)
        for field in self.sample_series._meta.get_fields():
            if field.concrete and field.name not in ['id', 'owner', 'created_at', 'lastmodified_at',
                                                     'visible_to_groups', 'temporal_distributions']:
                self.assertEqual(getattr(duplicate, field.name), getattr(self.sample_series, field.name))
            elif field.name == 'samples':
                self.assertTrue(self.sample_series.samples.exists())
                self.assertTrue(duplicate.samples.exists())
                for sample in self.sample_series.samples.all():
                    duplicate.samples.get(
                        owner=creator,
                        timestep=sample.timestep,
                        taken_at=sample.taken_at,
                    )
            elif field.name == 'temporal_distributions':
                self.assertTrue(self.sample_series.temporal_distributions.exists())
                self.assertTrue(duplicate.temporal_distributions.exists())
                self.assertQuerysetEqual(
                    duplicate.temporal_distributions.all().order_by('id'),
                    self.sample_series.temporal_distributions.all().order_by('id')
                )


class MaterialPropertyTestCase(TestCase):
    pass


class MaterialPropertyValueTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        pass

    def setUp(self):
        self.owner = get_default_owner()

    def test_duplicate_creates_new_instance_with_identical_field_values(self):
        prop = MaterialProperty.objects.create(owner=self.owner, name='Test Property')
        value = MaterialPropertyValue.objects.create(
            owner=self.owner,
            property=prop,
            average=27.3,
            standard_deviation=0.1337
        )
        creator = User.objects.create(username='creator')
        duplicate = value.duplicate(creator)
        self.assertIsInstance(duplicate, MaterialPropertyValue)
        self.assertNotEqual(duplicate, value)
        self.assertEqual(duplicate.owner, creator)
        self.assertEqual(duplicate.property, value.property)
        self.assertEqual(duplicate.average, value.average)
        self.assertEqual(duplicate.standard_deviation, value.standard_deviation)


class SampleTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        MaterialComponentGroup.objects.create(
            name='Custom Group',
            owner=owner
        )
        MaterialComponent.objects.create(
            name='Custom Component',
            owner=owner
        )
        material = Material.objects.create(owner=owner, name='Test Material')

        with mute_signals(signals.post_save):
            series = SampleSeries.objects.create(owner=owner, name='Test Series', material=material)
            Sample.objects.create(
                owner=owner,
                series=series,
                timestep=Timestep.objects.default()
            )

        prop = MaterialProperty.objects.create(owner=owner, name='Test Property', unit='Test Unit')
        MaterialPropertyValue.objects.create(owner=owner, property=prop, average=12.3, standard_deviation=0.321)

    def setUp(self):
        self.owner = get_default_owner()
        self.sample = Sample.objects.get(timestep=Timestep.objects.default())
        self.default_group = MaterialComponentGroup.objects.default()
        self.default_component = MaterialComponent.objects.default()
        self.custom_component = MaterialComponent.objects.get(name='Custom Component')
        self.composition = Composition.objects.create(
            owner=self.owner,
            group=self.default_group,
            sample=self.sample,
            fractions_of=self.default_component
        )

    def test_duplicate_creates_new_instance_with_identical_field_values(self):
        creator = User.objects.create(username='creator')
        property_value = MaterialPropertyValue.objects.get(average=12.3)
        self.sample.properties.add(property_value)
        duplicate = self.sample.duplicate(creator)
        self.assertIsInstance(duplicate, Sample)
        self.assertNotEqual(duplicate, self.sample)
        self.assertEqual(duplicate.owner, creator)
        for field in self.sample._meta.get_fields():
            if field.concrete and field.name not in ['id', 'owner', 'preview', 'created_at', 'lastmodified_at',
                                                     'visible_to_groups', 'properties', 'sources']:
                self.assertEqual(getattr(duplicate, field.name), getattr(self.sample, field.name))
            elif field.name == 'compositions':
                self.assertTrue(self.sample.compositions.exists())
                self.assertTrue(duplicate.compositions.exists())
                for composition in self.sample.compositions.all():
                    duplicate.compositions.get(
                        owner=creator,
                        group=composition.group,
                        fractions_of=composition.fractions_of
                    )
            elif field.name == 'properties':
                self.assertTrue(self.sample.properties.exists())
                self.assertTrue(duplicate.properties.exists())
                for prop in self.sample.properties.all():
                    duplicate.properties.get(
                        owner=creator,
                        property=prop.property,
                        average=prop.average,
                        standard_deviation=prop.standard_deviation
                    )


class CompositionTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        User.objects.create(username='standard_user')
        custom_distribution = TemporalDistribution.objects.create(
            name='Custom Distribution',
            owner=owner
        )
        main_step1 = Timestep.objects.create(
            name='Timestep 1',
            owner=owner,
            distribution=custom_distribution
        )
        main_step2 = Timestep.objects.create(
            name='Timestep 2',
            owner=owner,
            distribution=custom_distribution
        )
        MaterialComponentGroup.objects.create(
            name='Custom Group',
            owner=owner
        )

        MaterialComponent.objects.create(
            name='Custom Component',
            owner=owner
        )

        with mute_signals(signals.post_save):
            material1 = Material.objects.create(
                name='Test Material 1',
                owner=owner,
            )
            sample_series = SampleSeries.objects.create(
                owner=owner,
                material=material1,
                standard=True
            )
            Sample.objects.create(
                owner=owner,
                series=sample_series,
                timestep=Timestep.objects.default()
            )
            Sample.objects.create(
                owner=owner,
                series=sample_series,
                timestep=main_step1
            )
            Sample.objects.create(
                owner=owner,
                series=sample_series,
                timestep=main_step2
            )

    def setUp(self):
        self.owner = get_default_owner()
        self.user = User.objects.get(username='standard_user')
        self.material1 = Material.objects.get(name='Test Material 1')
        self.sample0 = Sample.objects.get(timestep=Timestep.objects.default())
        self.default_distribution = TemporalDistribution.objects.default()
        self.custom_distribution = TemporalDistribution.objects.get(name='Custom Distribution')
        self.default_group = MaterialComponentGroup.objects.default()
        self.custom_group = MaterialComponentGroup.objects.get(name='Custom Group')
        self.default_component = MaterialComponent.objects.default()
        self.custom_component = MaterialComponent.objects.get(name='Custom Component')
        self.composition = Composition.objects.create(
            owner=self.user,
            group=self.default_group,
            sample=self.sample0,
            fractions_of=self.default_component
        )

    def test_add_component(self):
        self.composition.add_temporal_distribution(self.default_distribution)
        self.composition.add_component(self.custom_component)

        WeightShare.objects.get(composition=self.composition, component=self.custom_component)
        self.assertEqual(self.composition.shares.count(), 1)

    def test_composition_create_with_signal(self):
        self.assertEqual(self.composition.timestep, Timestep.objects.default())
        self.assertEqual(self.composition.owner, self.user)

        self.composition.add_component(self.default_component)
        self.assertEqual(self.composition.components().count(), 1)
        self.assertEqual(self.composition.components().first(), self.default_component)

    def test_group_settings_add_component_on_distribution(self):
        self.composition.add_component(self.default_component)
        self.composition.add_temporal_distribution(self.custom_distribution)
        self.composition.add_component(self.custom_component)

        self.assertEqual(self.composition.sample.series.temporal_distributions.all().count(), 1)
        self.assertEqual(self.composition.components().count(), 2)
        self.assertEqual(WeightShare.objects.all().count(), 4)

    def test_group_settings_add_distribution_on_component(self):
        self.composition.add_component(self.default_component)
        self.composition.add_component(self.custom_component)
        self.composition.add_temporal_distribution(self.custom_distribution)

        self.assertEqual(self.composition.sample.series.temporal_distributions.all().count(), 1)
        self.assertEqual(self.composition.components().count(), 2)
        self.assertEqual(WeightShare.objects.all().count(), 4)

    def test_duplicate_creates_new_instance_with_identical_field_values(self):
        creator = User.objects.create(username='creator')
        WeightShare.objects.create(
            owner=self.owner,
            component=self.custom_component,
            composition=self.composition,
            average=0.9,
            standard_deviation=0.1337
        )
        duplicate = self.composition.duplicate(creator)
        self.assertIsInstance(duplicate, Composition)
        self.assertNotEqual(self.composition, duplicate)
        self.assertEqual(duplicate.owner, creator)
        for field in self.composition._meta.get_fields():
            if field.concrete and field.name not in ['id', 'owner', 'created_at', 'lastmodified_at',
                                                     'visible_to_groups']:
                self.assertEqual(getattr(duplicate, field.name), getattr(self.composition, field.name))
            elif field.name == 'shares':
                self.assertTrue(self.composition.shares.exists())
                self.assertTrue(duplicate.shares.exists())
                for share in self.composition.shares.all():
                    duplicate.shares.get(
                        owner=creator,
                        component=share.component,
                        average=share.average,
                        standard_deviation=share.standard_deviation
                    )


class WeightShareTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create(username='owner', password='very-secure!')
        material = Material.objects.create(owner=owner, name='Test Material')
        sample_series = SampleSeries.objects.create(owner=owner, material=material, name='Test Series')
        sample = Sample.objects.create(owner=owner, series=sample_series)
        component_group = MaterialComponentGroup.objects.create(owner=owner, name='Test Group')
        composition = Composition.objects.create(owner=owner, sample=sample, group=component_group)
        component = MaterialComponent.objects.create(owner=owner, name='Test Component')
        WeightShare.objects.create(
            owner=owner,
            composition=composition,
            component=component,
            average=1.0,
            standard_deviation=0.123
        )

    def setUp(self):
        self.share = WeightShare.objects.get(standard_deviation=0.123)
        self.sample_series = SampleSeries.objects.get(name='Test Series')

    def test_property_material(self):
        self.assertEqual(self.share.material.name, 'Test Material')

    def test_property_group(self):
        self.assertEqual(self.share.group.name, 'Test Group')

    def test_get_absolute_url(self):
        self.assertEqual(
            self.share.get_absolute_url(),
            reverse('sampleseries-detail', kwargs={'pk': self.sample_series.pk})
        )

    def test_str(self):
        self.assertEqual(
            self.share.__str__(),
            'Component share of material: Test Material, component: Test Component'
        )

    def test_duplicate_creates_new_instance_with_identical_field_values(self):
        creator = User.objects.create(username='creator')
        duplicate = self.share.duplicate(creator)
        self.assertIsInstance(duplicate, WeightShare)
        self.assertNotEqual(self.share, duplicate)
        self.assertEqual(duplicate.owner, creator)
        for field in self.share._meta.get_fields():
            if field.name not in ['id', 'owner', 'created_at', 'lastmodified_at', 'visible_to_groups']:
                self.assertEqual(getattr(duplicate, field.name), getattr(self.share, field.name))
