"""Boundary regressions for the migrated materials domain writers.

Each case pins one ungoverned-write finding to the shared mutation boundary:
denied actors write nothing and bump no revision; allowed writes run inside
the governed create/edit boundaries and record the revision bump and audit
event on the affected root.
"""

import json
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.http import QueryDict
from django.urls import reverse

from distributions.models import TemporalDistribution, Timestep
from materials.forms import MaterialPropertyValueModelForm
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
    get_sample_substrate_category_name,
)
from utils.object_management.models import ReviewAction
from utils.properties.models import Unit
from utils.tests.testcases import ViewWithPermissionsTestCase


def _events_for(obj):
    return ReviewAction.objects.filter(
        content_type=ContentType.objects.get_for_model(type(obj)),
        object_id=obj.pk,
    )


def _revision(obj):
    return type(obj)._base_manager.get(pk=obj.pk).content_revision


class SubstrateMaterialQuickCreateBoundaryTestCase(ViewWithPermissionsTestCase):
    """Quick-create persists new materials inside the authorized create
    boundary; reusing an existing material attaches the substrate category
    through a governed edit on that root."""

    member_permissions = ["add_material", "change_material"]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.category, _ = MaterialCategory.objects.get_or_create(
            name=get_sample_substrate_category_name(),
            defaults={"publication_status": "published"},
        )

    def post(self, name="GW Substrate"):
        return self.client.post(
            reverse("sample-substrate-material-quick-create"),
            data=json.dumps({"name": name}),
            content_type="application/json",
        )

    def test_post_denied_without_create_capability_writes_nothing(self):
        self.client.force_login(self.outsider)
        response = self.post()
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Material.objects.filter(name="GW Substrate").exists())

    def test_post_authorized_creates_material_with_audit(self):
        self.client.force_login(self.member)
        response = self.post()
        self.assertEqual(response.status_code, 201)
        material = Material.objects.get(pk=response.json()["id"])
        self.assertEqual(material.owner, self.member)
        self.assertIn(self.category, material.categories.all())
        self.assertTrue(
            _events_for(material)
            .filter(action=ReviewAction.ACTION_CREATED, user=self.member)
            .exists()
        )

    def test_post_reuse_attaches_category_inside_edit_boundary(self):
        material = Material.objects.create(owner=self.member, name="GW Substrate")
        revision = _revision(material)
        self.client.force_login(self.member)
        response = self.post()
        self.assertEqual(response.status_code, 200)
        material.refresh_from_db()
        self.assertIn(self.category, material.categories.all())
        self.assertEqual(_revision(material), revision + 1)
        self.assertTrue(
            _events_for(material)
            .filter(action=ReviewAction.ACTION_EDITED, user=self.member)
            .exists()
        )

    def test_post_reuse_denied_without_change_capability(self):
        material = Material.objects.create(owner=self.member, name="GW Substrate")
        self.member.user_permissions.clear()
        from django.contrib.auth.models import Permission

        self.member.user_permissions.add(
            Permission.objects.get(codename="add_material")
        )
        self.client.force_login(self.member)
        response = self.post()
        self.assertEqual(response.status_code, 403)
        material.refresh_from_db()
        self.assertNotIn(self.category, material.categories.all())


class _DuplicateFixtureMixin:
    @classmethod
    def make_material_tree(cls, owner):
        material = Material.objects.create(
            owner=owner, name="GW Material", publication_status="published"
        )
        cls.material = material


