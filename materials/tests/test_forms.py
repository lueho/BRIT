from django.contrib.auth.models import User, Group, Permission
from django.forms import inlineformset_factory
from django.test import TestCase

from ..forms import MaterialComponentShareModelForm, MaterialComponentShareInlineFormset
from ..models import Material, MaterialComponentGroup, MaterialComponentGroupSettings, MaterialComponent, \
    CompositionSet, MaterialComponentShare


class CompositionSetUpdateFormTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create(username='owner', password='very-secure!')
        User.objects.create(username='outsider', password='very-secure!')
        member = User.objects.create(username='member', password='very-secure!')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_compositionset'))
        members.permissions.add(Permission.objects.get(codename='change_materialcomponentshare'))
        member.groups.add(members)

        material = Material.objects.create(
            owner=owner,
            name='Test Material'
        )

        group = MaterialComponentGroup.objects.create(
            owner=owner,
            name='Test Group'
        )
        group_settings = MaterialComponentGroupSettings.objects.create(
            owner=owner,
            group=group,
            material_settings=material.standard_settings,
            fractions_of=MaterialComponent.objects.default()
        )

        composition_set = CompositionSet.objects.get(
            owner=owner,
            group_settings=group_settings
        )

        for i in range(5):
            component = MaterialComponent.objects.create(
                owner=owner,
                name=f'Test Component {i}'
            )
            MaterialComponentShare.objects.create(
                owner=owner,
                component=component,
                composition_set=composition_set,
                average=0.2,
                standard_deviation=0.01
            )

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.composition_set = CompositionSet.objects.get(
            group_settings__group__name='Test Group'
        )
        self.material = Material.objects.get(
            owner=self.owner,
            name='Test Material'
        )

    def test_initial_values_are_displayed_as_percentages(self):
        FormSet = inlineformset_factory(
            CompositionSet,
            MaterialComponentShare,
            form=MaterialComponentShareModelForm,
            formset=MaterialComponentShareInlineFormset,
            extra=0
        )
        formset = FormSet(instance=self.composition_set)
        averages_sum = 0
        for form in formset:
            component = MaterialComponent.objects.get(id=form['component'].value())
            share = MaterialComponentShare.objects.get(component=component)
            self.assertEqual(form['average'].value(), share.average * 100)
            self.assertEqual(form['standard_deviation'].value(), share.standard_deviation * 100)
            averages_sum += form['average'].value()
        self.assertEqual(averages_sum, 100)

    def test_input_percentages_are_stored_as_fractions_of_one(self):
        FormSet = inlineformset_factory(
            CompositionSet,
            MaterialComponentShare,
            form=MaterialComponentShareModelForm,
            formset=MaterialComponentShareInlineFormset,
            extra=0
        )
        components = [c.id for c in MaterialComponent.objects.exclude(name='Fresh Matter (FM)')]
        data = {
            'materialcomponentshare_set-INITIAL_FORMS': '0',
            'materialcomponentshare_set-TOTAL_FORMS': '2',
            'materialcomponentshare_set-0-id': '',
            'materialcomponentshare_set-0-component': f'{components[0]}',
            'materialcomponentshare_set-0-average': '45.5',
            'materialcomponentshare_set-0-standard_deviation': '1.5',
            'materialcomponentshare_set-1-id': '',
            'materialcomponentshare_set-1-component': f'{components[1]}',
            'materialcomponentshare_set-1-average': '54.5',
            'materialcomponentshare_set-1-standard_deviation': '1.5',
        }
        formset = FormSet(data=data, instance=self.composition_set)
        formset.is_valid()
        self.assertTrue(formset.is_valid())
        for form in formset:
            form.instance.owner = self.owner
        shares = formset.save()
        for share in shares:
            self.assertLessEqual(share.average, 1)
            self.assertEqual(share.standard_deviation, 0.015)

    def test_form_valid_if_averages_sum_up_to_100_percent(self):
        FormSet = inlineformset_factory(
            CompositionSet,
            MaterialComponentShare,
            form=MaterialComponentShareModelForm,
            formset=MaterialComponentShareInlineFormset,
            extra=0
        )
        components = [c.id for c in MaterialComponent.objects.exclude(name='Fresh Matter (FM)')]
        data = {
            'materialcomponentshare_set-INITIAL_FORMS': '0',
            'materialcomponentshare_set-TOTAL_FORMS': '2',
            'materialcomponentshare_set-0-id': '',
            'materialcomponentshare_set-0-component': f'{components[0]}',
            'materialcomponentshare_set-0-average': '45.5',
            'materialcomponentshare_set-0-standard_deviation': '1.5',
            'materialcomponentshare_set-1-id': '',
            'materialcomponentshare_set-1-component': f'{components[1]}',
            'materialcomponentshare_set-1-average': '54.5',
            'materialcomponentshare_set-1-standard_deviation': '1.5',
        }
        formset = FormSet(data=data, instance=self.composition_set)
        formset.is_valid()
        self.assertTrue(formset.is_valid())
        for form in formset:
            form.instance.owner = self.owner
        formset.save()
        for share in MaterialComponentShare.objects.all():
            self.assertLessEqual(share.average, 1)
            self.assertGreaterEqual(share.average, 0)

    def test_form_invalid_if_averages_dont_sum_up_to_100_percent(self):
        FormSet = inlineformset_factory(
            CompositionSet,
            MaterialComponentShare,
            form=MaterialComponentShareModelForm,
            formset=MaterialComponentShareInlineFormset,
            extra=0
        )
        components = [c.id for c in MaterialComponent.objects.exclude(name='Fresh Matter (FM)')]
        data = {
            'form-INITIAL_FORMS': '0',
            'form-TOTAL_FORMS': '2',
            'form-0-id': '',
            'form-0-component': f'{components[0]}',
            'form-0-average': '999',
            'form-0-standard_deviation': '0.01',
            'form-1-id': '',
            'form-1-component': f'{components[1]}',
            'form-1-average': '999',
            'form-1-standard_deviation': '0.01',
        }
        formset = FormSet(data=data)
        self.assertFalse(formset.is_valid())
        self.assertIn('Weight shares of components must sum up to 100%', formset.non_form_errors())
        for share in MaterialComponentShare.objects.all():
            self.assertLessEqual(share.average, 1)
            self.assertGreaterEqual(share.average, 0)
