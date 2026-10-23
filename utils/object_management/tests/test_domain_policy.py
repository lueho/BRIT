"""Domain authorization contract tests: settled read-query replacements.

Covers the lead-authored scope delegation for collection dataset versions,
viewset visible querysets, and inventory/map download guards. Unknown scopes
must return empty querysets and ``is_staff``/moderator predicates must never
grant read access to unrelated private or archived records.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.http import QueryDict
from django.test import RequestFactory, TestCase
from django.urls import reverse

from bibliography.models import Source
from distributions.models import TemporalDistribution, Timestep
from inventories.models import Scenario
from maps.models import GeoDataset, Region
from maps.views import GeoDataSetRuntimeMapView
from materials.models import (
    Composition,
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    Sample,
    SampleSeries,
)
from sources.greenhouses.models import (
    Culture,
    Greenhouse,
    GreenhouseGrowthCycle,
    GrowthTimeStepSet,
)
from sources.waste_collection.models import (
    Catchment,
    Collection,
    CollectionFrequency,
    CollectionPropertyValue,
    CollectionSystem,
    Collector,
    WasteCategory,
    WasteFlyer,
)
from sources.waste_collection.views import SoilcomDatasetVersionMixin
from utils.object_management.models import ObjectEditorGrant, ReviewAction
from utils.object_management.permissions import apply_scope_filter
from utils.object_management.services import content_mutation
from utils.properties.models import Property, Unit


def _perm(model, codename):
    """Fetch or provision a model permission row for the test registry.

    ``waste_collection`` models only ship ``can_moderate_*`` rows; the named
    add/change/delete capabilities are created ad hoc, matching the existing
    test convention.
    """
    permission, _ = Permission.objects.get_or_create(
        codename=codename,
        content_type=ContentType.objects.get_for_model(model, for_concrete_model=False),
        defaults={"name": f"Can {codename.replace('_', ' ')}"},
    )
    return permission


def _grant(obj, editor):
    return ObjectEditorGrant.objects.create(
        content_type=ContentType.objects.get_for_model(obj.__class__),
        object_id=obj.pk,
        editor=editor,
        granted_by=obj.owner,
    )


class ScopedReadContractBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="domain-owner")
        cls.staff = User.objects.create_user(username="domain-staff", is_staff=True)
        cls.stranger = User.objects.create_user(username="domain-stranger")
        cls.editor = User.objects.create_user(username="domain-editor")
        cls.moderator = User.objects.create_user(username="domain-moderator")

        cls.catchment = Catchment.objects.create(
            name="Domain Catchment", publication_status="published"
        )
        cls.collector = Collector.objects.create(
            name="Domain Collector", publication_status="published"
        )
        cls.collection_system = CollectionSystem.objects.create(
            name="Domain Collection System", publication_status="published"
        )
        cls.waste_category = WasteCategory.objects.create(
            name="Domain Category", publication_status="published"
        )

    def _collection(self, name, owner, publication_status):
        return Collection.objects.create(
            name=name,
            owner=owner,
            catchment=self.catchment,
            waste_category=self.waste_category,
            collection_system=self.collection_system,
            collector=self.collector,
            publication_status=publication_status,
        )


class DatasetVersionScopeTests(ScopedReadContractBase):
    """``SoilcomDatasetVersionMixin._dv_queryset`` must delegate to the shared
    scope predicate; staff-only shortcuts and unknown-scope fallthrough are
    forbidden."""

    def setUp(self):
        self.owner_private = self._collection("Owner Private", self.owner, "private")
        self.other_private = self._collection(
            "Stranger Private", self.stranger, "private"
        )
        self.published = self._collection("Published", self.stranger, "published")

    def _dv_queryset(self, user, scope):
        mixin = SoilcomDatasetVersionMixin()
        mixin.request = RequestFactory().get("/map/", {"scope": scope})
        mixin.request.user = user
        return mixin._dv_queryset()

    def test_private_scope_for_staff_excludes_other_users_rows(self):
        qs = self._dv_queryset(self.staff, "private")
        self.assertNotIn(self.other_private, qs)
        self.assertNotIn(self.owner_private, qs)

    def test_private_scope_for_owner_includes_own_and_shared(self):
        _grant(self.other_private, self.owner)
        qs = self._dv_queryset(self.owner, "private")
        self.assertIn(self.owner_private, qs)
        self.assertIn(self.other_private, qs)
        self.assertNotIn(self.published, qs)

    def test_unknown_scope_returns_empty(self):
        qs = self._dv_queryset(self.owner, "bogus")
        self.assertEqual(list(qs), [])

    def test_published_scope_returns_only_published(self):
        qs = self._dv_queryset(self.stranger, "published")
        self.assertIn(self.published, qs)
        self.assertNotIn(self.owner_private, qs)


class CollectionApiScopeTests(ScopedReadContractBase):
    """The viewset visible querysets must apply the shared scope predicate:
    unknown scopes return empty results instead of a visibility fallback."""

    def setUp(self):
        self.owner_private = self._collection("Owner Private", self.owner, "private")
        self.other_private = self._collection(
            "Stranger Private", self.stranger, "private"
        )
        self.published = self._collection("Published", self.stranger, "published")
        self.frequency = CollectionFrequency.objects.create(
            name="Domain Frequency",
            owner=self.stranger,
            publication_status="private",
        )
        self.prop = Property.objects.create(name="Domain Property", owner=self.owner)
        self.cpv = CollectionPropertyValue.objects.create(
            name="Domain CPV",
            owner=self.stranger,
            collection=self.other_private,
            property=self.prop,
            average=1.0,
            publication_status="private",
        )

    def test_summaries_unknown_scope_returns_empty(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("api-waste-collection-summaries"),
            {
                "scope": "bogus",
                "id": [self.owner_private.pk, self.published.pk],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summaries"], [])

    def test_summaries_private_scope_for_staff_excludes_other_users(self):
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("api-waste-collection-summaries"),
            {
                "scope": "private",
                "id": [self.other_private.pk, self.owner_private.pk],
            },
        )
        self.assertEqual(response.status_code, 200)
        returned_ids = {row["id"] for row in response.data["summaries"]}
        self.assertNotIn(self.other_private.pk, returned_ids)
        self.assertNotIn(self.owner_private.pk, returned_ids)

    def test_summaries_private_scope_includes_editor_grants(self):
        _grant(self.other_private, self.editor)
        self.client.force_login(self.editor)
        response = self.client.get(
            reverse("api-waste-collection-summaries"),
            {"scope": "private", "id": [self.other_private.pk]},
        )
        self.assertEqual(response.status_code, 200)
        returned_ids = {row["id"] for row in response.data["summaries"]}
        self.assertIn(self.other_private.pk, returned_ids)

    def test_summaries_default_scope_includes_own_and_shared_private(self):
        """No ``scope`` parameter means general read visibility: owned and
        editor-granted private collections are returned alongside public
        data; unrelated private collections stay hidden."""
        _grant(self.other_private, self.editor)
        self.client.force_login(self.editor)
        response = self.client.get(
            reverse("api-waste-collection-summaries"),
            {
                "id": [
                    self.owner_private.pk,
                    self.other_private.pk,
                    self.published.pk,
                ]
            },
        )
        self.assertEqual(response.status_code, 200)
        returned_ids = {row["id"] for row in response.data["summaries"]}
        self.assertEqual(returned_ids, {self.other_private.pk, self.published.pk})

    def test_summaries_default_scope_includes_owner_private(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("api-waste-collection-summaries"),
            {"id": [self.owner_private.pk, self.other_private.pk]},
        )
        self.assertEqual(response.status_code, 200)
        returned_ids = {row["id"] for row in response.data["summaries"]}
        self.assertEqual(returned_ids, {self.owner_private.pk})

    def test_summaries_published_scope_excludes_own_private(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("api-waste-collection-summaries"),
            {
                "scope": "published",
                "id": [self.owner_private.pk, self.published.pk],
            },
        )
        self.assertEqual(response.status_code, 200)
        returned_ids = {row["id"] for row in response.data["summaries"]}
        self.assertEqual(returned_ids, {self.published.pk})

    def test_frequencies_unknown_scope_returns_empty(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("api-waste-collection-frequencies"), {"scope": "bogus"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

    def test_property_values_unknown_scope_returns_empty(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("api-waste-collection-property-value-list"),
            {"scope": "bogus", "collection": self.other_private.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

    def test_apply_scope_filter_unknown_scope_returns_empty(self):
        qs = apply_scope_filter(Collection.objects.all(), "bogus", user=self.owner)
        self.assertEqual(list(qs), [])


class InventoryReadGuardTests(TestCase):
    """Download guards must use ``decide(actor, 'read', scenario)`` — grants
    work, and staff/moderator flags do not open unrelated private records."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="inv-owner")
        cls.staff = User.objects.create_user(username="inv-staff", is_staff=True)
        cls.stranger = User.objects.create_user(username="inv-stranger")
        cls.editor = User.objects.create_user(username="inv-editor")
        cls.moderator = User.objects.create_user(username="inv-moderator")
        cls.moderator.user_permissions.add(_perm(Scenario, "can_moderate_scenario"))
        cls.region = Region.objects.create(
            name="Inv Region", publication_status="published"
        )
        cls.scenario = Scenario.objects.create(
            name="Private Scenario",
            region=cls.region,
            owner=cls.owner,
            publication_status="private",
        )
        _grant(cls.scenario, cls.editor)

    def _get_summary(self, user):
        if user is not None:
            self.client.force_login(user)
        url = reverse(
            "scenario-download-summary", kwargs={"scenario_pk": self.scenario.pk}
        )
        with patch.object(Scenario, "summary_dict", return_value={"Name": "x"}):
            return self.client.get(url)

    def test_owner_can_download(self):
        response = self._get_summary(self.owner)
        self.assertEqual(response.status_code, 200)

    def test_editor_grant_holder_can_download(self):
        response = self._get_summary(self.editor)
        self.assertEqual(response.status_code, 200)

    def test_staff_cannot_download_unrelated_private_scenario(self):
        response = self._get_summary(self.staff)
        self.assertEqual(response.status_code, 403)

    def test_moderator_cannot_download_unrelated_private_scenario(self):
        response = self._get_summary(self.moderator)
        self.assertEqual(response.status_code, 403)

    def test_stranger_cannot_download_private_scenario(self):
        response = self._get_summary(self.stranger)
        self.assertEqual(response.status_code, 403)

    def test_result_summary_guard_matches(self):
        self.client.force_login(self.staff)
        url = reverse(
            "scenario-download-result-summary",
            kwargs={"scenario_pk": self.scenario.pk},
        )
        with patch("inventories.views.ScenarioResult") as result:
            result.return_value.summary_dict.return_value = {}
            response = self.client.get(url)
        self.assertEqual(response.status_code, 403)