class SampleSeriesCreateDuplicateBoundaryTestCase(ViewWithPermissionsTestCase):
    """Duplicating a series persists the new tree inside the authorized
    create boundary: locked source, ``new_version`` re-decision, reference
    validation, and ``created`` audit on the new root and copied samples."""

    member_permissions = ["add_sampleseries"]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.material = Material.objects.create(
            owner=cls.owner, name="GW Material", publication_status="published"
        )
        cls.series = SampleSeries.objects.create(
            owner=cls.owner,
            name="GW Series",
            material=cls.material,
            publication_status="published",
        )
        cls.sample = Sample.objects.create(
            owner=cls.owner,
            name="GW Sample",
            material=cls.material,
            series=cls.series,
            publication_status="published",
        )

    def url(self, series=None):
        return reverse(
            "sampleseries-duplicate", kwargs={"pk": (series or self.series).pk}
        )

    def post_data(self):
        return {"name": "GW Series Copy", "material": self.material.pk}

    def test_post_denied_for_outsider_creates_nothing(self):
        self.client.force_login(self.outsider)
        response = self.client.post(self.url(), self.post_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(SampleSeries.objects.filter(name="GW Series Copy").exists())

    def test_post_denied_on_unreadable_private_series(self):
        private = SampleSeries.objects.create(
            owner=self.owner,
            name="GW Private Series",
            material=self.material,
            publication_status="private",
        )
        self.client.force_login(self.member)
        response = self.client.post(self.url(private), self.post_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(SampleSeries.objects.filter(name="GW Series Copy").exists())

    def test_post_authorized_duplicates_tree_with_audit(self):
        self.client.force_login(self.member)
        response = self.client.post(self.url(), self.post_data())
        self.assertEqual(response.status_code, 302)
        duplicate = SampleSeries.objects.get(name="GW Series Copy")
        self.assertEqual(duplicate.owner, self.member)
        self.assertEqual(duplicate.publication_status, "private")
        self.assertTrue(
            _events_for(duplicate)
            .filter(action=ReviewAction.ACTION_CREATED, user=self.member)
            .exists()
        )
        copied = duplicate.samples.get()
        self.assertEqual(copied.owner, self.member)
        self.assertTrue(
            _events_for(copied)
            .filter(action=ReviewAction.ACTION_CREATED, user=self.member)
            .exists()
        )


class SampleCreateDuplicateBoundaryTestCase(ViewWithPermissionsTestCase):
    """Duplicating a sample persists the new tree inside the authorized
    create boundary, including ``created`` audit on copied evidence rows."""

    member_permissions = ["add_sample"]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        category, _ = MaterialCategory.objects.get_or_create(
            name=get_sample_substrate_category_name(),
            defaults={"publication_status": "published"},
        )
        cls.material = Material.objects.create(owner=cls.member, name="GW Material")
        cls.material.categories.add(category)
        cls.series = SampleSeries.objects.create(
            owner=cls.member, name="GW Series", material=cls.material
        )
        distribution = TemporalDistribution.objects.create(
            owner=cls.member, name="GW Distribution"
        )
        cls.timestep = Timestep.objects.create(
            owner=cls.member, name="GW Timestep", distribution=distribution
        )
        cls.sample = Sample.objects.create(
            owner=cls.member,
            name="GW Sample",
            material=cls.material,
            series=cls.series,
            timestep=cls.timestep,
        )

    def url(self, sample=None):
        return reverse("sample-duplicate", kwargs={"pk": (sample or self.sample).pk})

    def post_data(self):
        return {
            "name": "GW Sample Copy",
            "material": self.material.pk,
            "series": self.series.pk,
            "timestep": self.timestep.pk,
        }

    def test_post_denied_for_outsider_creates_nothing(self):
        self.client.force_login(self.outsider)
        response = self.client.post(self.url(), self.post_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Sample.objects.filter(name="GW Sample Copy").exists())

    def test_post_authorized_duplicates_sample_with_audit(self):
        prop = MaterialProperty.objects.create(
            owner=self.member, name="GW Property", publication_status="published"
        )
        unit = Unit.objects.create(
            owner=self.member, name="GW Unit", publication_status="published"
        )
        MaterialPropertyValue.objects.create(
            owner=self.member,
            sample=self.sample,
            property=prop,
            unit=unit,
            average=Decimal("1.5"),
            publication_status="published",
        )
        self.client.force_login(self.member)
        response = self.client.post(self.url(), self.post_data())
        if response.status_code != 302:
            self.fail(f"form errors: {response.context['form'].errors}")
        duplicate = Sample.objects.get(name="GW Sample Copy")
        self.assertEqual(duplicate.owner, self.member)
        self.assertTrue(
            _events_for(duplicate)
            .filter(action=ReviewAction.ACTION_CREATED, user=self.member)
            .exists()
        )
        copied_value = duplicate.property_values.get()
        self.assertEqual(copied_value.owner, self.member)
        self.assertTrue(
            _events_for(copied_value)
            .filter(action=ReviewAction.ACTION_CREATED, user=self.member)
            .exists()
        )


class SampleSeriesModalAddDistributionBoundaryTestCase(ViewWithPermissionsTestCase):
    """Attaching a distribution edits the series root inside
    ``content_mutation``; invisible distributions are rejected by
    ``validate_references`` under the lock."""

    member_permissions = ["change_sampleseries"]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name="GW Material")
        cls.series = SampleSeries.objects.create(
            owner=cls.member, name="GW Series", material=material
        )
        cls.distribution = TemporalDistribution.objects.create(
            owner=cls.owner, name="GW Distribution", publication_status="published"
        )
        cls.private_distribution = TemporalDistribution.objects.create(
            owner=cls.owner, name="GW Private Distribution"
        )

    def url(self):
        return reverse(
            "sampleseries-add-distribution-modal", kwargs={"pk": self.series.pk}
        )

    def test_post_denied_for_outsider_attaches_nothing(self):
        self.client.force_login(self.outsider)
        revision = _revision(self.series)
        response = self.client.post(self.url(), {"distribution": self.distribution.pk})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            self.series.temporal_distributions.filter(pk=self.distribution.pk).exists()
        )
        self.assertEqual(_revision(self.series), revision)

    def test_post_denied_for_invisible_distribution(self):
        self.client.force_login(self.member)
        revision = _revision(self.series)
        response = self.client.post(
            self.url(), {"distribution": self.private_distribution.pk}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(_revision(self.series), revision)

    def test_post_authorized_attaches_with_revision_and_audit(self):
        self.client.force_login(self.member)
        revision = _revision(self.series)
        response = self.client.post(self.url(), {"distribution": self.distribution.pk})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            self.series.temporal_distributions.filter(pk=self.distribution.pk).exists()
        )
        self.assertEqual(_revision(self.series), revision + 1)
        self.assertTrue(
            _events_for(self.series)
            .filter(action=ReviewAction.ACTION_EDITED, user=self.member)
            .exists()
        )


