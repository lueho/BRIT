from datetime import date

from django.test import TestCase
from django.urls import reverse

from utils.tests.testcases import ViewWithPermissionsTestCase

from case_studies.soilcom.models import (
    Collection,
    CollectionCatchment,
    CollectionSystem,
    WasteCategory,
    WasteStream,
)


class CollectionAddPropertyValueAnchoringTestCase(ViewWithPermissionsTestCase):
    member_permissions = ["add_collectionpropertyvalue"]
    url_name = "collection-add-property"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.catchment = CollectionCatchment.objects.create(name="C")
        cls.system = CollectionSystem.objects.create(name="S")
        cls.category = WasteCategory.objects.create(name="Cat")
        cls.stream = WasteStream.objects.create(category=cls.category)
        cls.root = Collection.objects.create(
            name="Root",
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_stream=cls.stream,
            valid_from=date(2020, 1, 1),
            publication_status="published",
            owner=cls.member,
        )
        cls.succ = Collection.objects.create(
            name="Succ",
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_stream=cls.stream,
            valid_from=date(2021, 1, 1),
            publication_status="published",
            owner=cls.member,
        )
        cls.succ.predecessors.add(cls.root)

        from utils.properties.models import Property, Unit

        cls.prop = Property.objects.create(name="AnchorProp", publication_status="published")
        cls.unit = Unit.objects.create(name="AnchorUnit", publication_status="published")
        cls.prop.allowed_units.add(cls.unit)

    def test_member_post_attaches_to_anchor(self):
        self.client.force_login(self.member)
        data = {
            "collection": self.succ.pk,  # client submits current version
            "property": self.prop.pk,
            "unit": self.unit.pk,
            "year": 2022,
            "average": 12.3,
        }
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.succ.pk}), data=data
        )
        self.assertEqual(response.status_code, 302)

        from case_studies.soilcom.models import CollectionPropertyValue

        cpv = CollectionPropertyValue.objects.get(property=self.prop, unit=self.unit, year=2022)
        # Saved on anchor, not on the submitted collection
        self.assertEqual(cpv.collection_id, (self.succ.version_anchor or self.succ).pk)


class CollectionPropertyValueUpdateReanchorTestCase(ViewWithPermissionsTestCase):
    member_permissions = ["change_collectionpropertyvalue"]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.catchment = CollectionCatchment.objects.create(name="C")
        cls.system = CollectionSystem.objects.create(name="S")
        cls.category = WasteCategory.objects.create(name="Cat")
        cls.stream = WasteStream.objects.create(category=cls.category)
        cls.root = Collection.objects.create(
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_stream=cls.stream,
            valid_from=date(2020, 1, 1),
            publication_status="published",
            owner=cls.member,
        )
        cls.succ = Collection.objects.create(
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_stream=cls.stream,
            valid_from=date(2021, 1, 1),
            publication_status="published",
            owner=cls.member,
        )
        cls.succ.predecessors.add(cls.root)

        from utils.properties.models import Property, Unit
        from case_studies.soilcom.models import CollectionPropertyValue

        cls.prop = Property.objects.create(name="ReanchorProp", publication_status="published")
        cls.unit = Unit.objects.create(name="ReanchorUnit", publication_status="published")
        cls.prop.allowed_units.add(cls.unit)

        cls.cpv = CollectionPropertyValue.objects.create(
            owner=cls.member,
            collection=cls.succ,
            property=cls.prop,
            unit=cls.unit,
            year=2020,
            average=5,
            publication_status="private",
        )

    def test_update_reanchors_to_version_anchor(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("collectionpropertyvalue-update", kwargs={"pk": self.cpv.pk}),
            data={
                "collection": self.succ.pk,
                "property": self.prop.pk,
                "unit": self.unit.pk,
                "year": 2020,
                "average": 6,
            },
        )
        self.assertEqual(response.status_code, 302)
        from case_studies.soilcom.models import CollectionPropertyValue

        cpv = CollectionPropertyValue.objects.get(pk=self.cpv.pk)
        self.assertEqual(cpv.collection_id, self.root.version_anchor.pk)
        self.assertEqual(cpv.average, 6)


