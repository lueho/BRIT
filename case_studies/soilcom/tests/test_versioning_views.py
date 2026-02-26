from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from case_studies.soilcom.models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionCatchment,
    CollectionPropertyValue,
    CollectionSystem,
    WasteCategory,
    WasteStream,
)
from utils.tests.testcases import ViewWithPermissionsTestCase


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

        cls.prop = Property.objects.create(
            name="AnchorProp", publication_status="published"
        )
        cls.unit = Unit.objects.create(
            name="AnchorUnit", publication_status="published"
        )
        cls.prop.allowed_units.add(cls.unit)

    def test_member_post_attaches_to_anchor(self):
        self.client.force_login(self.member)
        data = {
            "collection": self.succ.pk,  # client submits current version
            "property": self.prop.pk,
            "unit": self.unit.pk,
            "year": 2022,
            "average": 12.3,
            # Add formset management data for WasteFlyerFormSet
            "form-TOTAL_FORMS": "0",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
        }
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.succ.pk}), data=data
        )
        self.assertEqual(response.status_code, 302)

        from case_studies.soilcom.models import CollectionPropertyValue

        cpv = CollectionPropertyValue.objects.get(
            property=self.prop, unit=self.unit, year=2022
        )
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

        from case_studies.soilcom.models import CollectionPropertyValue
        from utils.properties.models import Property, Unit

        cls.prop = Property.objects.create(
            name="ReanchorProp", publication_status="published"
        )
        cls.unit = Unit.objects.create(
            name="ReanchorUnit", publication_status="published"
        )
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
                # Add formset management data for WasteFlyerFormSet
                "form-TOTAL_FORMS": "0",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
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

        from case_studies.soilcom.models import CollectionPropertyValue
        from utils.properties.models import Property, Unit

        cls.prop = Property.objects.create(
            name="DelProp", publication_status="published"
        )
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
            reverse(
                "collectionpropertyvalue-delete-modal",
                kwargs={"pk": self.child_value.pk},
            )
        )
        self.assertEqual(response.status_code, 302)
        from case_studies.soilcom.models import CollectionPropertyValue

        self.assertFalse(
            CollectionPropertyValue.objects.filter(
                pk__in=[self.child_value.pk, self.anchor_value.pk]
            ).exists()
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

        from case_studies.soilcom.models import CollectionPropertyValue
        from utils.properties.models import Property, Unit

        cls.prop = Property.objects.create(
            name="ViewProp", publication_status="published"
        )
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


class CollectionReviewDetailPropertiesTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model
        from django.contrib.contenttypes.models import ContentType

        from case_studies.soilcom.models import (
            AggregatedCollectionPropertyValue,
            Collection,
            CollectionCatchment,
            CollectionPropertyValue,
            CollectionSystem,
            WasteCategory,
            WasteStream,
        )
        from utils.properties.models import Property, Unit

        cls.User = get_user_model()
        cls.staff = cls.User.objects.create(username="moderator", is_staff=True)

        cls.catchment = CollectionCatchment.objects.create(name="RC")
        cls.system = CollectionSystem.objects.create(name="RS")
        cls.category = WasteCategory.objects.create(name="RCat")
        cls.stream = WasteStream.objects.create(category=cls.category)
        cls.collection = Collection.objects.create(
            name="R",
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_stream=cls.stream,
            publication_status="published",
        )

        cls.prop = Property.objects.create(
            name="ReviewProp", publication_status="published"
        )
        cls.unit = Unit.objects.create(
            name="ReviewUnit", publication_status="published"
        )
        cls.prop.allowed_units.add(cls.unit)

        cls.cpv = CollectionPropertyValue.objects.create(
            collection=cls.collection,
            property=cls.prop,
            unit=cls.unit,
            year=2020,
            average=77,
            publication_status="published",
        )

        cls.agg = AggregatedCollectionPropertyValue.objects.create(
            property=cls.prop,
            unit=cls.unit,
            year=2021,
            average=88,
            publication_status="published",
        )
        cls.agg.collections.add(cls.collection)

        # Precompute URL bits used in tests
        cls.ct_id = ContentType.objects.get_for_model(Collection).pk

    def test_review_detail_shows_cpv_and_aggregated(self):
        from django.urls import reverse

        self.client.force_login(self.staff)
        url = reverse(
            "object_management:review_item_detail",
            kwargs={"content_type_id": self.ct_id, "object_id": self.collection.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        body = response.content.decode()
        # CPV value rendered (average and unit)
        self.assertIn("77", body)
        self.assertIn("ReviewUnit", body)
        # Aggregated section marked with '(aggregated)'
        self.assertIn("aggregated", body)


class CollectionDetailOnlyPublishedCpvsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from utils.properties.models import Property, Unit

        cls.catchment = CollectionCatchment.objects.create(name="PC")
        cls.system = CollectionSystem.objects.create(name="PS")
        cls.category = WasteCategory.objects.create(name="PCat")
        cls.stream = WasteStream.objects.create(category=cls.category)
        cls.collection = Collection.objects.create(
            name="PublishedCollection",
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_stream=cls.stream,
            publication_status="published",
        )

        cls.prop = Property.objects.create(
            name="VisibilityProp", publication_status="published"
        )
        cls.published_unit = Unit.objects.create(
            name="PublishedUnit", publication_status="published"
        )
        cls.private_unit = Unit.objects.create(
            name="PrivateUnit", publication_status="published"
        )
        cls.prop.allowed_units.add(cls.published_unit, cls.private_unit)

        cls.published_value = CollectionPropertyValue.objects.create(
            collection=cls.collection,
            property=cls.prop,
            unit=cls.published_unit,
            year=2020,
            average=12,
            publication_status="published",
        )

        cls.private_value = CollectionPropertyValue.objects.create(
            collection=cls.collection,
            property=cls.prop,
            unit=cls.private_unit,
            year=2021,
            average=24,
            publication_status="private",
        )

    def test_public_detail_only_shows_published_cpvs(self):
        response = self.client.get(
            reverse("collection-detail", kwargs={"pk": self.collection.pk})
        )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("PublishedUnit", body)
        self.assertNotIn("PrivateUnit", body)

    def test_staff_detail_only_shows_published_cpvs(self):
        staff = get_user_model().objects.create(username="staff-user", is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(
            reverse("collection-detail", kwargs={"pk": self.collection.pk})
        )
        self.assertEqual(response.status_code, 200)
        context_vals = response.context["collection_property_values"]
        self.assertTrue(all(v.publication_status == "published" for v in context_vals))
        self.assertNotIn(
            "PrivateUnit",
            response.content.decode(),
        )


class CollectionReviewDetailPreviewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.contenttypes.models import ContentType

        from utils.properties.models import Property, Unit

        cls.User = get_user_model()
        cls.staff = cls.User.objects.create(username="reviewer", is_staff=True)

        cls.catchment = CollectionCatchment.objects.create(name="RC")
        cls.system = CollectionSystem.objects.create(name="RS")
        cls.category = WasteCategory.objects.create(name="RCat")
        cls.stream = WasteStream.objects.create(category=cls.category)
        cls.collection = Collection.objects.create(
            name="ReviewCollection",
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_stream=cls.stream,
            publication_status="review",
        )

        cls.prop = Property.objects.create(
            name="PreviewProp", publication_status="published"
        )
        cls.unit = Unit.objects.create(
            name="PreviewUnit", publication_status="published"
        )
        cls.other_unit = Unit.objects.create(
            name="OtherUnit", publication_status="published"
        )
        cls.prop.allowed_units.add(cls.unit, cls.other_unit)

        cls.cpv_published = CollectionPropertyValue.objects.create(
            collection=cls.collection,
            property=cls.prop,
            unit=cls.unit,
            year=2020,
            average=10,
            publication_status="published",
        )

        cls.cpv_review = CollectionPropertyValue.objects.create(
            collection=cls.collection,
            property=cls.prop,
            unit=cls.unit,
            year=2020,
            average=12,
            publication_status="review",
        )

        cls.cpv_private = CollectionPropertyValue.objects.create(
            collection=cls.collection,
            property=cls.prop,
            unit=cls.other_unit,
            year=2021,
            average=5,
            publication_status="private",
        )

        # Aggregated values
        cls.agg_prop = Property.objects.create(
            name="PreviewAggProp", publication_status="published"
        )
        cls.agg_unit = Unit.objects.create(
            name="AggUnit", publication_status="published"
        )
        cls.agg_prop.allowed_units.add(cls.agg_unit)

        cls.agg_published = AggregatedCollectionPropertyValue.objects.create(
            property=cls.agg_prop,
            unit=cls.agg_unit,
            year=2019,
            average=40,
            publication_status="published",
        )
        cls.agg_published.collections.add(cls.collection)

        cls.agg_review = AggregatedCollectionPropertyValue.objects.create(
            property=cls.agg_prop,
            unit=cls.agg_unit,
            year=2019,
            average=45,
            publication_status="review",
        )
        cls.agg_review.collections.add(cls.collection)

        cls.agg_private = AggregatedCollectionPropertyValue.objects.create(
            property=cls.agg_prop,
            unit=cls.agg_unit,
            year=2021,
            average=55,
            publication_status="private",
        )
        cls.agg_private.collections.add(cls.collection)

        cls.ct_id = ContentType.objects.get_for_model(Collection).pk

        # Create materials for testing allowed/forbidden display
        from materials.models import Material

        cls.allowed_material = Material.objects.create(name="Allowed Material")
        cls.forbidden_material = Material.objects.create(name="Forbidden Material")
        cls.stream.allowed_materials.add(cls.allowed_material)
        cls.stream.forbidden_materials.add(cls.forbidden_material)

    def test_review_preview_shows_published_and_review_only(self):
        self.client.force_login(self.staff)
        url = reverse(
            "object_management:review_item_detail",
            kwargs={"content_type_id": self.ct_id, "object_id": self.collection.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        cpvs = response.context["collection_property_values"]
        self.assertEqual([v.pk for v in cpvs], [self.cpv_review.pk])
        self.assertTrue(
            all(v.publication_status in {"published", "review"} for v in cpvs)
        )

        agg_vals = response.context["aggregated_collection_property_values"]
        self.assertEqual([v.pk for v in agg_vals], [self.agg_review.pk])
        self.assertTrue(
            all(v.publication_status in {"published", "review"} for v in agg_vals)
        )

        body = response.content.decode()
        self.assertIn("12", body)
        self.assertIn("45", body)
        self.assertNotIn("Private", body)

    def test_review_detail_shows_allowed_and_forbidden_materials(self):
        """Test that allowed and forbidden materials are displayed in review view."""
        self.client.force_login(self.staff)
        url = reverse(
            "object_management:review_item_detail",
            kwargs={"content_type_id": self.ct_id, "object_id": self.collection.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Check that materials are in context
        allowed_materials = response.context["allowed_materials"]
        forbidden_materials = response.context["forbidden_materials"]

        self.assertEqual(len(allowed_materials), 1)
        self.assertEqual(len(forbidden_materials), 1)
        self.assertEqual(allowed_materials[0].name, "Allowed Material")
        self.assertEqual(forbidden_materials[0].name, "Forbidden Material")

        # Check that materials are displayed in the rendered HTML
        body = response.content.decode()
        self.assertIn("Allowed Materials", body)
        self.assertIn("Forbidden Materials", body)
        self.assertIn("Allowed Material", body)
        self.assertIn("Forbidden Material", body)