class CompositionOrderBoundaryTestCase(ViewWithPermissionsTestCase):
    """Reordering compositions edits sibling rows of the sample's owned
    children; the governed boundary wraps the sample root and records the
    reorder as one audited revision bump."""

    member_permissions = ["change_sample"]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name="GW Material")
        cls.sample = Sample.objects.create(
            owner=cls.member, name="GW Sample", material=material
        )
        group_a = MaterialComponentGroup.objects.create(name="GW Group A")
        group_b = MaterialComponentGroup.objects.create(name="GW Group B")
        cls.first = Composition.objects.create(
            owner=cls.member, sample=cls.sample, group=group_a, order=10
        )
        cls.second = Composition.objects.create(
            owner=cls.member, sample=cls.sample, group=group_b, order=20
        )

    def test_get_denied_for_outsider_reorders_nothing(self):
        self.client.force_login(self.outsider)
        revision = _revision(self.sample)
        orders = (self.first.order, self.second.order)
        response = self.client.get(
            reverse("composition-order-down", kwargs={"pk": self.second.pk})
        )
        self.assertEqual(response.status_code, 403)
        self.first.refresh_from_db()
        self.second.refresh_from_db()
        self.assertEqual((self.first.order, self.second.order), orders)
        self.assertEqual(_revision(self.sample), revision)

    def test_get_authorized_reorders_inside_sample_boundary(self):
        self.client.force_login(self.member)
        revision = _revision(self.sample)
        first_order, second_order = self.first.order, self.second.order
        self.assertLess(first_order, second_order)
        response = self.client.get(
            reverse("composition-order-down", kwargs={"pk": self.second.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.first.refresh_from_db()
        self.second.refresh_from_db()
        self.assertEqual(self.second.order, first_order)
        self.assertEqual(self.first.order, second_order)
        self.assertEqual(_revision(self.sample), revision + 1)
        self.assertTrue(
            _events_for(self.sample)
            .filter(action=ReviewAction.ACTION_EDITED, user=self.member)
            .exists()
        )


class DerivedCompositionOrderBoundaryTestCase(ViewWithPermissionsTestCase):
    """The derived-settings bootstrap creates owned Composition children
    and reorders them inside one governed mutation on the sample root."""

    member_permissions = ["change_sample"]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name="GW Material")
        cls.sample = Sample.objects.create(
            owner=cls.member, name="GW Sample", material=material
        )
        cls.sample.compositions.all().delete()
        cls.group_a = MaterialComponentGroup.objects.create(
            name="GW Group A", publication_status="published"
        )
        cls.group_b = MaterialComponentGroup.objects.create(
            name="GW Group B", publication_status="published"
        )
        component = MaterialComponent.objects.create(
            name="GW Component", publication_status="published"
        )
        unit = Unit.objects.create(name="GW Unit")
        ComponentMeasurement.objects.create(
            owner=cls.member,
            sample=cls.sample,
            group=cls.group_a,
            component=component,
            unit=unit,
            average=Decimal("60"),
        )
        ComponentMeasurement.objects.create(
            owner=cls.member,
            sample=cls.sample,
            group=cls.group_b,
            component=component,
            unit=unit,
            average=Decimal("40"),
        )

    def url(self, name):
        return reverse(
            name, kwargs={"sample_pk": self.sample.pk, "group_pk": self.group_b.pk}
        )

    def test_get_denied_for_outsider_creates_nothing(self):
        self.client.force_login(self.outsider)
        revision = _revision(self.sample)
        response = self.client.get(self.url("derived-composition-order-down"))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.sample.compositions.exists())
        self.assertEqual(_revision(self.sample), revision)

    def test_get_authorized_creates_settings_inside_boundary(self):
        self.client.force_login(self.member)
        revision = _revision(self.sample)
        response = self.client.get(self.url("derived-composition-order-down"))
        self.assertEqual(response.status_code, 302)
        compositions = self.sample.compositions.order_by("order")
        self.assertEqual(compositions.count(), 2)
        for composition in compositions:
            self.assertEqual(composition.owner, self.member)
        self.assertEqual(_revision(self.sample), revision + 1)
        self.assertTrue(
            _events_for(self.sample)
            .filter(action=ReviewAction.ACTION_EDITED, user=self.member)
            .exists()
        )


class MaterialPropertyValueAllowedUnitsBoundaryTestCase(ViewWithPermissionsTestCase):
    """Saving a property value must not mutate the referenced property's
    ``allowed_units``: that M2M is governed content of the MaterialProperty
    root and is only established by editing the property itself."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.unit = Unit.objects.create(name="GW Unit")
        cls.property = MaterialProperty.objects.create(
            owner=cls.owner, name="GW Property", publication_status="published"
        )

    def test_form_save_does_not_extend_property_allowed_units(self):
        data = QueryDict("", mutable=True)
        data.update(
            {
                "property": self.property.pk,
                "unit": self.unit.pk,
                "average": "12.3",
            }
        )
        form = MaterialPropertyValueModelForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertFalse(self.property.allowed_units.filter(pk=self.unit.pk).exists())