class CollectionPropertyValueDeleteAnchorSemanticsTestCase(ViewWithPermissionsTestCase):
    member_permissions = ["delete_collectionpropertyvalue"]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.catchment = CollectionCatchment.objects.create(name="C")
        cls.system = CollectionSystem.objects.create(name="S")
        cls.category = WasteCategory.objects.create(name="Cat")
        cls.stream = WasteStream.objects.create(category=cls.category)
        cls.root = Collection.objects.create(
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_stream=cls.stream,
            valid_from=date(2020, 1, 1),
            publication_status="published",
            owner=cls.member,
        )
        cls.succ = Collection.objects.create(
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_stream=cls.stream,
            valid_from=date(2021, 1, 1),
            publication_status="published",
            owner=cls.member,
        )
        cls.succ.predecessors.add(cls.root)

        from utils.properties.models import Property, Unit
        from case_studies.soilcom.models import CollectionPropertyValue

        cls.prop = Property.objects.create(name="DelProp", publication_status="published")
        cls.unit = Unit.objects.create(name="DelUnit", publication_status="published")
        cls.prop.allowed_units.add(cls.unit)

        cls.anchor_value = CollectionPropertyValue.objects.create(
            owner=cls.member,
            collection=cls.root,
            property=cls.prop,
            unit=cls.unit,
            year=2020,
            average=10,
            publication_status="private",
        )
        cls.child_value = CollectionPropertyValue.objects.create(
            owner=cls.member,
            collection=cls.succ,
            property=cls.prop,
            unit=cls.unit,
            year=2020,
            average=11,
            publication_status="private",
        )

    def test_delete_child_also_deletes_anchor_duplicate(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("collectionpropertyvalue-delete-modal", kwargs={"pk": self.child_value.pk})
        )
        self.assertEqual(response.status_code, 302)
        from case_studies.soilcom.models import CollectionPropertyValue

        self.assertFalse(
            CollectionPropertyValue.objects.filter(pk__in=[self.child_value.pk, self.anchor_value.pk]).exists()
        )


class CollectionDetailChainAwareValuesTestCase(ViewWithPermissionsTestCase):
    url_name = "collection-detail"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.catchment = CollectionCatchment.objects.create(name="C")
        cls.system = CollectionSystem.objects.create(name="S")
        cls.category = WasteCategory.objects.create(name="Cat")
        cls.stream = WasteStream.objects.create(category=cls.category)
        cls.root = Collection.objects.create(
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_stream=cls.stream,
            valid_from=date(2020, 1, 1),
            publication_status="published",
        )
        cls.succ = Collection.objects.create(
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_stream=cls.stream,
            valid_from=date(2021, 1, 1),
            publication_status="published",
        )
        cls.succ.predecessors.add(cls.root)

        from utils.properties.models import Property, Unit
        from case_studies.soilcom.models import CollectionPropertyValue

        cls.prop = Property.objects.create(name="ViewProp", publication_status="published")
        cls.unit = Unit.objects.create(name="ViewUnit", publication_status="published")
        cls.prop.allowed_units.add(cls.unit)
        cls.anchor_value = CollectionPropertyValue.objects.create(
            collection=cls.root,
            property=cls.prop,
            unit=cls.unit,
            year=2020,
            average=77,
            publication_status="published",
        )

    def test_detail_context_includes_chain_values(self):
        response = self.client.get(reverse(self.url_name, kwargs={"pk": self.succ.pk}))
        self.assertEqual(response.status_code, 200)
        # Ensure context has chain-aware lists and contains the anchor value
        self.assertIn("collection_property_values", response.context)
        vals = response.context["collection_property_values"]
        self.assertTrue(any(v.pk == self.anchor_value.pk for v in vals))
