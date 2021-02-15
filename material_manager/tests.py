from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import signals
from django.db.utils import IntegrityError
from django.test import TestCase
from factory.django import mute_signals

from flexibi_dst.models import TemporalDistribution, Timestep
from material_manager.models import (
    Material,
    MaterialSettings,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialComponentGroupSettings,
    MaterialComponentShare,
    CompositionSet,
    BaseObjects
)


class BaseObjectsTestCase(TestCase):

    def setUp(self):
        self.standard_owner = User.objects.create(username='flexibi')
        self.base_distribution = TemporalDistribution.objects.create(
            name='Average',
            owner=self.standard_owner
        )
        pass

    def test_base_objects(self):
        standard_owner = BaseObjects.get.standard_owner()
        self.assertIsInstance(standard_owner, User)
        self.assertEqual(User.objects.all().count(), 1)
        self.assertEqual(standard_owner.username, 'flexibi')
        standard_owner = BaseObjects.get.standard_owner()
        self.assertIsInstance(standard_owner, User)
        self.assertEqual(User.objects.all().count(), 1)
        self.assertEqual(standard_owner.username, 'flexibi')

        base_group = BaseObjects.get.base_group()
        self.assertIsInstance(base_group, MaterialComponentGroup)
        self.assertEqual(MaterialComponentGroup.objects.all().count(), 1)
        self.assertEqual(base_group.name, 'Total Material')
        self.assertEqual(base_group.owner, standard_owner)
        base_group = BaseObjects.get.base_group()
        self.assertIsInstance(base_group, MaterialComponentGroup)
        self.assertEqual(MaterialComponentGroup.objects.all().count(), 1)
        self.assertEqual(base_group.name, 'Total Material')

        base_component = BaseObjects.get.base_component()
        self.assertIsInstance(base_component, MaterialComponent)
        self.assertEqual(MaterialComponent.objects.all().count(), 1)
        self.assertEqual(base_component.name, 'Fresh Matter (FM)')
        self.assertEqual(base_component.owner, standard_owner)
        base_component = BaseObjects.get.base_component()
        self.assertIsInstance(base_component, MaterialComponent)
        self.assertEqual(MaterialComponent.objects.all().count(), 1)
        self.assertEqual(base_component.name, 'Fresh Matter (FM)')

        base_distribution = BaseObjects.get.base_distribution()
        self.assertIsInstance(base_distribution, TemporalDistribution)
        self.assertEqual(TemporalDistribution.objects.all().count(), 1)
        self.assertEqual(base_distribution.name, 'Average')
        self.assertEqual(base_distribution.owner, standard_owner)
        base_distribution = BaseObjects.get.base_distribution()
        self.assertIsInstance(base_distribution, TemporalDistribution)
        self.assertEqual(TemporalDistribution.objects.all().count(), 1)
        self.assertEqual(base_distribution.name, 'Average')

        base_timestep = BaseObjects.get.base_timestep()
        self.assertIsInstance(base_timestep, Timestep)
        self.assertEqual(Timestep.objects.all().count(), 1)
        self.assertEqual(base_timestep.name, 'Average')
        self.assertEqual(base_timestep.owner, standard_owner)
        base_timestep = BaseObjects.get.base_timestep()
        self.assertIsInstance(base_timestep, Timestep)
        self.assertEqual(Timestep.objects.all().count(), 1)
        self.assertEqual(base_timestep.name, 'Average')

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TemporalDistribution.objects.create(
                    name='Average',
                    owner=standard_owner
                )
        first_base_distribution = BaseObjects.get.base_distribution()
        second_base_distribution = TemporalDistribution.objects.get(name='Average')
        self.assertEqual(first_base_distribution, second_base_distribution)


