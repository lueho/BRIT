from unittest import TestCase as NativeTestCase

from django.contrib.auth.models import User
from django.db.models import signals
from django.test import TestCase as DjangoTestCase, tag
from django.urls import reverse
from factory.django import mute_signals
from mock import Mock, patch, PropertyMock, MagicMock

from distributions.models import TemporalDistribution, Timestep
from materials.models import (
    Material,
    MaterialSettings,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialComponentGroupSettings,
    MaterialComponentShare,
    CompositionSet
)
from users.models import get_default_owner


@tag('db')
class MaterialSetupTestCase(DjangoTestCase):

    def setUp(self):
        self.material = Material.objects.create(
            name='Test material',
            owner=get_default_owner(),
        )

    def test_true(self):
        self.assertTrue(True)


@tag('db')
class MaterialTestCase(DjangoTestCase):

    def setUp(self):
        self.superuser = get_default_owner()
        self.user = User.objects.create(username='standard_user')
        self.base_distribution = TemporalDistribution.objects.default()
        self.main_distribution = TemporalDistribution.objects.create(
            name='Main',
            owner=self.superuser
        )
        self.base_timestep = Timestep.objects.default()
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
        self.base_group = MaterialComponentGroup.objects.default()
        self.main_group = MaterialComponentGroup.objects.create(
            name='Basics',
            owner=self.superuser
        )
        self.base_component = MaterialComponent.objects.default()
        self.main_component = MaterialComponent.objects.create(
            name='Total Solids (TS)',
            owner=self.superuser
        )
        with mute_signals(signals.post_save):
            self.material1 = Material.objects.create(
                name='First test material',
                owner=self.superuser,
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
        self.assertEqual(MaterialSettings.objects.all().count(), 3)
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


@tag('db')
class CompositionSetTestCaseDB(DjangoTestCase):
    def test_add_component(self):
        self.assertTrue(True)


class CompositionSetTestCase(NativeTestCase):

    def test_get_absolute_url(self):
        composition_set = CompositionSet()
        group_settings = Mock(spec=MaterialComponentGroupSettings)
        group_settings._state = Mock()
        group_settings.get_absolute_url = MagicMock(return_value='test_url')
        composition_set.group_settings = group_settings
        self.assertEqual(composition_set.get_absolute_url(), 'test_url')


class MaterialComponentShareTestCase(NativeTestCase):

    @patch('materials.models.MaterialComponentShare.material_settings', new_callable=PropertyMock)
    def test_property_material(self, mock_material_settings):
        material = Mock(spec=Material)
        material.name = 'Test material'
        material._state = Mock()
        material_settings = Mock(spec=MaterialSettings)
        material_settings._state = Mock()
        material_settings.material = material
        mock_material_settings.return_value = material_settings
        share = MaterialComponentShare()
        self.assertEqual(share.material.name, 'Test material')

    @patch('materials.models.MaterialComponentShare.group_settings', new_callable=PropertyMock)
    def test_property_material_settings(self, mock_group_settings):
        material_settings = Mock(spec=MaterialSettings)
        material_settings.name = 'Test settings'
        material_settings._state = Mock()
        group_settings = Mock(spec=MaterialComponentGroupSettings)
        group_settings.material_settings = material_settings
        group_settings._state = Mock()
        mock_group_settings.return_value = group_settings
        share = MaterialComponentShare()
        self.assertEqual(share.material_settings.name, 'Test settings')

    @patch('materials.models.MaterialComponentShare.group_settings', new_callable=PropertyMock)
    def test_property_group(self, mock_group_settings):
        group = Mock(spec=MaterialComponentGroup)
        group.name = 'Test group'
        group._status = Mock()
        group_settings = Mock(spec=MaterialComponentGroupSettings)
        group_settings.group = group
        group_settings._status = Mock()
        mock_group_settings.return_value = group_settings
        share = MaterialComponentShare()
        self.assertEqual(share.group.name, 'Test group')

    @patch('materials.models.MaterialComponentShare.composition_set', new_callable=PropertyMock)
    def test_property_group_settings(self, mock_composition_set):
        group_settings = Mock(spec=MaterialComponentGroupSettings)
        group_settings.id = 5
        group_settings._status = Mock()
        composition_set = Mock(spec=CompositionSet)
        composition_set.group_settings = group_settings
        composition_set._status = Mock()
        mock_composition_set.return_value = composition_set
        share = MaterialComponentShare()
        self.assertEqual(share.group_settings.id, 5)

    @patch('materials.models.MaterialComponentShare.composition_set', new_callable=PropertyMock)
    def test_property_timestep(self, mock_composition_set):
        timestep = Mock(spec=Timestep)
        timestep.name = 'Test timestep'
        timestep._status = Mock()
        composition_set = Mock(spec=CompositionSet)
        composition_set.timestep = timestep
        composition_set._status = Mock()
        mock_composition_set.return_value = composition_set
        share = MaterialComponentShare()
        self.assertEqual(share.timestep.name, 'Test timestep')

    @patch('materials.models.MaterialComponentShare.material_settings', new_callable=PropertyMock)
    def test_get_absolute_url(self, mock_material_settings):
        material_settings = Mock(spec=MaterialSettings)
        material_settings.id = 4
        material_settings._status = Mock()
        mock_material_settings.return_value = material_settings
        share = MaterialComponentShare()
        self.assertEqual(share.get_absolute_url(), reverse('material_settings', kwargs={'pk': 4}))

    @patch('materials.models.MaterialComponentShare.material', new_callable=PropertyMock)
    def test_str(self, mock_material):
        component = Mock(spec=MaterialComponent)
        component.name = 'Test component'
        component._state = Mock()
        material = Mock(spec=Material)
        material.name = 'Test material'
        material._state = Mock()
        mock_material.return_value = material
        share = MaterialComponentShare()
        share.component = component
        self.assertEqual(
            share.__str__(),
            'Component share of material: Test material, component: Test component'
        )