class MapsReadGuardTests(TestCase):
    """``GeoDataSetRuntimePermissionMixin.test_func`` (and the map view copy)
    must delegate to ``decide(actor, 'read', dataset)``."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="map-owner")
        cls.staff = User.objects.create_user(username="map-staff", is_staff=True)
        cls.editor = User.objects.create_user(username="map-editor")
        cls.moderator = User.objects.create_user(username="map-moderator")
        cls.moderator.user_permissions.add(_perm(GeoDataset, "can_moderate_geodataset"))
        cls.region = Region.objects.create(
            name="Map Region", publication_status="published"
        )
        cls.private_dataset = GeoDataset.objects.create(
            name="Private Dataset",
            region=cls.region,
            owner=cls.owner,
            publication_status="private",
        )
        _grant(cls.private_dataset, cls.editor)

    def _test_func(self, user, dataset):
        view = GeoDataSetRuntimeMapView()
        request = RequestFactory().get("/map/")
        request.user = user
        view.request = request
        view.kwargs = {"pk": dataset.pk}
        return view.test_func()

    def test_owner_reads_private_dataset(self):
        self.assertTrue(self._test_func(self.owner, self.private_dataset))

    def test_editor_grant_reads_private_dataset(self):
        self.assertTrue(self._test_func(self.editor, self.private_dataset))

    def test_staff_cannot_read_unrelated_private_dataset(self):
        self.assertFalse(self._test_func(self.staff, self.private_dataset))

    def test_moderator_cannot_read_unrelated_private_dataset(self):
        self.assertFalse(self._test_func(self.moderator, self.private_dataset))


class CollectionUpdateWriterTests(ScopedReadContractBase):
    """``update_collection``/legacy must map to ``edit`` on the resolved root
    through ``content_mutation`` — owner-or-editor with change capability,
    immutable states denied, identity mismatch an atomic no-op."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.change_collection = _perm(Collection, "change_collection")
        cls.add_wasteflyer, _ = Permission.objects.get_or_create(
            codename="add_wasteflyer",
            content_type=ContentType.objects.get_for_model(
                WasteFlyer, for_concrete_model=False
            ),
            defaults={"name": "Can add waste flyer"},
        )

    def setUp(self):
        self.collection = self._collection("Mutable", self.owner, "private")
        self.collection.valid_from = date(2024, 1, 1)
        self.collection.save(update_fields=["valid_from"])
        self.owner.user_permissions.add(self.change_collection)
        self.url = reverse(
            "api-waste-collection-update", kwargs={"pk": self.collection.pk}
        )

    def _payload(self, **overrides):
        payload = {
            "expected_catchment": str(self.collection.catchment),
            "expected_waste_category": str(self.collection.effective_waste_category),
            "expected_collection_system": str(self.collection.collection_system),
            "expected_publication_status": self.collection.publication_status,
            "expected_valid_from": self.collection.valid_from.isoformat(),
        }
        payload.update(overrides)
        return payload

    def test_owner_with_change_updates_and_bumps_revision(self):
        self.client.force_login(self.owner)
        before = self.collection.content_revision
        response = self.client.post(
            self.url, self._payload(description="owner edit"), format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.description, "owner edit")
        self.assertEqual(self.collection.content_revision, before + 1)
        event = ReviewAction.for_object(self.collection).get(action="edited")
        self.assertEqual(event.content_revision, self.collection.content_revision)

    def test_editor_with_change_and_grant_updates(self):
        self.editor.user_permissions.add(self.change_collection)
        _grant(self.collection, self.editor)
        self.client.force_login(self.editor)
        response = self.client.post(
            self.url, self._payload(description="editor edit"), format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.description, "editor edit")

    def test_owner_without_change_permission_denied(self):
        self.owner.user_permissions.remove(self.change_collection)
        self.client.force_login(self.owner)
        response = self.client.post(
            self.url, self._payload(description="no change"), format="json"
        )
        self.assertEqual(response.status_code, 403)
        self.collection.refresh_from_db()
        self.assertNotEqual(self.collection.description, "no change")

    def test_stranger_denied(self):
        self.stranger.user_permissions.add(self.change_collection)
        self.client.force_login(self.stranger)
        response = self.client.post(
            self.url, self._payload(description="stranger"), format="json"
        )
        self.assertIn(response.status_code, {403, 404})

    def test_staff_without_capability_denied(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            self.url, self._payload(description="staff"), format="json"
        )
        self.assertIn(response.status_code, {403, 404})

    def test_published_collection_frozen_for_owner(self):
        self.collection.publication_status = "published"
        self.collection.save(update_fields=["publication_status"])
        self.client.force_login(self.owner)
        response = self.client.post(
            self.url,
            self._payload(
                expected_publication_status="private", description="frozen edit"
            ),
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.collection.refresh_from_db()
        self.assertNotEqual(self.collection.description, "frozen edit")

    def test_published_collection_frozen_for_administrator(self):
        self.collection.publication_status = "published"
        self.collection.save(update_fields=["publication_status"])
        administrator = User.objects.create_user(username="domain-admin")
        administrator.user_permissions.add(
            Permission.objects.get(codename="administer_objects")
        )
        self.client.force_login(administrator)
        response = self.client.post(
            self.url,
            self._payload(
                expected_publication_status="private", description="admin edit"
            ),
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_identity_mismatch_is_atomic_noop(self):
        self.client.force_login(self.owner)
        before = self.collection.content_revision
        response = self.client.post(
            self.url,
            self._payload(expected_catchment="Wrong Catchment", description="mismatch"),
            format="json",
        )
        self.assertEqual(response.status_code, 409)
        self.collection.refresh_from_db()
        self.assertNotEqual(self.collection.description, "mismatch")
        self.assertEqual(self.collection.content_revision, before)
        self.assertFalse(
            ReviewAction.for_object(self.collection).filter(action="edited").exists()
        )

    def test_legacy_endpoint_uses_same_boundary(self):
        self.client.force_login(self.owner)
        url = reverse(
            "api-waste-collection-update-collection",
            kwargs={"pk": self.collection.pk},
        )
        response = self.client.post(
            url, self._payload(description="legacy edit"), format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.description, "legacy edit")

    def test_update_context_reports_edit_capability(self):
        from sources.waste_collection.review_hooks import (
            serialize_collection_update_context,
        )

        context = serialize_collection_update_context(self.owner, self.collection)
        self.assertTrue(context["available"])

        self.editor.user_permissions.add(self.change_collection)
        _grant(self.collection, self.editor)
        context = serialize_collection_update_context(self.editor, self.collection)
        self.assertTrue(context["available"])

        context = serialize_collection_update_context(self.staff, self.collection)
        self.assertFalse(context["available"])

        self.collection.publication_status = "published"
        self.collection.save(update_fields=["publication_status"])
        context = serialize_collection_update_context(self.owner, self.collection)
        self.assertFalse(context["available"])
        self.assertTrue(context.get("detail"))


class CollectionCreateWriterTests(ScopedReadContractBase):
    """Custom create endpoints must use the named ``create`` decisions with
    model targets and record creation audits."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.add_collection = _perm(Collection, "add_collection")
        cls.add_cpv = _perm(CollectionPropertyValue, "add_collectionpropertyvalue")

    def setUp(self):
        self.collection = self._collection("Base", self.owner, "private")
        self.published_collection = self._collection(
            "Published Base", self.stranger, "published"
        )

    def _create_payload(self, **overrides):
        payload = {
            "catchment": self.catchment.pk,
            "waste_category": self.waste_category.pk,
            "collection_system": self.collection_system.pk,
            "valid_from": "2025-01-01",
            "submit_for_review": False,
        }
        payload.update(overrides)
        return payload

    def test_create_collection_requires_named_create_capability(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("api-waste-collection-create"),
            self._create_payload(),
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Collection.objects.filter(owner=self.staff).exists())

    def test_create_collection_records_creation_event(self):
        self.owner.user_permissions.add(self.add_collection)
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("api-waste-collection-create"),
            self._create_payload(),
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        collection = Collection.objects.get(pk=response.data["id"])
        self.assertEqual(collection.owner, self.owner)
        self.assertEqual(collection.publication_status, "private")
        self.assertTrue(
            ReviewAction.for_object(collection)
            .filter(action=ReviewAction.ACTION_CREATED)
            .exists()
        )

    def test_create_collection_denies_inaccessible_references(self):
        private_frequency = CollectionFrequency.objects.create(
            name="Hidden Frequency",
            owner=self.stranger,
            publication_status="private",
        )
        self.owner.user_permissions.add(self.add_collection)
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("api-waste-collection-create"),
            self._create_payload(frequency=private_frequency.pk),
            format="json",
        )
        self.assertIn(response.status_code, {400, 403})
        self.assertEqual(
            Collection.objects.filter(owner=self.owner)
            .exclude(pk=self.collection.pk)
            .count(),
            0,
        )

    def _cpv_payload(self, collection, **overrides):
        self.cpv_property = Property.objects.create(
            name="CPV Prop", publication_status="published"
        )
        self.cpv_unit = Unit.objects.create(
            name="CPV Unit", publication_status="published"
        )
        payload = {
            "collection": collection.pk,
            "property_id": self.cpv_property.pk,
            "unit_name": self.cpv_unit.name,
            "year": 2024,
            "average": 1.5,
            "submit_for_review": False,
        }
        payload.update(overrides)
        return payload

    def test_create_property_value_allows_read_published_parent(self):
        self.editor.user_permissions.add(self.add_cpv)
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse("api-waste-collection-property-value-create"),
            self._cpv_payload(self.published_collection),
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        cpv = CollectionPropertyValue.objects.get(pk=response.data["id"])
        self.assertEqual(cpv.owner, self.editor)
        self.assertEqual(cpv.publication_status, "private")
        self.assertTrue(
            ReviewAction.for_object(cpv)
            .filter(action=ReviewAction.ACTION_CREATED)
            .exists()
        )

    def test_create_property_value_denies_inaccessible_parent(self):
        self.editor.user_permissions.add(self.add_cpv)
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse("api-waste-collection-property-value-create"),
            self._cpv_payload(self.collection),
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            CollectionPropertyValue.objects.filter(collection=self.collection).exists()
        )

    def test_create_property_value_without_add_permission_denied(self):
        self.editor.user_permissions.remove(self.add_cpv)
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse("api-waste-collection-property-value-create"),
            self._cpv_payload(self.published_collection),
            format="json",
        )
        self.assertEqual(response.status_code, 403)


class MaterialsDomainFixture(TestCase):
    """Shared fixture for sample-scoped writer contract tests."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="mat-owner")
        cls.editor = User.objects.create_user(username="mat-editor")
        cls.stranger = User.objects.create_user(username="mat-stranger")
        cls.staff = User.objects.create_user(username="mat-staff", is_staff=True)
        cls.material = Material.objects.create(owner=cls.owner, name="Domain Material")
        cls.series = SampleSeries.objects.create(
            owner=cls.owner, material=cls.material, name="Domain Series"
        )
        cls.sample = cls.series.samples.get(timestep=Timestep.objects.default())
        cls.composition = cls.sample.compositions.get(
            group=MaterialComponentGroup.objects.default()
        )
        # The shared default component is a public-catalogue reference in the
        # supported workflow: private foreign references are denied reads.
        MaterialComponent.objects.filter(pk=cls.composition.fractions_of_id).update(
            publication_status="published"
        )
        cls.second_group = MaterialComponentGroup.objects.create(
            owner=cls.owner, name="Second Domain Group"
        )
        cls.other_composition = Composition.objects.create(
            owner=cls.owner,
            name="Other composition",
            group=cls.second_group,
            sample=cls.sample,
            fractions_of=cls.composition.fractions_of,
            order=2,
        )
        Composition.objects.filter(pk=cls.composition.pk).update(order=1)

    def _orders(self):
        return list(
            Composition.objects.filter(
                pk__in=[self.composition.pk, self.other_composition.pk]
            )
            .order_by("order")
            .values_list("pk", flat=True)
        )


class ReorderWriterTests(MaterialsDomainFixture):
    """Reorder endpoints must be POST-only, policy-bound parent mutations."""

    def test_get_order_up_never_mutates(self):
        self.owner.user_permissions.add(_perm(Sample, "change_sample"))
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("composition-order-up", kwargs={"pk": self.composition.pk})
        )
        self.assertEqual(response.status_code, 405)
        self.assertEqual(
            self._orders(), [self.composition.pk, self.other_composition.pk]
        )

    def test_get_order_down_never_mutates(self):
        self.owner.user_permissions.add(_perm(Sample, "change_sample"))
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("composition-order-down", kwargs={"pk": self.other_composition.pk})
        )
        self.assertEqual(response.status_code, 405)
        self.assertEqual(
            self._orders(), [self.composition.pk, self.other_composition.pk]
        )

    def test_get_derived_order_up_never_mutates(self):
        self.owner.user_permissions.add(_perm(Sample, "change_sample"))
        self.client.force_login(self.owner)
        count_before = Composition.objects.filter(sample=self.sample).count()
        response = self.client.get(
            reverse(
                "derived-composition-order-up",
                kwargs={
                    "sample_pk": self.sample.pk,
                    "group_pk": self.second_group.pk,
                },
            )
        )
        self.assertEqual(response.status_code, 405)
        self.assertEqual(
            Composition.objects.filter(sample=self.sample).count(), count_before
        )
        self.assertEqual(
            self._orders(), [self.composition.pk, self.other_composition.pk]
        )

    def test_post_owner_reorders_and_bumps_sample_revision(self):
        self.owner.user_permissions.add(_perm(Sample, "change_sample"))
        self.client.force_login(self.owner)
        revision_before = Sample.objects.get(pk=self.sample.pk).content_revision
        response = self.client.post(
            reverse("composition-order-up", kwargs={"pk": self.composition.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self._orders(), [self.other_composition.pk, self.composition.pk]
        )
        sample = Sample.objects.get(pk=self.sample.pk)
        self.assertEqual(sample.content_revision, revision_before + 1)
        self.assertTrue(
            ReviewAction.for_object(sample)
            .filter(action=ReviewAction.ACTION_EDITED)
            .exists()
        )

    def test_post_editor_with_grant_reorders(self):
        self.editor.user_permissions.add(_perm(Sample, "change_sample"))
        _grant(self.sample, self.editor)
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse("composition-order-up", kwargs={"pk": self.composition.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self._orders(), [self.other_composition.pk, self.composition.pk]
        )

    def test_post_stranger_denied(self):
        self.stranger.user_permissions.add(_perm(Sample, "change_sample"))
        self.client.force_login(self.stranger)
        response = self.client.post(
            reverse("composition-order-up", kwargs={"pk": self.composition.pk})
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self._orders(), [self.composition.pk, self.other_composition.pk]
        )

    def test_post_staff_only_denied(self):
        self.staff.user_permissions.add(_perm(Sample, "change_sample"))
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("composition-order-up", kwargs={"pk": self.composition.pk})
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self._orders(), [self.composition.pk, self.other_composition.pk]
        )

    def test_post_on_published_sample_denied(self):
        Sample.objects.filter(pk=self.sample.pk).update(publication_status="published")
        self.owner.user_permissions.add(_perm(Sample, "change_sample"))
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("composition-order-up", kwargs={"pk": self.composition.pk})
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self._orders(), [self.composition.pk, self.other_composition.pk]
        )


class SampleBoundWriterTests(MaterialsDomainFixture):
    """Sample-scoped create/update writers use typed attachment decisions."""

    def test_editor_creates_composition_through_sample_scope(self):
        self.editor.user_permissions.add(
            _perm(Sample, "change_sample"), _perm(Composition, "add_composition")
        )
        _grant(self.sample, self.editor)
        third_group = MaterialComponentGroup.objects.create(
            owner=self.owner, name="Third Domain Group"
        )
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse("sample-add-composition", kwargs={"pk": self.sample.pk}),
            {
                "sample": self.sample.pk,
                "group": third_group.pk,
                "fractions_of": self.composition.fractions_of.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Composition.objects.filter(sample=self.sample, group=third_group).exists()
        )

    def test_composition_update_rejects_reparent_to_foreign_sample(self):
        self.owner.user_permissions.add(
            _perm(Sample, "change_sample"),
            _perm(Composition, "change_composition"),
        )
        foreign_sample = Sample.objects.create(
            owner=self.stranger, name="Foreign sample", material=self.material
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("composition-update", kwargs={"pk": self.composition.pk}),
            {
                "group": self.composition.group_id,
                "sample": foreign_sample.pk,
                "fractions_of": self.composition.fractions_of_id,
            },
        )
        self.assertEqual(response.status_code, 403)
        self.composition.refresh_from_db()
        self.assertEqual(self.composition.sample_id, self.sample.pk)

    def test_series_add_composition_requires_series_edit(self):
        self.stranger.user_permissions.add(
            _perm(Composition, "add_composition"),
            _perm(SampleSeries, "change_sampleseries"),
        )
        new_group = MaterialComponentGroup.objects.create(
            owner=self.owner, name="Series Add Group"
        )
        self.client.force_login(self.stranger)
        response = self.client.post(
            reverse("sampleseries-add-composition", kwargs={"pk": self.series.pk}),
            {
                "group": new_group.pk,
                "fractions_of": self.composition.fractions_of_id,
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            Composition.objects.filter(
                sample__series=self.series, group=new_group
            ).exists()
        )

    def test_series_add_composition_owner_via_edit(self):
        self.owner.user_permissions.add(
            _perm(SampleSeries, "change_sampleseries"),
            _perm(Sample, "change_sample"),
        )
        new_group = MaterialComponentGroup.objects.create(
            owner=self.owner, name="Series Owner Group"
        )
        revision_before = Sample.objects.get(pk=self.sample.pk).content_revision
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("sampleseries-add-composition", kwargs={"pk": self.series.pk}),
            {
                "group": new_group.pk,
                "fractions_of": self.composition.fractions_of_id,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Composition.objects.filter(sample=self.sample, group=new_group).exists()
        )
        self.assertGreater(
            Sample.objects.get(pk=self.sample.pk).content_revision, revision_before
        )


class SeriesAddCompositionAtomicityTests(MaterialsDomainFixture):
    """``AddCompositionView.form_valid`` writes the per-sample compositions
    inside one atomic boundary: every sample needs its own editable state
    and access, and a failure on any sample rolls back all writes and
    audits. Composition itself needs no ``add_composition`` permission."""

    def _url(self):
        return reverse("sampleseries-add-composition", kwargs={"pk": self.series.pk})

    def _second_sample(self, *, owner=None, status="private"):
        return Sample.objects.create(
            name="B2a second sample",
            owner=owner or self.owner,
            material=self.material,
            series=self.series,
            publication_status=status,
        )

    def _reference_group(self, *, owner=None, status="published"):
        return MaterialComponentGroup.objects.create(
            owner=owner or self.stranger,
            name=f"B2a reference group {status}",
            publication_status=status,
        )

    def _post(self, group, fractions_of=None):
        return self.client.post(
            self._url(),
            {
                "group": group.pk,
                "fractions_of": fractions_of or self.composition.fractions_of_id,
            },
        )

    def _permit_series_and_sample_edits(self, user):
        user.user_permissions.add(
            _perm(SampleSeries, "change_sampleseries"),
            _perm(Sample, "change_sample"),
        )

    @staticmethod
    def _edited_events(obj):
        return ReviewAction.objects.filter(
            content_type=ContentType.objects.get_for_model(
                obj.__class__, for_concrete_model=False
            ),
            object_id=obj.pk,
            action=ReviewAction.ACTION_EDITED,
        )

    def test_compositions_written_per_sample_with_sample_events(self):
        self._permit_series_and_sample_edits(self.owner)
        sample2 = self._second_sample()
        group = self._reference_group()
        revisions_before = {
            self.sample.pk: self.sample.content_revision,
            sample2.pk: sample2.content_revision,
        }
        series_revision = SampleSeries.objects.get(pk=self.series.pk).content_revision
        self.client.force_login(self.owner)

        response = self._post(group)

        self.assertEqual(response.status_code, 302)
        for sample in (self.sample, sample2):
            self.assertTrue(
                Composition.objects.filter(
                    sample=sample,
                    group=group,
                    fractions_of_id=self.composition.fractions_of_id,
                ).exists()
            )
            sample.refresh_from_db()
            self.assertEqual(sample.content_revision, revisions_before[sample.pk] + 1)
            self.assertEqual(self._edited_events(sample).count(), 1)
        # The locked series had no content change: no revision or event.
        self.series.refresh_from_db()
        self.assertEqual(self.series.content_revision, series_revision)
        self.assertFalse(self._edited_events(self.series).exists())

    def test_frozen_second_sample_denies_and_rolls_back_first(self):
        self._permit_series_and_sample_edits(self.owner)
        sample2 = self._second_sample(status="published")
        group = self._reference_group()
        revisions_before = {
            self.sample.pk: self.sample.content_revision,
            sample2.pk: sample2.content_revision,
        }
        self.client.force_login(self.owner)

        response = self._post(group)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Composition.objects.filter(group=group).exists())
        for sample in (self.sample, sample2):
            sample.refresh_from_db()
            self.assertEqual(sample.content_revision, revisions_before[sample.pk])
            self.assertFalse(self._edited_events(sample).exists())

    def test_foreign_private_second_sample_denies_and_rolls_back(self):
        self._permit_series_and_sample_edits(self.owner)
        sample2 = self._second_sample(owner=self.stranger)
        group = self._reference_group()
        self.client.force_login(self.owner)

        response = self._post(group)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Composition.objects.filter(group=group).exists())
        self.sample.refresh_from_db()
        self.assertFalse(self._edited_events(self.sample).exists())
        self.assertFalse(self._edited_events(sample2).exists())

    def test_audit_failure_on_second_sample_rolls_back_everything(self):
        self._permit_series_and_sample_edits(self.owner)
        self._second_sample()
        group = self._reference_group()
        self.client.force_login(self.owner)

        real_create = ReviewAction.objects.create
        calls = {"n": 0}

        def flaky_create(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise RuntimeError("audit failure")
            return real_create(*args, **kwargs)

        with (
            self.assertLogs("django.request", level="ERROR") as logs,
            self.assertRaises(RuntimeError) as raised,
            patch.object(ReviewAction.objects, "create", side_effect=flaky_create),
        ):
            self._post(group)

        self.assertIn("audit failure", str(raised.exception))
        self.assertTrue(
            any("Internal Server Error" in message for message in logs.output)
        )
        self.assertFalse(Composition.objects.filter(group=group).exists())
        self.sample.refresh_from_db()
        self.assertFalse(self._edited_events(self.sample).exists())

    def test_private_foreign_group_reference_denied(self):
        self._permit_series_and_sample_edits(self.owner)
        self._second_sample()
        group = self._reference_group(status="private")
        self.client.force_login(self.owner)

        response = self._post(group)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Composition.objects.filter(group=group).exists())

    def test_private_foreign_fractions_of_reference_denied(self):
        self._permit_series_and_sample_edits(self.owner)
        self._second_sample()
        group = self._reference_group()
        # Keep the default component a valid form choice (owner unchanged) but
        # turn it into unreadable foreign evidence for this actor.
        component_pk = self.composition.fractions_of_id
        MaterialComponent.objects.filter(pk=component_pk).update(
            publication_status="private"
        )
        self.client.force_login(self.owner)

        response = self._post(group, fractions_of=component_pk)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Composition.objects.filter(group=group).exists())

    def test_own_private_references_allowed(self):
        self._permit_series_and_sample_edits(self.owner)
        sample2 = self._second_sample()
        group = self._reference_group(owner=self.owner, status="private")
        # fractions_of defaults to the published public-catalogue component.
        self.client.force_login(self.owner)

        response = self._post(group)

        self.assertEqual(response.status_code, 302)
        for sample in (self.sample, sample2):
            self.assertTrue(
                Composition.objects.filter(sample=sample, group=group).exists()
            )

    def test_shared_editor_grants_allow_without_add_composition(self):
        self._permit_series_and_sample_edits(self.editor)
        sample2 = self._second_sample()
        for obj in (self.series, self.sample, sample2):
            _grant(obj, self.editor)
        group = self._reference_group()
        revisions_before = {
            self.sample.pk: self.sample.content_revision,
            sample2.pk: sample2.content_revision,
        }
        self.client.force_login(self.editor)

        response = self._post(group)

        self.assertEqual(response.status_code, 302)
        for sample in (self.sample, sample2):
            sample.refresh_from_db()
            # The grant holder wrote the rows; ownership stays with the owners.
            self.assertEqual(sample.owner, self.owner)
            self.assertEqual(sample.content_revision, revisions_before[sample.pk] + 1)
            self.assertEqual(self._edited_events(sample).count(), 1)
            self.assertTrue(
                Composition.objects.filter(
                    sample=sample, group=group, owner=self.editor
                ).exists()
            )
        self.series.refresh_from_db()
        self.assertEqual(self.series.owner, self.owner)

    def test_archived_second_sample_denies_and_rolls_back(self):
        self._permit_series_and_sample_edits(self.owner)
        sample2 = self._second_sample(status="archived")
        group = self._reference_group()
        revisions_before = {
            self.sample.pk: self.sample.content_revision,
            sample2.pk: sample2.content_revision,
        }
        self.client.force_login(self.owner)

        response = self._post(group)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Composition.objects.filter(group=group).exists())
        for sample in (self.sample, sample2):
            sample.refresh_from_db()
            self.assertEqual(sample.content_revision, revisions_before[sample.pk])
            self.assertFalse(self._edited_events(sample).exists())

    def test_moved_sample_under_lock_denies_and_rolls_back(self):
        self._permit_series_and_sample_edits(self.owner)
        sample2 = self._second_sample()
        other_series = SampleSeries.objects.create(
            owner=self.owner, material=self.material, name="B2a other series"
        )
        group = self._reference_group()
        self.client.force_login(self.owner)

        real_mutation = content_mutation

        def reparent_before_lock(actor, target, **kwargs):
            if isinstance(target, Sample) and target.pk == sample2.pk:
                # Concurrent reparent between queryset evaluation and row lock.
                Sample.objects.filter(pk=sample2.pk).update(series=other_series)
            return real_mutation(actor, target, **kwargs)

        with patch(
            "materials.views.content_mutation", side_effect=reparent_before_lock
        ):
            response = self._post(group)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Composition.objects.filter(group=group).exists())
        for sample in (self.sample, sample2):
            sample.refresh_from_db()
            self.assertEqual(sample.series_id, self.series.pk)
            self.assertFalse(self._edited_events(sample).exists())


