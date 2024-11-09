from decimal import Decimal

from django.contrib.auth.models import Group, Permission, User
from django.forms import inlineformset_factory
from django.test import TestCase

from distributions.models import Timestep
from ..forms import AddComponentModalForm, AddCompositionModalForm, WeightShareInlineFormset, WeightShareModelForm
from ..models import Composition, Material, MaterialComponent, MaterialComponentGroup, Sample, SampleSeries, \
    WeightShare, get_default_owner


class AddComponentGroupModalModelFormTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        material = Material.objects.create(
            owner=owner,
            name='Test Material'
        )
        MaterialComponentGroup.objects.create(
            owner=owner,
            name='Test Group 1'
        )
        MaterialComponentGroup.objects.create(
            owner=owner,
            name='Test Group 2'
        )

    def setUp(self):
        self.owner = get_default_owner()
        self.material = Material.objects.get(name='Test Material')
        self.group1 = MaterialComponentGroup.objects.get(name='Test Group 1')
        self.group2 = MaterialComponentGroup.objects.get(name='Test Group 2')

    def test_initial_group_queryset_has_only_unused_groups(self):
        sample_series = SampleSeries.objects.create(
            owner=self.owner,
            material=self.material
        )
        sample_series.add_component_group(self.group1)
        form = AddCompositionModalForm(instance=sample_series)
        self.assertQuerySetEqual(
            form.fields['group'].queryset.order_by('id'),
            MaterialComponentGroup.objects.filter(name='Test Group 2').order_by('id')
        )

    def test_initial_fractions_of_queryset_has_only_used_components(self):
        sample_series = SampleSeries.objects.create(
            owner=self.owner,
            material=self.material
        )
        form = AddCompositionModalForm(instance=sample_series)
        self.assertQuerySetEqual(
            form.fields['fractions_of'].queryset.order_by('id'),
            MaterialComponent.objects.filter(id=MaterialComponent.objects.default().id).order_by('id')
        )


class AddComponentModalModelFormTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = get_default_owner()
        material = Material.objects.create(
            owner=owner,
            name='Test Material'
        )
        sample_series = SampleSeries.objects.create(
            owner=owner,
            material=material,
            name='Test Series',
        )
        sample = Sample.objects.get(
            owner=owner,
            series=sample_series,
            timestep=Timestep.objects.default()
        )
        component_group = MaterialComponentGroup.objects.create(
            owner=owner,
            name='Test Group'
        )
        Composition.objects.create(
            owner=owner,
            sample=sample,
            group=component_group,
            fractions_of=MaterialComponent.objects.default()
        )

        MaterialComponent.objects.create(
            owner=owner,
            name='Test Component 1'
        )

        MaterialComponent.objects.create(
            owner=owner,
            name='Test Component 2'
        )

    def setUp(self):
        self.owner = get_default_owner()
        self.component_group = MaterialComponentGroup.objects.get(name='Test Group')
        self.sample = Sample.objects.get(series__name='Test Series', timestep=Timestep.objects.default())
        self.composition = Composition.objects.get(sample=self.sample, group=self.component_group)
        self.component1 = MaterialComponent.objects.get(name='Test Component 1')
        self.component2 = MaterialComponent.objects.get(name='Test Component 2')

    def test_initial_component_queryset_contains_only_unused_components(self):
        self.composition.add_component(self.component1, average=0.5, standard_deviation=0.02)
        self.composition.add_component(MaterialComponent.objects.other(), average=0.5, standard_deviation=0.1337)
        form = AddComponentModalForm(instance=self.composition)
        self.assertQuerySetEqual(
            form.fields['component'].queryset.order_by('id'),
            MaterialComponent.objects.filter(name='Test Component 2').order_by('id')
        )


class CompositionUpdateFormTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        owner = User.objects.create(username='owner', password='very-secure!')
        User.objects.create(username='outsider', password='very-secure!')
        member = User.objects.create(username='member', password='very-secure!')
        members = Group.objects.create(name='members')
        members.permissions.add(Permission.objects.get(codename='change_composition'))
        members.permissions.add(Permission.objects.get(codename='change_weightshare'))
        member.groups.add(members)

        material = Material.objects.create(
            owner=owner,
            name='Test Material'
        )

        group = MaterialComponentGroup.objects.create(
            owner=owner,
            name='Test Group'
        )

        SampleSeries.objects.create(
            owner=owner,
            material=material,
            name='Test Series'
        )

        composition = Composition.objects.create(
            owner=owner,
            group=group,
            sample=Sample.objects.get(series__name='Test Series'),
            fractions_of=MaterialComponent.objects.default()
        )

        for i in range(5):
            component = MaterialComponent.objects.create(
                owner=owner,
                name=f'Test Component {i}'
            )
            WeightShare.objects.create(
                owner=owner,
                component=component,
                composition=composition,
                average=Decimal('0.2000000000'),
                standard_deviation=Decimal('0.0500000000')
            )

    def setUp(self):
        self.owner = User.objects.get(username='owner')
        self.outsider = User.objects.get(username='outsider')
        self.member = User.objects.get(username='member')
        self.composition = Composition.objects.get(
            group__name='Test Group'
        )
        self.material = Material.objects.get(
            owner=self.owner,
            name='Test Material'
        )

    def test_initial_values_are_displayed_as_percentages(self):
        FormSet = inlineformset_factory(
            Composition,
            WeightShare,
            form=WeightShareModelForm,
            formset=WeightShareInlineFormset,
            extra=0
        )
        formset = FormSet(instance=self.composition)
        averages_sum = Decimal('0.0')
        for form in formset:
            component = MaterialComponent.objects.get(id=form['component'].value())
            share = WeightShare.objects.get(component=component)
            self.assertEqual(form['average'].value(), share.average * Decimal('100'))
            self.assertEqual(form['standard_deviation'].value(), share.standard_deviation * Decimal('100'))
            averages_sum += form['average'].value()
        self.assertEqual(averages_sum, Decimal('100'))

    def test_input_percentages_are_stored_as_fractions_of_one(self):
        FormSet = inlineformset_factory(
            Composition,
            WeightShare,
            form=WeightShareModelForm,
            formset=WeightShareInlineFormset,
            extra=0
        )
        components = [c.id for c in MaterialComponent.objects.exclude(name='Fresh Matter (FM)')]
        data = {
            'shares-INITIAL_FORMS': '0',
            'shares-TOTAL_FORMS': '2',
            'shares-0-id': '',
            'shares-0-component': f'{components[0]}',
            'shares-0-average': '45.5',
            'shares-0-standard_deviation': '1.5',
            'shares-1-id': '',
            'shares-1-component': f'{components[1]}',
            'shares-1-average': '54.5',
            'shares-1-standard_deviation': '1.5',
        }
        formset = FormSet(data=data, instance=self.composition)
        formset.is_valid()
        self.assertTrue(formset.is_valid())
        for form in formset:
            form.instance.owner = self.owner
        shares = formset.save()
        for share in shares:
            self.assertLessEqual(share.average, Decimal('1'))
            self.assertEqual(share.standard_deviation, Decimal('0.015'))

    def test_form_valid_if_averages_sum_up_to_100_percent(self):
        FormSet = inlineformset_factory(
            Composition,
            WeightShare,
            form=WeightShareModelForm,
            formset=WeightShareInlineFormset,
            extra=0
        )
        components = [c.id for c in MaterialComponent.objects.exclude(name='Fresh Matter (FM)')]
        data = {
            'shares-INITIAL_FORMS': '0',
            'shares-TOTAL_FORMS': '2',
            'shares-0-id': '',
            'shares-0-component': f'{components[0]}',
            'shares-0-average': '45.5',
            'shares-0-standard_deviation': '1.5',
            'shares-1-id': '',
            'shares-1-component': f'{components[1]}',
            'shares-1-average': '54.5',
            'shares-1-standard_deviation': '1.5',
        }
        formset = FormSet(data=data, instance=self.composition)
        formset.is_valid()
        self.assertTrue(formset.is_valid())
        for form in formset:
            form.instance.owner = self.owner
        formset.save()
        for share in WeightShare.objects.all():
            self.assertLessEqual(share.average, Decimal('1'))
            self.assertGreaterEqual(share.average, Decimal('0'))

    def test_form_invalid_if_averages_dont_sum_up_to_100_percent(self):
        FormSet = inlineformset_factory(
            Composition,
            WeightShare,
            form=WeightShareModelForm,
            formset=WeightShareInlineFormset,
            extra=0
        )
        components = [c.id for c in MaterialComponent.objects.exclude(name='Fresh Matter (FM)')]
        data = {
            'shares-INITIAL_FORMS': '0',
            'shares-TOTAL_FORMS': '2',
            'shares-0-id': '',
            'shares-0-component': f'{components[0]}',
            'shares-0-average': '100',
            'shares-0-standard_deviation': '0.01',
            'shares-1-id': '',
            'shares-1-component': f'{components[1]}',
            'shares-1-average': '100',
            'shares-1-standard_deviation': '0.01',
        }
        formset = FormSet(data=data)
        self.assertFalse(formset.is_valid())
        self.assertIn('Weight shares of components must sum up to 100%', formset.non_form_errors())
        for share in WeightShare.objects.all():
            self.assertLessEqual(share.average, Decimal('1'))
            self.assertGreaterEqual(share.average, Decimal('0'))

    def test_form_fields_render_percentage_suffix(self):
        FormSet = inlineformset_factory(
            Composition,
            WeightShare,
            form=WeightShareModelForm,
            formset=WeightShareInlineFormset,
            extra=0
        )
        formset = FormSet(instance=self.composition)
        for form in formset:
            rendered_form = form.as_p()
            self.assertIn('%', rendered_form)