class MaterialTestCase(TestCase):

    def setUp(self):
        self.superuser = User.objects.create_superuser(username='flexibi')
        self.user = User.objects.create(username='standard_user')
        self.base_distribution = TemporalDistribution.objects.create(
            name='Average',
            owner=self.superuser
        )
        self.main_distribution = TemporalDistribution.objects.create(
            name='Main',
            owner=self.superuser
        )
        self.base_timestep = Timestep.objects.create(
            name='Average',
            owner=self.superuser,
            distribution=self.base_distribution
        )
        self.main_step1 = Timestep.objects.create(
            name='Summer',
            owner=self.superuser,
            distribution=self.main_distribution
        )
        self.main_step2 = Timestep.objects.create(
            name='Winter',
            owner=self.superuser,
            distribution=self.main_distribution
        )
        self.base_group = MaterialComponentGroup.objects.create(
            name='Total Material',
            owner=self.superuser
        )
        self.main_group = MaterialComponentGroup.objects.create(
            name='Basics',
            owner=self.superuser
        )
        self.base_component = MaterialComponent.objects.create(
            name='Fresh Matter (FM)',
            owner=self.superuser
        )
        self.main_component = MaterialComponent.objects.create(
            name='Total Solids (TS)',
            owner=self.superuser
        )
        with mute_signals(signals.post_save):
            self.material1 = Material.objects.create(
                name='First test material',
                owner=self.superuser,
                is_feedstock=True
            )
            self.msettings1 = MaterialSettings.objects.create(
                owner=self.superuser,
                material=self.material1,
                standard=True
            )
        #     material2 = Material.objects.create(
        #         name='Second test material (Not feedstock)',
        #         owner=self.superuser,
        #     )

        # group2 = MaterialComponentGroup.objects.create(
        #     name='Second test group',
        #     owner=superuser
        # )

        # component2 = MaterialComponent.objects.create(
        #     name='Second test component',
        #     owner=superuser
        # )
        # component3 = MaterialComponent.objects.create(
        #     name='Third test component',
        #     owner=superuser
        # )

    def test_material_initialize_standard_settings(self):
        # TODO: Implement check for materials with the same name
        material = Material.objects.create(
            name='Second test material',
            owner=self.user,
            is_feedstock=True
        )
        self.assertEqual(MaterialSettings.objects.all().count(), 2)
        self.assertEqual(MaterialComponentGroupSettings.objects.all().count(), 1)
        self.assertEqual(CompositionSet.objects.all().count(), 1)
        self.assertEqual(MaterialComponentShare.objects.all().count(), 1)
        self.assertEqual(material.materialsettings_set.all().count(), 1)
        self.assertEqual(material.materialsettings_set.filter(standard=True).count(), 1)

        msettings = MaterialSettings.objects.get(material=material)
        self.assertEqual(msettings.material, material)
        self.assertEqual(msettings.owner, self.user)
        self.assertTrue(msettings.standard)

        standard_settings = material.standard_settings
        self.assertEqual(standard_settings.material, material)
        self.assertEqual(standard_settings.owner, self.user)
        self.assertTrue(standard_settings.standard)

        gsettings = MaterialComponentGroupSettings.objects.get(material_settings=msettings)
        self.assertEqual(gsettings.owner, self.user)
        self.assertEqual(gsettings.group, self.base_group)
        self.assertEqual(gsettings.fractions_of, self.base_component)
        self.assertEqual(gsettings.sources.count(), 0)
        self.assertEqual(gsettings.components().count(), 1)

        self.assertEqual(gsettings.temporal_distributions.count(), 1)
        dist = gsettings.temporal_distributions.first()
        self.assertEqual(dist, self.base_distribution)

        composition_set = CompositionSet.objects.get(group_settings=gsettings)
        self.assertEqual(composition_set.owner, self.user)
        self.assertEqual(composition_set.timestep, self.base_timestep)

        share = MaterialComponentShare.objects.get(composition_set=composition_set)
        self.assertEqual(share.owner, self.user)
        self.assertEqual(share.component, self.base_component)
        self.assertEqual(share.average, 0.0)
        self.assertEqual(share.standard_deviation, 0.0)

    def test_material_settings_add_component_group(self):
        material = Material.objects.create(
            name='Second test material',
            owner=self.user,
            is_feedstock=True
        )
        settings = material.standard_settings
        main_group_settings = settings.add_component_group(self.main_group)
        self.assertEqual(main_group_settings,
                         MaterialComponentGroupSettings.objects.get(material_settings=settings, group=self.main_group))

        self.assertEqual(settings.materialcomponentgroupsettings_set.all().count(), 2)
        self.assertEqual(MaterialComponentGroupSettings.objects.all().count(), 2)
        self.assertEqual(
            list(MaterialComponentGroupSettings.objects.all()),
            list(settings.materialcomponentgroupsettings_set.all())
        )
        self.assertEqual(main_group_settings.components().count(), 0)
        self.assertEqual(main_group_settings.compositionset_set.all().count(), 1)
        self.assertEqual(main_group_settings.compositionset_set.first().timestep.name, 'Average')

    def test_group_settings_add_temporal_distribution(self):
        with mute_signals(signals.post_save):
            settings = MaterialComponentGroupSettings.objects.create(
                owner=self.user,
                group=self.base_group,
                material_settings=self.msettings1,
                fractions_of=self.base_component
            )
            settings.add_temporal_distribution(self.base_distribution)
        self.assertEqual(settings.temporal_distributions.all().count(), 1)
        self.assertEqual(settings.temporal_distributions.first(), self.base_distribution)
        self.assertEqual(settings.compositionset_set.all().count(), 1)
        composition = settings.compositionset_set.first()
        self.assertEqual(composition.timestep, self.base_timestep)
        self.assertEqual(composition.group_settings, settings)
        self.assertEqual(composition.owner, self.user)

        settings.add_temporal_distribution(self.main_distribution)
        self.assertEqual(settings.temporal_distributions.all().count(), 2)
        self.assertEqual(settings.compositionset_set.all().count(), 3)
        summer_composition = settings.compositionset_set.get(timestep__name='Summer')
        self.assertEqual(summer_composition.timestep, self.main_step1)
        self.assertEqual(summer_composition.materialcomponentshare_set.all().count(), 0)
        winter_composition = settings.compositionset_set.get(timestep__name='Winter')
        self.assertEqual(winter_composition.timestep, self.main_step2)
        self.assertEqual(winter_composition.materialcomponentshare_set.all().count(), 0)

    def test_group_settings_add_component(self):
        with mute_signals(signals.post_save):
            settings = MaterialComponentGroupSettings.objects.create(
                owner=self.user,
                group=self.base_group,
                material_settings=self.msettings1,
                fractions_of=self.base_component
            )
        settings.add_temporal_distribution(self.base_distribution)
        settings.add_component(self.base_component)

        self.assertEqual(settings.components().count(), 1)
        self.assertEqual(settings.components().first(), self.base_component)

        settings.add_component(self.main_component)
        self.assertEqual(settings.components().count(), 2)
        self.assertEqual(CompositionSet.objects.all().count(), 1)

        composition_set = settings.compositionset_set.first()
        self.assertEqual(composition_set.materialcomponentshare_set.all().count(), 2)
        self.assertEqual(MaterialComponentShare.objects.all().count(), 2)

    def test_group_settings_create_with_signal(self):
        settings = MaterialComponentGroupSettings.objects.create(
            owner=self.user,
            group=self.base_group,
            material_settings=self.msettings1,
            fractions_of=self.base_component
        )
        self.assertEqual(settings.temporal_distributions.all().count(), 1)
        self.assertEqual(settings.temporal_distributions.first(), self.base_distribution)
        self.assertEqual(settings.compositionset_set.all().count(), 1)
        composition = settings.compositionset_set.first()
        self.assertEqual(composition.timestep, self.base_timestep)
        self.assertEqual(composition.group_settings, settings)
        self.assertEqual(composition.owner, self.user)

        settings.add_component(self.base_component)
        self.assertEqual(settings.components().count(), 1)
        self.assertEqual(settings.components().first(), self.base_component)

    def test_group_settings_add_component_on_distribution(self):
        settings = MaterialComponentGroupSettings.objects.create(
            owner=self.user,
            group=self.base_group,
            material_settings=self.msettings1,
            fractions_of=self.base_component
        )
        settings.add_component(self.base_component)
        settings.add_temporal_distribution(self.main_distribution)
        settings.add_component(self.main_component)

        self.assertEqual(settings.temporal_distributions.all().count(), 2)
        self.assertEqual(settings.components().count(), 2)
        self.assertEqual(settings.compositionset_set.all().count(), 3)
        self.assertEqual(MaterialComponentShare.objects.all().count(), 6)

    def test_group_settings_add_distribution_on_component(self):
        settings = MaterialComponentGroupSettings.objects.create(
            owner=self.user,
            group=self.base_group,
            material_settings=self.msettings1,
            fractions_of=self.base_component
        )
        settings.add_component(self.base_component)
        settings.add_component(self.main_component)
        settings.add_temporal_distribution(self.main_distribution)

        self.assertEqual(settings.temporal_distributions.all().count(), 2)
        self.assertEqual(settings.components().count(), 2)
        self.assertEqual(settings.compositionset_set.all().count(), 3)
        self.assertEqual(MaterialComponentShare.objects.all().count(), 6)

    def test_group_settings_remove_temporal_distribution(self):
        settings = MaterialComponentGroupSettings.objects.create(
            owner=self.user,
            group=self.base_group,
            material_settings=self.msettings1,
            fractions_of=self.base_component
        )
        settings.add_component(self.base_component)
        settings.add_component(self.main_component)
        settings.add_temporal_distribution(self.main_distribution)
        settings.remove_temporal_distribution(self.main_distribution)

        self.assertEqual(settings.temporal_distributions.all().count(), 1)
        self.assertEqual(settings.components().count(), 2)
        self.assertEqual(settings.compositionset_set.all().count(), 1)
        self.assertEqual(MaterialComponentShare.objects.all().count(), 2)

    def test_group_settings_remove_component(self):
        settings = MaterialComponentGroupSettings.objects.create(
            owner=self.user,
            group=self.base_group,
            material_settings=self.msettings1,
            fractions_of=self.base_component
        )
        settings.add_component(self.base_component)
        settings.add_component(self.main_component)
        settings.add_temporal_distribution(self.main_distribution)
        settings.remove_component(self.main_component)

        self.assertEqual(settings.temporal_distributions.all().count(), 2)
        self.assertEqual(settings.components().count(), 1)
        self.assertEqual(settings.compositionset_set.all().count(), 3)
        self.assertEqual(MaterialComponentShare.objects.all().count(), 3)

    def test_material_settings_create(self):
        settings = MaterialSettings.objects.create(
            owner=self.user,
            material=self.material1,
            standard=True
        )
        self.assertIsInstance(settings, MaterialSettings)
        self.assertEqual(MaterialSettings.objects.all().count(), 2)

    def test_material_create_copy(self):
        material = Material.objects.create(
            name='Second test material',
            owner=self.user,
            is_feedstock=True
        )
        standard_settings = material.standard_settings
        self.assertEqual(standard_settings.materialcomponentgroupsettings_set.all().count(), 1)
        base_group_settings = MaterialComponentGroupSettings.objects.first()
        self.assertEqual(base_group_settings.temporal_distributions.all().count(), 1)
        self.assertEqual(base_group_settings.components().count(), 1)
        self.assertEqual(base_group_settings.compositionset_set.all().count(), 1)
        main_group_settings = standard_settings.add_component_group(self.main_group)
        self.assertEqual(standard_settings.materialcomponentgroupsettings_set.all().count(), 2)
        main_group_settings.add_temporal_distribution(self.main_distribution)
        main_group_settings.add_component(self.main_component)
        self.assertEqual(main_group_settings.temporal_distributions.all().count(), 2)
        self.assertEqual(main_group_settings.components().count(), 1)
        self.assertEqual(main_group_settings.compositionset_set.all().count(), 3)
        self.assertEqual(main_group_settings.shares.all().count(), 3)
        self.assertEqual(MaterialSettings.objects.all().count(), 2)
        self.assertEqual(MaterialComponentGroupSettings.objects.all().count(), 2)
        self.assertEqual(CompositionSet.objects.all().count(), 4)
        self.assertEqual(MaterialComponentShare.objects.all().count(), 4)
        self.assertEqual(main_group_settings.average_composition.timestep.name, 'Average')
        material_settings_copy = material.standard_settings.create_copy(self.user)
        self.assertEqual(MaterialSettings.objects.all().count(), 3)
        print(MaterialComponentGroupSettings.objects.all())
        self.assertEqual(MaterialComponentGroupSettings.objects.all().count(), 4)
        self.assertEqual(CompositionSet.objects.all().count(), 8)
        self.assertEqual(MaterialComponentShare.objects.all().count(), 8)
        self.assertEqual(material.materialsettings_set.all().count(), 2)
        self.assertEqual(material.materialsettings_set.filter(standard=True).count(), 1)
        self.assertEqual(material.materialsettings_set.filter(standard=False).count(), 1)

    def test_component_group(self):
        pass

    def test_shares(self):
        pass