class GreenhouseWriterTests(TestCase):
    """Greenhouse growth writers use parent-scope policy and services."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="gh-owner")
        cls.editor = User.objects.create_user(username="gh-editor")
        cls.stranger = User.objects.create_user(username="gh-stranger")
        cls.staff = User.objects.create_user(username="gh-staff", is_staff=True)
        cls.material = Material.objects.create(owner=cls.owner, name="GH Material")
        cls.residue = SampleSeries.objects.create(
            owner=cls.owner, material=cls.material, name="GH Residue"
        )
        cls.culture = Culture.objects.create(
            owner=cls.owner, name="GH Culture", residue=cls.residue
        )
        cls.greenhouse = Greenhouse.objects.create(
            owner=cls.owner, name="GH Greenhouse"
        )
        cls.other_greenhouse = Greenhouse.objects.create(
            owner=cls.stranger, name="Foreign Greenhouse"
        )
        base_composition = cls.residue.samples.get(
            timestep=Timestep.objects.default()
        ).compositions.get(group=MaterialComponentGroup.objects.default())
        cls.group_settings = base_composition
        cls.cycle = GreenhouseGrowthCycle.objects.create(
            owner=cls.owner,
            culture=cls.culture,
            greenhouse=cls.greenhouse,
            group_settings=cls.group_settings,
        )
        distribution, _ = TemporalDistribution.objects.get_or_create(
            name="Months of the year"
        )
        cls.timestep, _ = Timestep.objects.get_or_create(
            name="January", distribution=distribution
        )
        cls.timestepset = GrowthTimeStepSet.objects.create(
            owner=cls.owner, growth_cycle=cls.cycle, timestep=cls.timestep
        )

    def test_cycle_values_update_denies_stranger(self):
        self.client.force_login(self.stranger)
        url = reverse(
            "greenhouse_growth_cycle_update_values",
            kwargs={"pk": self.greenhouse.pk, "cycle_pk": self.cycle.pk},
        )
        self.assertEqual(self.client.get(url).status_code, 403)
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 403)
        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.owner, self.owner)

    def test_cycle_values_update_preserves_owner_on_editor_post(self):
        self.editor.user_permissions.add(_perm(Greenhouse, "change_greenhouse"))
        _grant(self.greenhouse, self.editor)
        self.client.force_login(self.editor)
        url = reverse(
            "greenhouse_growth_cycle_update_values",
            kwargs={"pk": self.greenhouse.pk, "cycle_pk": self.cycle.pk},
        )
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 302)
        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.owner, self.owner)

    def test_timestepset_update_allows_greenhouse_editor(self):
        self.editor.user_permissions.add(_perm(Greenhouse, "change_greenhouse"))
        _grant(self.greenhouse, self.editor)
        self.client.force_login(self.editor)
        response = self.client.get(
            reverse(
                "greenhousegrowthcycle-timestep-update-modal",
                kwargs={"pk": self.timestepset.pk},
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_timestepset_update_denies_staff_only(self):
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse(
                "greenhousegrowthcycle-timestep-update-modal",
                kwargs={"pk": self.timestepset.pk},
            )
        )
        self.assertEqual(response.status_code, 403)

    def test_inline_cycle_create_denies_foreign_greenhouse(self):
        self.stranger.user_permissions.add(
            _perm(GreenhouseGrowthCycle, "add_greenhousegrowthcycle")
        )
        self.client.force_login(self.stranger)
        count_before = GreenhouseGrowthCycle.objects.count()
        response = self.client.post(
            reverse("growth_cycle_create_inline"),
            {
                "culture": self.culture.pk,
                "greenhouse": self.greenhouse.pk,
                "group_settings": self.group_settings.pk,
                "growthtimestepset_set-TOTAL_FORMS": 0,
                "growthtimestepset_set-INITIAL_FORMS": 0,
                "growthtimestepset_set-MIN_NUM_FORMS": 0,
                "growthtimestepset_set-MAX_NUM_FORMS": 1000,
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(GreenhouseGrowthCycle.objects.count(), count_before)

    def test_modal_cycle_create_bumps_greenhouse_revision(self):
        self.owner.user_permissions.add(_perm(Greenhouse, "change_greenhouse"))
        revision_before = Greenhouse.objects.get(pk=self.greenhouse.pk).content_revision
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("greenhousegrowthcycle-create", kwargs={"pk": self.greenhouse.pk}),
            {"culture": self.culture.pk, "timesteps": [self.timestep.pk]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            GreenhouseGrowthCycle.objects.filter(
                greenhouse=self.greenhouse, culture=self.culture
            )
            .exclude(pk=self.cycle.pk)
            .exists()
        )
        self.assertGreater(
            Greenhouse.objects.get(pk=self.greenhouse.pk).content_revision,
            revision_before,
        )

    def test_modal_cycle_create_denies_published_greenhouse(self):
        Greenhouse.objects.filter(pk=self.greenhouse.pk).update(
            publication_status="published"
        )
        self.owner.user_permissions.add(_perm(Greenhouse, "change_greenhouse"))
        self.client.force_login(self.owner)
        count_before = GreenhouseGrowthCycle.objects.count()
        response = self.client.post(
            reverse("greenhousegrowthcycle-create", kwargs={"pk": self.greenhouse.pk}),
            {"culture": self.culture.pk, "timesteps": [self.timestep.pk]},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(GreenhouseGrowthCycle.objects.count(), count_before)


class CheckUrlActionTests(TestCase):
    """URL health checks are operational metadata gated by check_url."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="url-owner")
        cls.stranger = User.objects.create_user(username="url-stranger")
        cls.staff = User.objects.create_user(username="url-staff", is_staff=True)
        cls.flyer = WasteFlyer.objects.create(
            owner=cls.owner,
            title="Owned flyer",
            abbreviation="WF-domain",
            url="https://example.com/flyer.pdf",
        )
        cls.foreign_flyer = WasteFlyer.objects.create(
            owner=cls.stranger,
            title="Foreign flyer",
            abbreviation="WF-foreign",
            url="https://example.com/foreign.pdf",
        )
        cls.published_flyer = WasteFlyer.objects.create(
            owner=cls.stranger,
            title="Published flyer",
            abbreviation="WF-pub",
            url="https://example.com/published.pdf",
            publication_status="published",
        )
        cls.source = Source.objects.create(
            owner=cls.owner,
            title="Owned source",
            url="https://example.com/source.pdf",
        )
        cls.material = Material.objects.create(
            owner=cls.owner, name="URL-check Material"
        )

    def test_owner_with_change_permission_gets_check_url(self):
        from utils.object_management.policy import decide

        self.owner.user_permissions.add(_perm(WasteFlyer, "change_wasteflyer"))
        self.assertTrue(decide(self.owner, "check_url", self.flyer).allowed)

    def test_missing_model_permission_denies_check_url(self):
        from utils.object_management.policy import decide

        decision = decide(self.owner, "check_url", self.flyer)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "missing_model_permission")

    def test_foreign_private_target_denies_check_url(self):
        from utils.object_management.policy import decide

        self.stranger.user_permissions.add(_perm(WasteFlyer, "change_wasteflyer"))
        self.assertFalse(decide(self.stranger, "check_url", self.flyer).allowed)

    def test_published_target_allows_check_url_for_permitted_actor(self):
        from utils.object_management.policy import decide

        self.stranger.user_permissions.add(_perm(WasteFlyer, "change_wasteflyer"))
        self.assertTrue(
            decide(self.stranger, "check_url", self.published_flyer).allowed
        )

    def test_check_url_unsupported_for_other_models(self):
        from utils.object_management.policy import decide

        self.owner.user_permissions.add(_perm(Sample, "change_sample"))
        self.assertFalse(decide(self.owner, "check_url", self.material).allowed)

    def test_anonymous_denied_check_url(self):
        from django.contrib.auth.models import AnonymousUser

        from utils.object_management.policy import decide

        self.assertFalse(
            decide(AnonymousUser(), "check_url", self.published_flyer).allowed
        )

    def test_single_flyer_check_denies_staff_only(self):
        from unittest.mock import patch

        self.staff.user_permissions.add(_perm(WasteFlyer, "change_wasteflyer"))
        self.client.force_login(self.staff)
        with patch("sources.waste_collection.views.check_wasteflyer_url") as mock_task:
            response = self.client.get(
                reverse("wasteflyer-check-url", kwargs={"pk": self.flyer.pk})
            )
        self.assertEqual(response.status_code, 403)
        mock_task.delay.assert_not_called()

    def test_single_flyer_check_denies_foreign_private(self):
        from unittest.mock import patch

        self.stranger.user_permissions.add(_perm(WasteFlyer, "change_wasteflyer"))
        self.client.force_login(self.stranger)
        with patch("sources.waste_collection.views.check_wasteflyer_url") as mock_task:
            response = self.client.get(
                reverse("wasteflyer-check-url", kwargs={"pk": self.flyer.pk})
            )
        self.assertEqual(response.status_code, 403)
        mock_task.delay.assert_not_called()

    def test_single_flyer_check_owner_dispatches_and_binds_job(self):
        from unittest.mock import patch

        self.owner.user_permissions.add(_perm(WasteFlyer, "change_wasteflyer"))
        self.client.force_login(self.owner)
        with (
            patch("sources.waste_collection.views.check_wasteflyer_url") as mock_task,
            patch("sources.waste_collection.views.AsyncResult") as mock_result,
        ):
            mock_task.delay.return_value.task_id = "job-1"
            response = self.client.get(
                reverse("wasteflyer-check-url", kwargs={"pk": self.flyer.pk})
            )
            self.assertEqual(response.status_code, 200)
            mock_task.delay.assert_called_once()
            mock_result.return_value.state = "SUCCESS"
            mock_result.return_value.info = {}
            progress = self.client.get(
                reverse("wasteflyer-check-url-progress", kwargs={"task_id": "job-1"})
            )
        self.assertEqual(progress.status_code, 200)

    def test_progress_view_denies_other_users_job(self):
        from unittest.mock import patch

        self.owner.user_permissions.add(_perm(WasteFlyer, "change_wasteflyer"))
        self.client.force_login(self.owner)
        with patch("sources.waste_collection.views.check_wasteflyer_url") as mock_task:
            mock_task.delay.return_value.task_id = "job-2"
            self.client.get(
                reverse("wasteflyer-check-url", kwargs={"pk": self.flyer.pk})
            )
        self.stranger.user_permissions.add(_perm(WasteFlyer, "change_wasteflyer"))
        self.client.force_login(self.stranger)
        with patch("sources.waste_collection.views.AsyncResult") as mock_result:
            mock_result.return_value.state = "SUCCESS"
            mock_result.return_value.info = {}
            response = self.client.get(
                reverse("wasteflyer-check-url-progress", kwargs={"task_id": "job-2"})
            )
        self.assertEqual(response.status_code, 404)
        mock_result.assert_not_called()

    def test_batch_scoped_to_decidable_targets(self):
        from unittest.mock import patch

        from sources.waste_collection.tasks import check_wasteflyer_urls

        self.owner.user_permissions.add(_perm(WasteFlyer, "change_wasteflyer"))
        captured = {}

        def fake_chord(header):
            captured["header"] = list(header)
            return lambda _cb: type("Task", (object,), {"task_id": "batch-job"})()

        with (
            patch("sources.waste_collection.tasks.chord", side_effect=fake_chord),
            patch("sources.waste_collection.tasks.check_wasteflyer_urls_callback"),
        ):
            check_wasteflyer_urls.run(
                QueryDict("scope=private", mutable=True), self.owner.pk
            )
        scheduled = sorted(sig.args[0] for sig in captured["header"])
        self.assertEqual(scheduled, [self.flyer.pk])

    def test_batch_view_passes_actor_identity(self):
        from unittest.mock import patch

        self.owner.user_permissions.add(_perm(WasteFlyer, "change_wasteflyer"))
        self.client.force_login(User.objects.get(pk=self.owner.pk))
        with patch(
            "sources.waste_collection.views.check_wasteflyer_urls.delay"
        ) as mock_delay:
            mock_delay.return_value.task_id = "batch-1"
            response = self.client.get(reverse("wasteflyer-list-check-urls"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_delay.call_args.args[-1], self.owner.pk)

    def test_task_updates_only_health_metadata(self):
        from unittest.mock import patch

        from sources.waste_collection.tasks import check_wasteflyer_url

        with patch("sources.waste_collection.tasks.check_url", return_value=False):
            check_wasteflyer_url.run(self.flyer.pk)
        self.flyer.refresh_from_db()
        self.assertEqual(self.flyer.url, "https://example.com/flyer.pdf")
        self.assertFalse(self.flyer.url_valid)
        self.assertIsNotNone(self.flyer.url_checked)
        self.assertEqual(self.flyer.owner, self.owner)
        self.assertEqual(self.flyer.publication_status, "private")

    def test_source_check_view_uses_named_action(self):
        from unittest.mock import patch

        self.staff.user_permissions.add(_perm(Source, "change_source"))
        self.client.force_login(self.staff)
        with patch("bibliography.views.check_source_url") as mock_task:
            response = self.client.get(
                reverse("source-check-url", kwargs={"pk": self.source.pk})
            )
        self.assertEqual(response.status_code, 403)
        mock_task.delay.assert_not_called()
