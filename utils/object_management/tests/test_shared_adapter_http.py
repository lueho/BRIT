"""Real-request regression tests for the shared policy adapters.

Both ``UserCreatedObjectViewSet`` and ``AutoPermModelViewSet`` must apply the
same authorization contract: literal policy expectations (not values recomputed
from ``decide``), exercised through real HTTP calls against test-local viewset
endpoints for a real registered model (``utils.properties.Property``).
"""

import io
from types import SimpleNamespace
from unittest.mock import patch

from django import forms
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.forms import modelform_factory
from django.http import HttpResponse, HttpResponseServerError
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import isolate_apps
from django.urls import include, path, reverse
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter

from bibliography.models import Author, Source, SourceAuthor
from maps.models import (
    GeoDataset,
    GeoDatasetColumnPolicy,
    GeoDatasetRuntimeConfiguration,
    GeoPolygon,
    Region,
)
from materials.models import Material, SampleSeries
from sources.waste_collection.models import (
    AggregatedCollectionPropertyValue,
    Collection,
)
from utils.object_management.policy import decide, decide_reassign, editable_queryset
from utils.properties.models import Property, Unit
from utils.viewsets import AutoPermModelViewSet

from ..models import (
    ObjectEditorGrant,
    ObjectGroupEditorGrant,
    ReviewAction,
    UserCreatedObject,
)
from ..templatetags.moderation_tags import model_creation_policy
from ..views import (
    UserCreatedObjectModalDeleteView,
    _perform_bound_create,
    _perform_bound_update,
)
from ..viewsets import UserCreatedObjectViewSet


class _PropertySerializer(serializers.ModelSerializer):
    allowed_units = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Unit.objects.all(), required=False
    )

    class Meta:
        model = Property
        fields = ("name", "description", "allowed_units")


class _UCOPropertyViewSet(UserCreatedObjectViewSet):
    queryset = Property.objects.all()
    serializer_class = _PropertySerializer


class _AutoPermPropertyViewSet(AutoPermModelViewSet):
    queryset = Property.objects.all()
    serializer_class = _PropertySerializer


class _ColumnPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = GeoDatasetColumnPolicy
        fields = ("dataset", "column_name", "display_label")


class _UCOColumnPolicyViewSet(UserCreatedObjectViewSet):
    queryset = GeoDatasetColumnPolicy.objects.all()
    serializer_class = _ColumnPolicySerializer


class _AutoPermColumnPolicyViewSet(AutoPermModelViewSet):
    queryset = GeoDatasetColumnPolicy.objects.all()
    serializer_class = _ColumnPolicySerializer


class _SampleSeriesSerializer(serializers.ModelSerializer):
    class Meta:
        model = SampleSeries
        fields = ("name", "material")


class _UCOSampleSeriesViewSet(UserCreatedObjectViewSet):
    queryset = SampleSeries.objects.all()
    serializer_class = _SampleSeriesSerializer

    @action(detail=True, methods=["post"])
    def frobnicate(self, request, pk=None):
        from utils.object_management.services import perform_transition

        obj = self.get_object()
        perform_transition(request.user, obj, "frobnicate")
        return Response({"ok": True})


class _AutoPermSampleSeriesViewSet(AutoPermModelViewSet):
    queryset = SampleSeries.objects.all()
    serializer_class = _SampleSeriesSerializer
    custom_permission_required = {"frobnicate": None}

    @action(detail=True, methods=["post"])
    def frobnicate(self, request, pk=None):
        from utils.object_management.services import perform_transition

        obj = self.get_object()
        perform_transition(request.user, obj, "frobnicate")
        return Response({"ok": True})


_router = DefaultRouter()
_router.register("uco-property", _UCOPropertyViewSet, basename="uco-property")
_router.register(
    "autoperm-property", _AutoPermPropertyViewSet, basename="autoperm-property"
)
_router.register("uco-colpol", _UCOColumnPolicyViewSet, basename="uco-colpol")
_router.register(
    "autoperm-colpol", _AutoPermColumnPolicyViewSet, basename="autoperm-colpol"
)
_router.register("uco-series", _UCOSampleSeriesViewSet, basename="uco-series")
_router.register(
    "autoperm-series", _AutoPermSampleSeriesViewSet, basename="autoperm-series"
)

COLPOL_ADAPTERS = ("uco-colpol", "autoperm-colpol")
SERIES_ADAPTERS = ("uco-series", "autoperm-series")


def _plain_500(request):
    return HttpResponseServerError("error")


urlpatterns = [
    path("home/", lambda request: HttpResponse(""), name="home"),
    path("login/", lambda request: HttpResponse(""), name="auth_login"),
    path("om/", include("utils.object_management.urls")),
    *_router.urls,
]


def _plain_403(request, exception=None):
    from django.http import HttpResponseForbidden

    return HttpResponseForbidden("denied")


handler403 = _plain_403
handler500 = _plain_500

ADAPTERS = ("uco-property", "autoperm-property")


def _events(obj, action=None):
    qs = ReviewAction.objects.filter(
        content_type=ContentType.objects.get_for_model(obj), object_id=obj.pk
    )
    return qs.filter(action=action) if action else qs


@override_settings(
    ROOT_URLCONF="utils.object_management.tests.test_shared_adapter_http"
)
class SharedAdapterHttpTests(TestCase):
    """Identical contract for both base viewsets, exercised over real HTTP."""

    @classmethod
    def setUpTestData(cls):
        call_command("sync_roles", "--apply", stdout=io.StringIO())

    def setUp(self):
        self.registered = Group.objects.get(name="registered")
        self.owner = User.objects.create_user(username="owner")
        self.direct_editor = User.objects.create_user(username="direct-editor")
        self.group_editor = User.objects.create_user(username="group-editor")
        self.stranger = User.objects.create_user(username="stranger")
        self.no_change_owner = User.objects.create_user(username="no-change-owner")
        self.staff = User.objects.create_user(username="staff", is_staff=True)
        self.inactive = User.objects.create_user(username="inactive", is_active=False)
        self.admin = User.objects.create_user(username="app-admin")
        self.moderator = User.objects.create_user(username="moderator")
        for user in (
            self.owner,
            self.direct_editor,
            self.group_editor,
            self.stranger,
            self.moderator,
        ):
            user.groups.add(self.registered)
        self.admin.groups.add(Group.objects.get(name="administrators"))
        self.no_change_owner.groups.clear()
        self.staff.groups.clear()
        self.no_change_owner.user_permissions.add(
            Permission.objects.get(codename="add_property")
        )
        self.moderator.user_permissions.add(
            Permission.objects.get(codename="can_moderate_property")
        )

        self.prop = Property.objects.create(
            name="Shared Prop", owner=self.owner, publication_status="private"
        )
        ct = ContentType.objects.get_for_model(Property)
        ObjectEditorGrant.objects.create(
            content_type=ct, object_id=self.prop.pk, editor=self.direct_editor
        )
        self.editor_group = Group.objects.create(name="prop-editors")
        self.group_editor.groups.add(self.editor_group)
        ObjectGroupEditorGrant.objects.create(
            content_type=ct, object_id=self.prop.pk, group=self.editor_group
        )
        self.own_unit = Unit.objects.create(name="kg", symbol="kg", owner=self.owner)
        self.foreign_unit = Unit.objects.create(
            name="secret", symbol="s", owner=self.stranger
        )

    # -- helpers ------------------------------------------------------------

    def _detail(self, prefix, pk=None):
        return reverse(f"{prefix}-detail", kwargs={"pk": pk or self.prop.pk})

    def _list(self, prefix, scope=None):
        url = reverse(f"{prefix}-list")
        return f"{url}?scope={scope}" if scope else url

    def _action(self, prefix, name, pk=None):
        return reverse(f"{prefix}-{name}", kwargs={"pk": pk or self.prop.pk})

    def _patch(self, prefix, user, data, pk=None):
        self.client.force_login(user)
        return self.client.patch(
            self._detail(prefix, pk), data, content_type="application/json"
        )

    def _review_prop(self):
        self.prop.publication_status = UserCreatedObject.STATUS_REVIEW
        self.prop.save(update_fields=["publication_status"])
        return self.prop

    def _assert_edited_once(self, prop=None):
        prop = prop or self.prop
        prop.refresh_from_db()
        self.assertEqual(prop.content_revision, 2)
        self.assertEqual(_events(prop, "edited").count(), 1)

    # -- shared allow paths -------------------------------------------------

    def test_owner_edit_in_review(self):
        self._review_prop()
        for prefix in ADAPTERS:
            with self.subTest(adapter=prefix):
                response = self._patch(prefix, self.owner, {"name": "Edited"})
                self.assertEqual(response.status_code, 200)
                self.prop.refresh_from_db()
                self.assertEqual(self.prop.name, "Edited")
                self.assertEqual(
                    self.prop.publication_status,
                    UserCreatedObject.STATUS_REVIEW,
                )
                self._assert_edited_once()
                # reset for the second adapter
                self.prop.name = "Shared Prop"
                self.prop.content_revision = 1
                self.prop.save()
                _events(self.prop).delete()

    def test_direct_and_group_editor_edit_in_review(self):
        for prefix in ADAPTERS:
            for persona in (self.direct_editor, self.group_editor):
                with self.subTest(adapter=prefix, persona=persona.username):
                    prop = Property.objects.create(
                        name="E", owner=self.owner, publication_status="review"
                    )
                    ct = ContentType.objects.get_for_model(Property)
                    if persona is self.direct_editor:
                        ObjectEditorGrant.objects.create(
                            content_type=ct, object_id=prop.pk, editor=persona
                        )
                    else:
                        ObjectGroupEditorGrant.objects.create(
                            content_type=ct,
                            object_id=prop.pk,
                            group=self.editor_group,
                        )
                    response = self._patch(
                        prefix, persona, {"name": "Edited"}, pk=prop.pk
                    )
                    self.assertEqual(response.status_code, 200)
                    prop.refresh_from_db()
                    self.assertEqual(prop.name, "Edited")
                    self.assertEqual(prop.publication_status, "review")
                    self._assert_edited_once(prop)

    def test_revoked_grant_denies_next_request(self):
        ct = ContentType.objects.get_for_model(Property)
        for prefix in ADAPTERS:
            with self.subTest(adapter=prefix):
                ObjectEditorGrant.objects.get_or_create(
                    content_type=ct,
                    object_id=self.prop.pk,
                    editor=self.direct_editor,
                )
                response = self._patch(prefix, self.direct_editor, {"name": "Allowed"})
                self.assertEqual(response.status_code, 200)
                ObjectEditorGrant.objects.filter(
                    object_id=self.prop.pk, editor=self.direct_editor
                ).delete()
                response = self._patch(prefix, self.direct_editor, {"name": "Revoked"})
                self.assertEqual(response.status_code, 404)
                self.prop.refresh_from_db()
                self.assertEqual(self.prop.name, "Allowed")

    # -- shared denials -----------------------------------------------------

    def test_denied_personas_no_delta(self):
        self._review_prop()
        cases = {
            "anonymous": None,
            "inactive": self.inactive,
            "staff_only": self.staff,
            "owner_without_change": self.no_change_owner,
            "unrelated": self.stranger,
        }
        self.no_change_prop = Property.objects.create(
            name="NC",
            owner=self.no_change_owner,
            publication_status="private",
        )
        for prefix in ADAPTERS:
            for label, user in cases.items():
                target = (
                    self.no_change_prop
                    if label == "owner_without_change"
                    else self.prop
                )
                with self.subTest(adapter=prefix, persona=label):
                    if user is None:
                        self.client.logout()
                    else:
                        self.client.force_login(user)
                    response = self.client.patch(
                        self._detail(prefix, target.pk),
                        {"name": "Denied"},
                        content_type="application/json",
                    )
                    self.assertIn(response.status_code, (401, 403, 404))
                    target.refresh_from_db()
                    self.assertNotEqual(target.name, "Denied")
                    self.assertFalse(_events(target).exists())

    def test_frozen_states_deny_even_admin(self):
        for frozen in ("published", "archived"):
            prop = Property.objects.create(
                name="F", owner=self.owner, publication_status=frozen
            )
            revision = prop.content_revision
            for prefix in ADAPTERS:
                with self.subTest(adapter=prefix, status=frozen):
                    response = self._patch(
                        prefix, self.admin, {"name": "X"}, pk=prop.pk
                    )
                    self.assertIn(response.status_code, (403, 404))
                    prop.refresh_from_db()
                    self.assertEqual(prop.name, "F")
                    self.assertEqual(prop.content_revision, revision)
                    self.assertFalse(_events(prop).exists())

    def test_protected_payload_fields_not_forged(self):
        for prefix in ADAPTERS:
            with self.subTest(adapter=prefix):
                response = self._patch(
                    prefix,
                    self.owner,
                    {
                        "name": "Legit",
                        "owner": self.stranger.pk,
                        "publication_status": "published",
                        "content_revision": 42,
                    },
                )
                # protected keys are denied outright, never forged
                self.assertIn(response.status_code, (400, 403))
                self.prop.refresh_from_db()
                self.assertEqual(self.prop.owner, self.owner)
                self.assertEqual(
                    self.prop.publication_status,
                    UserCreatedObject.STATUS_PRIVATE,
                )
                self.assertEqual(self.prop.content_revision, 1)
                self.assertEqual(self.prop.name, "Shared Prop")

    def test_unknown_scope_fails_closed(self):
        for prefix in ADAPTERS:
            with self.subTest(adapter=prefix):
                self.client.force_login(self.owner)
                response = self.client.get(self._list(prefix, "bogus-scope"))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), [])

    def test_list_and_detail_read_visibility(self):
        for prefix in ADAPTERS:
            with self.subTest(adapter=prefix):
                self.client.force_login(self.stranger)
                response = self.client.get(self._list(prefix))
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("Shared Prop", [r["name"] for r in response.json()])
                self.assertEqual(self.client.get(self._detail(prefix)).status_code, 404)
                self.client.force_login(self.owner)
                response = self.client.get(self._list(prefix))
                names = [r["name"] for r in response.json()]
                self.assertIn("Shared Prop", names)

    # -- reference write boundary -------------------------------------------

    def test_inaccessible_m2m_reference_denied_with_rollback(self):
        self._review_prop()
        revision = self.prop.content_revision
        for prefix in ADAPTERS:
            with self.subTest(adapter=prefix):
                response = self._patch(
                    prefix,
                    self.owner,
                    {"name": "ShouldNotStick", "allowed_units": [self.foreign_unit.pk]},
                )
                self.assertEqual(response.status_code, 403)
                self.prop.refresh_from_db()
                self.assertEqual(self.prop.name, "Shared Prop")
                self.assertEqual(self.prop.content_revision, revision)
                self.assertEqual(self.prop.allowed_units.count(), 0)
                self.assertFalse(_events(self.prop).exists())

    def test_readable_m2m_reference_accepted(self):
        for prefix in ADAPTERS:
            with self.subTest(adapter=prefix):
                response = self._patch(
                    prefix, self.owner, {"allowed_units": [self.own_unit.pk]}
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    list(self.prop.allowed_units.values_list("pk", flat=True)),
                    [self.own_unit.pk],
                )
                self.prop.allowed_units.clear()
                _events(self.prop).delete()
                Property.objects.filter(pk=self.prop.pk).update(content_revision=1)

    def test_audit_failure_rolls_back_content_and_relations(self):
        for prefix in ADAPTERS:
            with self.subTest(adapter=prefix):
                self.client.force_login(self.owner)
                with (
                    self.assertLogs("django.request", level="ERROR"),
                    self.assertRaises(RuntimeError),
                    patch.object(
                        ReviewAction.objects,
                        "create",
                        side_effect=RuntimeError("audit failure"),
                    ),
                ):
                    self.client.patch(
                        self._detail(prefix),
                        {
                            "name": "Rolled",
                            "allowed_units": [self.own_unit.pk],
                        },
                        content_type="application/json",
                    )
                self.prop.refresh_from_db()
                self.assertEqual(self.prop.name, "Shared Prop")
                self.assertEqual(self.prop.content_revision, 1)
                self.assertEqual(self.prop.allowed_units.count(), 0)

    # -- review transport ----------------------------------------------------

    def test_approve_requires_matching_revision(self):
        self._review_prop()
        for prefix in ("uco-property",):
            with self.subTest(adapter=prefix):
                self.client.force_login(self.moderator)
                response = self.client.post(self._action(prefix, "approve"))
                self.assertEqual(response.status_code, 400)
                response = self.client.post(
                    self._action(prefix, "approve"), {"expected_revision": 999}
                )
                self.assertEqual(response.status_code, 409)
                self.prop.refresh_from_db()
                self.assertEqual(self.prop.publication_status, "review")
                response = self.client.post(
                    self._action(prefix, "approve"),
                    {"expected_revision": self.prop.content_revision},
                )
                self.assertEqual(response.status_code, 200)
                self.prop.refresh_from_db()
                self.assertEqual(self.prop.publication_status, "published")
                # reset for second adapter
                self.prop.publication_status = "review"
                self.prop.save(update_fields=["publication_status"])

    def test_review_comment_survives_edit(self):
        self._review_prop()
        ct = ContentType.objects.get_for_model(Property)
        comment_url = reverse(
            "object_management:api_add_review_comment",
            kwargs={"content_type_id": ct.pk, "object_id": self.prop.pk},
        )
        self.client.force_login(self.moderator)
        response = self.client.post(
            comment_url, {"message": "kept"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        for prefix in ADAPTERS:
            with self.subTest(adapter=prefix):
                response = self._patch(prefix, self.owner, {"description": "d"})
                self.assertEqual(response.status_code, 200)
        self.assertTrue(_events(self.prop, "comment").filter(comment="kept").exists())

    # -- direct boundary regression -----------------------------------------

    def test_perform_update_uses_fresh_locked_instance(self):
        """A serializer bound to a stale instance must write onto the fresh
        locked row, preserving a concurrent description change."""
        for cls in (_UCOPropertyViewSet, _AutoPermPropertyViewSet):
            with self.subTest(viewset=cls.__name__):
                prop = Property.objects.create(
                    name="Old",
                    description="orig",
                    owner=self.owner,
                    publication_status="private",
                )
                stale = Property.objects.get(pk=prop.pk)
                serializer = _PropertySerializer(
                    instance=stale, data={"name": "New"}, partial=True
                )
                self.assertTrue(serializer.is_valid(), serializer.errors)
                Property.objects.filter(pk=prop.pk).update(description="concurrent")
                view = cls()
                view.request = SimpleNamespace(user=self.owner)
                view.kwargs = {}
                view.perform_update(serializer)
                prop.refresh_from_db()
                self.assertEqual(prop.name, "New")
                self.assertEqual(prop.description, "concurrent")
                self.assertEqual(prop.content_revision, 2)

    # -- create affordance ---------------------------------------------------

    def test_model_creation_policy_matches_capabilities(self):
        request = SimpleNamespace(user=self.owner)
        self.assertTrue(model_creation_policy({"request": request}, Property).allowed)
        self.assertFalse(
            model_creation_policy(
                {"request": SimpleNamespace(user=self.staff)}, Property
            ).allowed
        )
        self.assertFalse(
            model_creation_policy(
                {"request": SimpleNamespace(user=None)}, Property
            ).allowed
        )


@override_settings(
    ROOT_URLCONF="utils.object_management.tests.test_shared_adapter_http"
)
class SharedAdapterHardeningTests(TestCase):
    """Rework-batch regressions: fresh references, fresh actor, governed
    non-UCO owned models, revocation, and unknown mutations."""

    @classmethod
    def setUpTestData(cls):
        call_command("sync_roles", "--apply", stdout=io.StringIO())

    def setUp(self):
        self.registered = Group.objects.get(name="registered")
        self.owner = User.objects.create_user(username="h-owner")
        self.admin = User.objects.create_user(username="h-admin")
        self.stranger = User.objects.create_user(username="h-stranger")
        for u in (self.owner, self.stranger):
            u.groups.add(self.registered)
        self.admin.groups.add(Group.objects.get(name="administrators"))
        self.prop = Property.objects.create(
            name="P", owner=self.owner, publication_status="private"
        )
        self.own_unit = Unit.objects.create(name="kg", symbol="kg", owner=self.owner)
        self.region = Region.objects.create(
            name="R",
            country="DE",
            owner=self.owner,
            publication_status="published",
            borders=GeoPolygon.objects.create(
                geom=MultiPolygon(Polygon(((0, 0), (0, 1), (1, 1), (1, 0), (0, 0))))
            ),
        )
        self.dataset = GeoDataset.objects.create(
            name="DS",
            owner=self.owner,
            publication_status="private",
            region=self.region,
        )
        self.own_material = Material.objects.create(
            name="mat", owner=self.owner, publication_status="private"
        )

    def _detail(self, prefix, pk):
        return reverse(f"{prefix}-detail", kwargs={"pk": pk})

    # finding 1: stale reference hole --------------------------------------

    def test_reference_reloaded_after_owner_transfer_denies(self):
        for prefix in ADAPTERS:
            with self.subTest(adapter=prefix):
                unit = Unit.objects.create(
                    name=f"u-{prefix}", symbol="u", owner=self.owner
                )
                prop = Property.objects.create(
                    name="R", owner=self.owner, publication_status="private"
                )
                serializer = _PropertySerializer(
                    instance=prop,
                    data={"name": "New", "allowed_units": [unit.pk]},
                    partial=True,
                )
                self.assertTrue(serializer.is_valid(), serializer.errors)
                # transfer the unit to a stranger so owner loses read
                Unit.objects.filter(pk=unit.pk).update(owner=self.stranger)
                view_cls = (
                    _UCOPropertyViewSet
                    if prefix == "uco-property"
                    else _AutoPermPropertyViewSet
                )
                view = view_cls()
                view.request = SimpleNamespace(user=self.owner)
                view.kwargs = {}
                with self.assertRaises(PermissionDenied):
                    view.perform_update(serializer)
                prop.refresh_from_db()
                self.assertEqual(prop.name, "R")
                self.assertEqual(prop.content_revision, 1)
                self.assertEqual(prop.allowed_units.count(), 0)

    def test_deleted_reference_denies(self):
        for prefix in ADAPTERS:
            with self.subTest(adapter=prefix):
                unit = Unit.objects.create(
                    name=f"u2-{prefix}", symbol="u2", owner=self.owner
                )
                prop = Property.objects.create(
                    name="R2", owner=self.owner, publication_status="private"
                )
                serializer = _PropertySerializer(
                    instance=prop,
                    data={"allowed_units": [unit.pk]},
                    partial=True,
                )
                self.assertTrue(serializer.is_valid(), serializer.errors)
                Unit.objects.filter(pk=unit.pk).delete()
                view_cls = (
                    _UCOPropertyViewSet
                    if prefix == "uco-property"
                    else _AutoPermPropertyViewSet
                )
                view = view_cls()
                view.request = SimpleNamespace(user=self.owner)
                view.kwargs = {}
                with self.assertRaises(PermissionDenied):
                    view.perform_update(serializer)

    # finding 2: fresh actor at the write boundary --------------------------

    def test_create_rechecks_revoked_capability(self):
        """Prime has_perm on a stale user object, revoke via a fresh ORM
        instance, then create must still deny."""
        for cls in (_UCOPropertyViewSet, _AutoPermPropertyViewSet):
            with self.subTest(viewset=cls.__name__):
                self.owner.groups.add(self.registered)
                stale = User.objects.get(pk=self.owner.pk)
                # prime the permission cache on the stale instance
                self.assertTrue(stale.has_perm("properties.add_property"))
                User.objects.get(pk=self.owner.pk).groups.clear()
                serializer = _PropertySerializer(data={"name": "Forged"})
                self.assertTrue(serializer.is_valid(), serializer.errors)
                view = cls()
                view.request = SimpleNamespace(user=stale)
                view.kwargs = {}
                with self.assertRaises(PermissionDenied):
                    view.perform_create(serializer)
                self.assertFalse(Property.objects.filter(name="Forged").exists())
                self.owner.groups.add(self.registered)

    def test_permitted_root_create_succeeds(self):
        for cls in (_UCOPropertyViewSet, _AutoPermPropertyViewSet):
            with self.subTest(viewset=cls.__name__):
                serializer = _PropertySerializer(data={"name": "RootOK"})
                self.assertTrue(serializer.is_valid(), serializer.errors)
                view = cls()
                view.request = SimpleNamespace(user=self.owner)
                view.kwargs = {}
                view.perform_create(serializer)
                obj = Property.objects.get(name="RootOK")
                self.assertEqual(obj.owner, self.owner)
                self.assertEqual(
                    obj.publication_status,
                    UserCreatedObject.STATUS_PRIVATE,
                )
                obj.delete()

    # finding 3: registered non-UCO owned models are governed ----------------

    def test_owned_non_uco_create_update_delete_governed(self):
        for prefix in COLPOL_ADAPTERS:
            with self.subTest(adapter=prefix):
                self.client.force_login(self.admin)
                response = self.client.post(
                    reverse(f"{prefix}-list"),
                    {
                        "dataset": self.dataset.pk,
                        "column_name": "geom",
                        "display_label": "Geom",
                    },
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 201)
                col = GeoDatasetColumnPolicy.objects.get(
                    dataset=self.dataset, column_name="geom"
                )
                self.dataset.refresh_from_db()
                self.assertEqual(self.dataset.content_revision, 2)
                self.assertEqual(_events(self.dataset, "edited").count(), 1)
                # update
                response = self.client.patch(
                    self._detail(prefix, col.pk),
                    {"display_label": "Geom2"},
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 200)
                col.refresh_from_db()
                self.assertEqual(col.display_label, "Geom2")
                self.dataset.refresh_from_db()
                self.assertEqual(self.dataset.content_revision, 3)
                self.assertEqual(_events(self.dataset, "edited").count(), 2)
                # delete
                response = self.client.delete(self._detail(prefix, col.pk))
                self.assertEqual(response.status_code, 204)
                self.assertFalse(
                    GeoDatasetColumnPolicy.objects.filter(pk=col.pk).exists()
                )
                self.dataset.refresh_from_db()
                self.assertEqual(self.dataset.content_revision, 4)
                self.assertEqual(_events(self.dataset, "edited").count(), 3)
                # reset
                self.dataset.content_revision = 1
                self.dataset.save(update_fields=["content_revision"])
                _events(self.dataset).delete()

    def test_owned_non_uco_denied_on_frozen_parent(self):
        for status in ("published", "archived"):
            ds = GeoDataset.objects.create(
                name="F",
                owner=self.owner,
                publication_status=status,
                region=self.region,
            )
            for prefix in COLPOL_ADAPTERS:
                with self.subTest(adapter=prefix, status=status):
                    self.client.force_login(self.admin)
                    response = self.client.post(
                        reverse(f"{prefix}-list"),
                        {"dataset": ds.pk, "column_name": "g"},
                        content_type="application/json",
                    )
                    self.assertIn(response.status_code, (400, 403, 404))
                    self.assertFalse(
                        GeoDatasetColumnPolicy.objects.filter(dataset=ds).exists()
                    )
                    self.assertFalse(_events(ds).exists())

    # finding 4: FK references, revocation, unknown mutation -----------------

    def test_fk_reference_access(self):
        foreign = Material.objects.create(
            name="fm", owner=self.stranger, publication_status="private"
        )
        published = Material.objects.create(
            name="pm", owner=self.stranger, publication_status="published"
        )
        for prefix in SERIES_ADAPTERS:
            with self.subTest(adapter=prefix, target="foreign"):
                self.client.force_login(self.owner)
                response = self.client.post(
                    reverse(f"{prefix}-list"),
                    {"name": "S", "material": foreign.pk},
                    content_type="application/json",
                )
                self.assertIn(response.status_code, (400, 403))
                self.assertFalse(SampleSeries.objects.filter(name="S").exists())
            with self.subTest(adapter=prefix, target="owned"):
                response = self.client.post(
                    reverse(f"{prefix}-list"),
                    {"name": "S2", "material": self.own_material.pk},
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 201)
                SampleSeries.objects.filter(name="S2").delete()
            with self.subTest(adapter=prefix, target="published"):
                response = self.client.post(
                    reverse(f"{prefix}-list"),
                    {"name": "S3", "material": published.pk},
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 201)
                SampleSeries.objects.filter(name="S3").delete()

    def test_group_membership_revocation_and_overlap(self):
        editors = Group.objects.create(name="s-editors")
        member = User.objects.create_user(username="gmember")
        member.groups.add(self.registered, editors)
        ct = ContentType.objects.get_for_model(Property)
        ObjectGroupEditorGrant.objects.create(
            content_type=ct, object_id=self.prop.pk, group=editors
        )
        ObjectEditorGrant.objects.create(
            content_type=ct, object_id=self.prop.pk, editor=member
        )
        for prefix in ADAPTERS:
            with self.subTest(adapter=prefix):
                # both routes -> allowed
                r = self._patch(prefix, member, {"name": "V1"})
                self.assertEqual(r.status_code, 200)
                # revoke direct grant -> group route still allows
                ObjectEditorGrant.objects.filter(
                    object_id=self.prop.pk, editor=member
                ).delete()
                r = self._patch(prefix, member, {"name": "V2"})
                self.assertEqual(r.status_code, 200)
                # revoke membership -> denied
                member.groups.remove(editors)
                r = self._patch(prefix, member, {"name": "V3"})
                self.assertIn(r.status_code, (403, 404))
                self.prop.refresh_from_db()
                self.assertEqual(self.prop.name, "V2")
                member.groups.add(editors)
                ObjectEditorGrant.objects.create(
                    content_type=ct, object_id=self.prop.pk, editor=member
                )

    def _patch(self, prefix, user, data):
        self.client.force_login(user)
        return self.client.patch(
            self._detail(prefix, self.prop.pk),
            data,
            content_type="application/json",
        )

    def test_unknown_custom_action_denied(self):
        for prefix in SERIES_ADAPTERS:
            with self.subTest(adapter=prefix):
                series = SampleSeries.objects.create(
                    name="SS",
                    owner=self.owner,
                    publication_status="private",
                    material=self.own_material,
                )
                self.client.force_login(self.owner)
                response = self.client.post(
                    reverse(f"{prefix}-frobnicate", kwargs={"pk": series.pk})
                )
                self.assertIn(response.status_code, (403, 404))

    # finding 5: inactive user must not hit cached positive -----------------

    def test_is_moderator_for_any_model_inactive_denied(self):
        from ..templatetags.moderation_tags import is_moderator_for_any_model

        moderator = User.objects.create_user(username="mod2")
        moderator.user_permissions.add(
            Permission.objects.get(codename="can_moderate_property")
        )
        self.assertTrue(is_moderator_for_any_model(moderator))  # prime cache
        User.objects.filter(pk=moderator.pk).update(is_active=False)
        moderator.refresh_from_db()
        self.assertFalse(is_moderator_for_any_model(moderator))


@override_settings(
    ROOT_URLCONF="utils.object_management.tests.test_shared_adapter_http"
)
class AdministratorManagedChildrenTests(TestCase):
    """Core policy parity for ADMINISTRATOR_MANAGED_CHILDREN."""

    @classmethod
    def setUpTestData(cls):
        call_command("sync_roles", "--apply", stdout=io.StringIO())

    def setUp(self):
        self.registered = Group.objects.get(name="registered")
        self.owner = User.objects.create_user(username="am-owner")
        self.owner.groups.add(self.registered)
        self.admin = User.objects.create_user(username="am-admin")
        self.admin.groups.add(Group.objects.get(name="administrators"))
        self.stranger = User.objects.create_user(username="am-stranger")
        self.stranger.groups.add(self.registered)
        self.region = Region.objects.create(
            name="AMR",
            country="DE",
            owner=self.owner,
            publication_status="published",
            borders=GeoPolygon.objects.create(
                geom=MultiPolygon(Polygon(((0, 0), (0, 1), (1, 1), (1, 0), (0, 0))))
            ),
        )
        self.dataset = GeoDataset.objects.create(
            name="DS",
            owner=self.owner,
            publication_status="private",
            region=self.region,
        )

    def test_admin_managed_child_create_requires_admin(self):
        for model in (
            GeoDatasetColumnPolicy,
            GeoDatasetRuntimeConfiguration,
        ):
            with self.subTest(model=model._meta.label_lower):
                self.assertFalse(
                    decide(self.owner, "create", model, parent=self.dataset).allowed
                )
                self.assertTrue(
                    decide(self.admin, "create", model, parent=self.dataset).allowed
                )

    def test_admin_managed_child_edit_delete_require_admin(self):
        row = GeoDatasetColumnPolicy.objects.create(
            dataset=self.dataset, column_name="geom"
        )
        self.assertFalse(decide(self.owner, "edit", row).allowed)
        self.assertFalse(decide(self.owner, "delete", row).allowed)
        self.assertTrue(decide(self.admin, "edit", row).allowed)
        self.assertTrue(decide(self.admin, "delete", row).allowed)

    def test_admin_managed_child_reassign_requires_admin(self):
        other = GeoDataset.objects.create(
            name="DS2",
            owner=self.owner,
            publication_status="private",
            region=self.region,
        )
        row = GeoDatasetColumnPolicy.objects.create(
            dataset=self.dataset, column_name="geom"
        )
        self.assertFalse(decide_reassign(self.owner, row, other).allowed)
        self.assertTrue(decide_reassign(self.admin, row, other).allowed)

    def test_admin_managed_child_editable_queryset_parity(self):
        row = GeoDatasetColumnPolicy.objects.create(
            dataset=self.dataset, column_name="geom"
        )
        self.assertFalse(
            editable_queryset(self.owner, GeoDatasetColumnPolicy.objects.all()).exists()
        )
        self.assertIn(
            row,
            editable_queryset(self.admin, GeoDatasetColumnPolicy.objects.all()),
        )

    def test_ordinary_owned_child_still_parent_governed(self):
        """Unlisted owned children keep parent-edit authorization."""
        source = Source.objects.create(
            title="S", owner=self.owner, publication_status="private"
        )
        author = Author.objects.create(last_names="Doe", owner=self.owner)
        self.assertTrue(
            decide(self.owner, "create", SourceAuthor, parent=source).allowed
        )
        link = SourceAuthor.objects.create(source=source, author=author, position=1)
        self.assertTrue(decide(self.owner, "edit", link).allowed)
        self.assertIn(link, editable_queryset(self.owner, SourceAuthor.objects.all()))
        self.assertFalse(
            decide(self.stranger, "create", SourceAuthor, parent=source).allowed
        )
        self.assertFalse(
            editable_queryset(self.stranger, SourceAuthor.objects.all()).exists()
        )


class _ACPVSerializer(serializers.ModelSerializer):
    class Meta:
        model = AggregatedCollectionPropertyValue
        fields = ("name", "collections", "property", "unit", "year", "average")


class _UCOACPVViewSet(UserCreatedObjectViewSet):
    queryset = AggregatedCollectionPropertyValue.objects.all()
    serializer_class = _ACPVSerializer


class _AutoPermACPVViewSet(AutoPermModelViewSet):
    queryset = AggregatedCollectionPropertyValue.objects.all()
    serializer_class = _ACPVSerializer


class _GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ("name",)


class _WritablePropertySerializer(serializers.ModelSerializer):
    """Deliberately writable server-controlled fields to prove the shared
    boundary strips them rather than honoring forged payload values."""

    owner = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False
    )
    approved_by = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Property
        fields = (
            "name",
            "owner",
            "publication_status",
            "content_revision",
            "submitted_at",
            "approved_at",
            "approved_by",
        )


class _UCOWritablePropertyViewSet(UserCreatedObjectViewSet):
    queryset = Property.objects.all()
    serializer_class = _WritablePropertySerializer


class _AutoPermWritablePropertyViewSet(AutoPermModelViewSet):
    queryset = Property.objects.all()
    serializer_class = _WritablePropertySerializer


class _AutoPermGroupViewSet(AutoPermModelViewSet):
    queryset = Group.objects.all()
    serializer_class = _GroupSerializer


class _ColumnPolicyModalDeleteView(UserCreatedObjectModalDeleteView):
    model = GeoDatasetColumnPolicy
    queryset = GeoDatasetColumnPolicy.objects.all()
    fields = ("dataset", "column_name", "display_label")
    success_url = "/done/"


def _acpv_urls():
    router = DefaultRouter()
    router.register("uco-acpv", _UCOACPVViewSet, basename="uco-acpv")
    router.register("autoperm-acpv", _AutoPermACPVViewSet, basename="autoperm-acpv")
    router.register("autoperm-group", _AutoPermGroupViewSet, basename="autoperm-group")
    router.register("uco-wprop", _UCOWritablePropertyViewSet, basename="uco-wprop")
    router.register(
        "autoperm-wprop", _AutoPermWritablePropertyViewSet, basename="autoperm-wprop"
    )
    return [
        path(
            "colpol/<int:pk>/modal-delete/",
            _ColumnPolicyModalDeleteView.as_view(),
            name="colpol-modal-delete",
        ),
        *router.urls,
    ]


urlpatterns += _acpv_urls()

# named routes resolved by the foreignkey template's create affordance
# and the review/detail URLs resolved by detail_or_review_url
urlpatterns += [
    path("unit-create-modal/", lambda r: None, name="unit-create-modal"),
    path("property/<int:pk>/", lambda r: None, name="property-detail"),
    path(
        "om/",
        include(
            ("utils.object_management.urls", "object_management"),
            namespace="object_management",
        ),
    ),
    path("unit-options/", lambda r: None, name="unit-options"),
]


ACPV_ADAPTERS = ("uco-acpv", "autoperm-acpv")


@override_settings(
    ROOT_URLCONF="utils.object_management.tests.test_shared_adapter_http"
)
class AuthorizeCreateBoundaryTests(TestCase):
    """Plural/exotic parent contexts and bound HTML create coverage."""

    @classmethod
    def setUpTestData(cls):
        call_command("sync_roles", "--apply", stdout=io.StringIO())

    def setUp(self):
        self.registered = Group.objects.get(name="registered")
        self.owner = User.objects.create_user(username="ac-owner")
        self.owner.groups.add(self.registered)
        self.stranger = User.objects.create_user(username="ac-stranger")
        self.stranger.groups.add(self.registered)
        self.prop = Property.objects.create(
            name="p", owner=self.owner, publication_status="private"
        )
        self.unit = Unit.objects.create(name="kg", symbol="kg", owner=self.owner)
        self.c1 = Collection.objects.create(
            name="C1", owner=self.owner, publication_status="published"
        )
        self.c2 = Collection.objects.create(
            name="C2", owner=self.stranger, publication_status="published"
        )
        self.foreign_private = Collection.objects.create(
            name="CP", owner=self.stranger, publication_status="private"
        )

    def _payload(self, collections):
        return {
            "name": "ACPV",
            "collections": [c.pk for c in collections],
            "property": self.prop.pk,
            "unit": self.unit.pk,
            "year": 2024,
            "average": 10.0,
        }

    def test_plural_parent_create_both_bases(self):
        for prefix in ACPV_ADAPTERS:
            with self.subTest(adapter=prefix):
                c1_rev, c2_rev = (
                    self.c1.content_revision,
                    self.c2.content_revision,
                )
                self.client.force_login(self.owner)
                response = self.client.post(
                    reverse(f"{prefix}-list"),
                    self._payload([self.c1, self.c2]),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 201)
                row = AggregatedCollectionPropertyValue.objects.get(name="ACPV")
                self.assertEqual(row.owner, self.owner)
                self.assertEqual(row.publication_status, "private")
                self.assertEqual(_events(row, "created").count(), 1)
                self.c1.refresh_from_db()
                self.c2.refresh_from_db()
                self.assertEqual(self.c1.content_revision, c1_rev)
                self.assertEqual(self.c2.content_revision, c2_rev)
                row.delete()
                _events(row).delete()

    def test_plural_parent_denied_contexts(self):
        deleted = Collection.objects.create(
            name="Gone", owner=self.owner, publication_status="published"
        )
        deleted_pk = deleted.pk
        deleted.delete()
        # deleted/empty are rejected by serializer validation (400);
        # readable-but-private contexts are denied by the policy layer (403)
        cases = {
            "foreign_private": ([self.foreign_private], 403),
            "mixed": ([self.c1, self.foreign_private], 403),
            "deleted": ([Collection(pk=deleted_pk)], 400),
            "empty": ([], 400),
        }
        for prefix in ACPV_ADAPTERS:
            for label, (collections, expected) in cases.items():
                with self.subTest(adapter=prefix, case=label):
                    self.client.force_login(self.owner)
                    response = self.client.post(
                        reverse(f"{prefix}-list"),
                        self._payload(collections),
                        content_type="application/json",
                    )
                    self.assertEqual(response.status_code, expected)
                    self.assertFalse(
                        AggregatedCollectionPropertyValue.objects.filter(
                            name="ACPV"
                        ).exists()
                    )
                    self.assertFalse(ReviewAction.objects.exists())

    def test_unsaved_parent_denied_direct(self):
        from utils.object_management.services import authorize_create

        unsaved = Collection(name="unsaved", owner=self.owner)
        with self.assertRaises(PermissionDenied):
            authorize_create(
                self.owner,
                AggregatedCollectionPropertyValue,
                parent=[unsaved],
            )

    def test_wrong_parent_type_denied_direct(self):
        from utils.object_management.services import authorize_create

        with self.assertRaises(PermissionDenied):
            authorize_create(
                self.owner,
                AggregatedCollectionPropertyValue,
                parent=[self.prop],
            )

    def _bound_view(self, model, parent=None, form_valid=None):
        """Fake view exposing the real mixin create helpers."""
        from utils.object_management.registry import model_policy
        from utils.object_management.views import CreateUserObjectMixin

        request = RequestFactory().post("/")
        request.user = self.owner
        view = SimpleNamespace(request=request)
        view.get_policy_model = lambda: model
        view._resolve_create_parent = lambda form: (model_policy(model), parent)
        view._enforce_policy_create = lambda form, parent=parent: (
            CreateUserObjectMixin._enforce_policy_create(view, form, parent=parent)
        )
        view._call_super_form_valid = form_valid or (lambda form: form.save())
        return view

    def test_bound_form_plural_parent_create(self):
        """HTML bound-create path accepts plural declared parents."""
        ACPVForm = modelform_factory(
            AggregatedCollectionPropertyValue,
            fields=(
                "name",
                "collections",
                "property",
                "unit",
                "year",
                "average",
            ),
        )
        form = ACPVForm(
            data={
                "name": "ACPV-HTML",
                "collections": [self.c1.pk, self.c2.pk],
                "property": self.prop.pk,
                "unit": self.unit.pk,
                "year": 2024,
                "average": 10.0,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        view = self._bound_view(
            AggregatedCollectionPropertyValue, parent=[self.c1, self.c2]
        )
        c1_rev = self.c1.content_revision
        response = _perform_bound_create(view, form)
        self.assertIsNotNone(response)
        row = AggregatedCollectionPropertyValue.objects.get(name="ACPV-HTML")
        self.assertEqual(_events(row, "created").count(), 1)
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.content_revision, c1_rev)

    def test_bound_form_denied_parent_context(self):
        ACPVForm = modelform_factory(
            AggregatedCollectionPropertyValue,
            fields=("name", "collections", "property", "unit", "year", "average"),
        )
        form = ACPVForm(
            data={
                "name": "ACPV-BAD",
                "collections": [self.c1.pk, self.foreign_private.pk],
                "property": self.prop.pk,
                "unit": self.unit.pk,
                "year": 2024,
                "average": 10.0,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        view = self._bound_view(
            AggregatedCollectionPropertyValue,
            parent=[self.c1, self.foreign_private],
        )
        with self.assertRaises(PermissionDenied):
            _perform_bound_create(view, form)
        self.assertFalse(
            AggregatedCollectionPropertyValue.objects.filter(name="ACPV-BAD").exists()
        )
        self.assertFalse(ReviewAction.objects.exists())

    @isolate_apps("utils.object_management")
    def test_bound_form_unknown_uco_denied(self):
        """Unregistered UCO models must not slip through the HTML path."""

        class _UnregisteredUCO(UserCreatedObject):
            class Meta:
                app_label = "object_management"

        view = self._bound_view(_UnregisteredUCO)
        with self.assertRaises(PermissionDenied):
            view._enforce_policy_create(None)


@override_settings(
    ROOT_URLCONF="utils.object_management.tests.test_shared_adapter_http"
)
class StaleActorAndModalDeleteTests(TestCase):
    """Fresh-actor checks inside write boundaries; governed modal deletes."""

    @classmethod
    def setUpTestData(cls):
        call_command("sync_roles", "--apply", stdout=io.StringIO())

    def setUp(self):
        self.registered = Group.objects.get(name="registered")
        self.owner = User.objects.create_user(username="sa-owner")
        self.owner.groups.add(self.registered)
        self.admin = User.objects.create_user(username="sa-admin")
        self.admin.groups.add(Group.objects.get(name="administrators"))
        self.stranger = User.objects.create_user(username="sa-stranger")
        self.stranger.groups.add(self.registered)
        self.prop = Property.objects.create(
            name="P", owner=self.owner, publication_status="private"
        )
        self.foreign_unit = Unit.objects.create(
            name="fu",
            symbol="f",
            owner=self.stranger,
            publication_status="private",
        )
        self.region = Region.objects.create(
            name="SR",
            country="DE",
            owner=self.owner,
            publication_status="published",
            borders=GeoPolygon.objects.create(
                geom=MultiPolygon(Polygon(((0, 0), (0, 1), (1, 1), (1, 0), (0, 0))))
            ),
        )
        self.dataset = GeoDataset.objects.create(
            name="DS",
            owner=self.owner,
            publication_status="private",
            region=self.region,
        )

    def test_update_reference_check_uses_fresh_actor(self):
        """Actor privileges revoked after request binding must not authorize
        the referenced-object read check inside the update boundary."""
        # dual-hat persona: owner keeps registered capability; admin is what
        # made the foreign private unit readable during validation.
        self.owner.groups.add(Group.objects.get(name="administrators"))
        for cls in (_UCOPropertyViewSet, _AutoPermPropertyViewSet):
            with self.subTest(viewset=cls.__name__):
                stale = User.objects.get(pk=self.owner.pk)
                self.assertTrue(stale.has_perm("object_management.administer_objects"))
                prop = Property.objects.create(
                    name="S", owner=self.owner, publication_status="private"
                )
                serializer = _PropertySerializer(
                    instance=prop,
                    data={"name": "New", "allowed_units": [self.foreign_unit.pk]},
                    partial=True,
                )
                self.assertTrue(serializer.is_valid(), serializer.errors)
                # revoke ONLY the administrator grant via a fresh ORM row
                fresh = User.objects.get(pk=self.owner.pk)
                fresh.groups.remove(Group.objects.get(name="administrators"))
                view = cls()
                view.request = SimpleNamespace(user=stale)
                view.kwargs = {}
                with self.assertRaises(PermissionDenied):
                    view.perform_update(serializer)
                prop.refresh_from_db()
                self.assertEqual(prop.name, "S")
                self.assertEqual(prop.content_revision, 1)
                self.assertEqual(prop.allowed_units.count(), 0)
                self.assertFalse(_events(prop).exists())
                # restore admin grant for next iteration
                self.owner.groups.add(Group.objects.get(name="administrators"))

    def test_bound_update_revalidates_with_fresh_actor(self):
        """The locked bound-form revalidation must see the fresh actor."""
        from utils.forms import UserCreatedObjectFormMixin

        class PropForm(UserCreatedObjectFormMixin, forms.ModelForm):
            class Meta:
                model = Property
                fields = ("name", "allowed_units")

        PropForm.__module__ = __name__
        self.owner.groups.add(Group.objects.get(name="administrators"))
        request = RequestFactory().post("/")
        request.user = self.owner
        form = PropForm(
            data={
                "name": "Bound",
                "allowed_units": [self.foreign_unit.pk],
            },
            instance=self.prop,
        )
        form.request = request
        self.assertTrue(form.is_valid(), form.errors)
        # revoke administrator status via a second ORM instance
        User.objects.get(pk=self.owner.pk).groups.remove(
            Group.objects.get(name="administrators")
        )
        view = SimpleNamespace(
            request=request,
            object=self.prop,
            _call_super_form_valid=lambda f: f.save(),
            form_invalid=lambda f: "INVALID",
        )
        _perform_bound_update(view, form)
        # denied or form-invalid — but never persisted
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.name, "P")
        self.assertEqual(self.prop.allowed_units.count(), 0)
        self.assertEqual(self.prop.content_revision, 1)

    def test_modal_delete_governs_registered_non_uco(self):
        col = GeoDatasetColumnPolicy.objects.create(
            dataset=self.dataset, column_name="geom"
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("colpol-modal-delete", kwargs={"pk": col.pk})
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(GeoDatasetColumnPolicy.objects.filter(pk=col.pk).exists())
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.content_revision, 2)
        self.assertEqual(_events(self.dataset, "edited").count(), 1)

    def test_modal_delete_denies_non_admin_and_frozen(self):
        for persona, status in (
            ("owner", "private"),
            ("admin", "published"),
        ):
            with self.subTest(persona=persona, status=status):
                ds = GeoDataset.objects.create(
                    name=f"DS-{status}",
                    owner=self.owner,
                    publication_status=status,
                    region=self.region,
                )
                col = GeoDatasetColumnPolicy.objects.create(dataset=ds, column_name="g")
                rev = ds.content_revision
                user = self.owner if persona == "owner" else self.admin
                self.client.force_login(user)
                response = self.client.post(
                    reverse("colpol-modal-delete", kwargs={"pk": col.pk})
                )
                self.assertEqual(response.status_code, 403)
                self.assertTrue(
                    GeoDatasetColumnPolicy.objects.filter(pk=col.pk).exists()
                )
                ds.refresh_from_db()
                self.assertEqual(ds.content_revision, rev)
                self.assertFalse(_events(ds).exists())


@override_settings(
    ROOT_URLCONF="utils.object_management.tests.test_shared_adapter_http"
)
class BoundCreateFreshReferencesTests(TestCase):
    """HTML bound-create must revalidate references and the declared parent."""

    @classmethod
    def setUpTestData(cls):
        call_command("sync_roles", "--apply", stdout=io.StringIO())

    def setUp(self):
        self.registered = Group.objects.get(name="registered")
        self.owner = User.objects.create_user(username="bc-owner")
        self.owner.groups.add(self.registered)
        self.admin_group = Group.objects.get(name="administrators")
        self.stranger = User.objects.create_user(username="bc-stranger")
        self.stranger.groups.add(self.registered)
        self.foreign_unit = Unit.objects.create(
            name="fu",
            symbol="f",
            owner=self.stranger,
            publication_status="private",
        )
        self.region = Region.objects.create(
            name="BR",
            country="DE",
            owner=self.owner,
            publication_status="published",
            borders=GeoPolygon.objects.create(
                geom=MultiPolygon(Polygon(((0, 0), (0, 1), (1, 1), (1, 0), (0, 0))))
            ),
        )
        self.dataset_a = GeoDataset.objects.create(
            name="A",
            owner=self.owner,
            publication_status="private",
            region=self.region,
        )
        self.dataset_b = GeoDataset.objects.create(
            name="B",
            owner=self.stranger,
            publication_status="published",
            region=self.region,
        )

    def _prop_form(self):
        from utils.forms import UserCreatedObjectFormMixin

        class PropForm(UserCreatedObjectFormMixin, forms.ModelForm):
            class Meta:
                model = Property
                fields = ("name", "allowed_units")

        PropForm.__module__ = __name__
        return PropForm

    def _bound_create_view(self, model, parent=None):
        from utils.object_management.registry import model_policy
        from utils.object_management.views import CreateUserObjectMixin

        request = RequestFactory().post("/")
        request.user = self.owner
        view = SimpleNamespace(request=request)
        view.get_policy_model = lambda: model
        view._resolve_create_parent = lambda form: (model_policy(model), parent)
        view._enforce_policy_create = lambda form, parent=parent: (
            CreateUserObjectMixin._enforce_policy_create(view, form, parent=parent)
        )
        view._call_super_form_valid = lambda form: form.save()
        return view

    def test_bound_create_revoked_admin_reference_denied(self):
        self.owner.groups.add(self.admin_group)
        PropForm = self._prop_form()
        form = PropForm(
            data={
                "name": "BoundCreate",
                "allowed_units": [self.foreign_unit.pk],
            },
            request=RequestFactory().post("/"),
        )
        form.request.user = self.owner
        self.assertTrue(form.is_valid(), form.errors)
        # revoke ONLY administrator status; owner keeps registered add rights
        User.objects.get(pk=self.owner.pk).groups.remove(self.admin_group)
        view = self._bound_create_view(Property)
        with self.assertRaises(PermissionDenied):
            _perform_bound_create(view, form)
        self.assertFalse(Property.objects.filter(name="BoundCreate").exists())
        self.assertFalse(ReviewAction.objects.exists())

    def test_bound_create_transferred_reference_denied(self):
        PropForm = self._prop_form()
        unit = Unit.objects.create(name="owned", symbol="o", owner=self.owner)
        form = PropForm(
            data={"name": "Transfer", "allowed_units": [unit.pk]},
            request=RequestFactory().post("/"),
        )
        form.request.user = self.owner
        self.assertTrue(form.is_valid(), form.errors)
        # unit moves to a stranger between validation and persist
        Unit.objects.filter(pk=unit.pk).update(owner=self.stranger)
        view = self._bound_create_view(Property)
        with self.assertRaises(PermissionDenied):
            _perform_bound_create(view, form)
        self.assertFalse(Property.objects.filter(name="Transfer").exists())
        self.assertFalse(ReviewAction.objects.exists())

    def test_api_create_declared_parent_mismatch_denied(self):
        """URL-resolved parent A, payload parent B: the saved relation must
        equal the authorized context."""

        class _PinnedParentUCO(_UCOColumnPolicyViewSet):
            def get_policy_parent(self):
                return self._pinned

        class _PinnedParentAP(_AutoPermColumnPolicyViewSet):
            def get_policy_parent(self):
                return self._pinned

        admin = User.objects.create_user(username="pa")
        admin.groups.add(self.admin_group)
        for cls in (_PinnedParentUCO, _PinnedParentAP):
            with self.subTest(viewset=cls.__name__):
                # register the test viewset on the fly via a direct call
                col = f"x-{cls.__name__}"
                serializer = _ColumnPolicySerializer(
                    data={
                        "dataset": self.dataset_b.pk,
                        "column_name": col,
                    }
                )
                self.assertTrue(serializer.is_valid(), serializer.errors)
                view = cls()
                view._pinned = self.dataset_a
                view.request = SimpleNamespace(user=admin)
                view.kwargs = {}
                rev_a, rev_b = (
                    self.dataset_a.content_revision,
                    self.dataset_b.content_revision,
                )
                with self.assertRaises(PermissionDenied):
                    view.perform_create(serializer)
                self.assertFalse(
                    GeoDatasetColumnPolicy.objects.filter(column_name=col).exists()
                )
                self.dataset_a.refresh_from_db()
                self.dataset_b.refresh_from_db()
                self.assertEqual(self.dataset_a.content_revision, rev_a)
                self.assertEqual(self.dataset_b.content_revision, rev_b)

    def test_bound_create_declared_parent_mismatch_denied(self):
        ColPolForm = modelform_factory(
            GeoDatasetColumnPolicy,
            fields=("dataset", "column_name", "display_label"),
        )
        admin = User.objects.create_user(username="pb")
        admin.groups.add(self.admin_group)
        form = ColPolForm(
            data={
                "dataset": self.dataset_b.pk,
                "column_name": "y",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        request = RequestFactory().post("/")
        request.user = admin
        from utils.object_management.registry import model_policy
        from utils.object_management.views import CreateUserObjectMixin

        view = SimpleNamespace(request=request)
        view.get_policy_model = lambda: GeoDatasetColumnPolicy
        view._resolve_create_parent = lambda form: (
            model_policy(GeoDatasetColumnPolicy),
            self.dataset_a,
        )
        view._enforce_policy_create = lambda form, parent=self.dataset_a: (
            CreateUserObjectMixin._enforce_policy_create(view, form, parent=parent)
        )
        view._call_super_form_valid = lambda form: form.save()
        rev_a, rev_b = (
            self.dataset_a.content_revision,
            self.dataset_b.content_revision,
        )
        with self.assertRaises(PermissionDenied):
            _perform_bound_create(view, form)
        self.assertFalse(
            GeoDatasetColumnPolicy.objects.filter(column_name="y").exists()
        )
        self.dataset_a.refresh_from_db()
        self.dataset_b.refresh_from_db()
        self.assertEqual(self.dataset_a.content_revision, rev_a)
        self.assertEqual(self.dataset_b.content_revision, rev_b)

    def test_wrong_scalar_parent_denied(self):
        from utils.object_management.services import authorize_create

        with self.assertRaises(PermissionDenied):
            authorize_create(
                self.owner,
                AggregatedCollectionPropertyValue,
                parent="not-a-model",
            )


@override_settings(
    ROOT_URLCONF="utils.object_management.tests.test_shared_adapter_http"
)
class ForeignKeyCreateAffordanceRenderTests(TestCase):
    """The actual foreignkey template must render the create affordance only
    when the shared policy allows creation of the referenced model."""

    @classmethod
    def setUpTestData(cls):
        call_command("sync_roles", "--apply", stdout=io.StringIO())

    def _render(self, user):
        from django.template.loader import render_to_string

        from utils.forms import UserCreatedObjectFormMixin

        class PropForm(UserCreatedObjectFormMixin, forms.ModelForm):
            class Meta:
                model = Property
                fields = ("name", "allowed_units")

        request = RequestFactory().get("/")
        request.user = user
        form = PropForm(request=request)
        return render_to_string(
            "fields/foreignkey_field.html",
            {"field": form["allowed_units"], "request": request},
            request=request,
        )

    def test_contributor_sees_create_affordance(self):
        contributor = User.objects.create_user(username="fk-contributor")
        contributor.groups.add(Group.objects.get(name="registered"))
        html = self._render(contributor)
        self.assertIn("modal-fk-create", html)

    def test_staff_only_does_not_see_create_affordance(self):
        staff = User.objects.create_user(username="fk-staff", is_staff=True)
        staff.groups.clear()  # staff flag alone must not add capabilities
        html = self._render(staff)
        self.assertNotIn("modal-fk-create", html)


@override_settings(
    ROOT_URLCONF="utils.object_management.tests.test_shared_adapter_http"
)
class UnregisteredPlainModelCreateTests(TestCase):
    """Unregistered non-UCO models keep the plain adapter path: capability
    via the model's own add permission, no policy boundary involved."""

    @classmethod
    def setUpTestData(cls):
        call_command("sync_roles", "--apply", stdout=io.StringIO())

    def test_authorized_plain_create_persists(self):
        user = User.objects.create_user(username="plain-creator")
        user.groups.clear()
        user.user_permissions.add(Permission.objects.get(codename="add_group"))
        self.client.force_login(user)
        response = self.client.post(
            reverse("autoperm-group-list"),
            {"name": "plain-created"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Group.objects.filter(name="plain-created").exists())
        self.assertFalse(ReviewAction.objects.exists())

    def test_missing_add_capability_denied(self):
        user = User.objects.create_user(username="plain-denied")
        user.groups.clear()
        self.client.force_login(user)
        response = self.client.post(
            reverse("autoperm-group-list"),
            {"name": "plain-denied"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Group.objects.filter(name="plain-denied").exists())

    def test_inactive_user_denied(self):
        user = User.objects.create_user(username="plain-inactive", is_active=False)
        user.user_permissions.add(Permission.objects.get(codename="add_group"))
        self.client.force_login(user)
        response = self.client.post(
            reverse("autoperm-group-list"),
            {"name": "plain-inactive"},
            content_type="application/json",
        )
        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(Group.objects.filter(name="plain-inactive").exists())


@override_settings(
    ROOT_URLCONF="utils.object_management.tests.test_shared_adapter_http"
)
class ServerControlledCreateFieldsTests(TestCase):
    """Forged server-controlled fields must be stripped at the boundary:
    the row persists with server-injected owner/status/revision."""

    @classmethod
    def setUpTestData(cls):
        call_command("sync_roles", "--apply", stdout=io.StringIO())

    def setUp(self):
        self.registered = Group.objects.get(name="registered")
        self.owner = User.objects.create_user(username="sc-owner")
        self.owner.groups.add(self.registered)
        self.stranger = User.objects.create_user(username="sc-stranger")

    def test_forged_server_fields_ignored(self):
        for prefix in ("uco-wprop", "autoperm-wprop"):
            with self.subTest(adapter=prefix):
                Property.objects.filter(name="Forged").delete()
                self.client.force_login(self.owner)
                response = self.client.post(
                    reverse(f"{prefix}-list"),
                    {
                        "name": "Forged",
                        "owner": self.stranger.pk,
                        "publication_status": "published",
                        "content_revision": 99,
                        "submitted_at": "2020-01-01T00:00:00Z",
                        "approved_at": "2020-01-01T00:00:00Z",
                        "approved_by": self.stranger.pk,
                    },
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 201)
                prop = Property.objects.get(name="Forged")
                self.assertEqual(prop.owner, self.owner)
                self.assertEqual(prop.publication_status, "private")
                self.assertEqual(prop.content_revision, 1)
                self.assertIsNone(prop.submitted_at)
                self.assertIsNone(prop.approved_at)
                self.assertIsNone(prop.approved_by_id)
                created_event = _events(prop, "created").get()
                self.assertEqual(created_event.content_revision, 1)


@override_settings(
    ROOT_URLCONF="utils.object_management.tests.test_shared_adapter_http"
)
class DetailOrReviewUrlTagTests(TestCase):
    """detail_or_review_url must follow the shared review-activity decision:
    declined owners/editors get the review URL only when they can act on it;
    inactive owners fall back to the plain object URL."""

    @classmethod
    def setUpTestData(cls):
        call_command("sync_roles", "--apply", stdout=io.StringIO())

    def setUp(self):
        self.registered = Group.objects.get(name="registered")
        self.owner = User.objects.create_user(username="tag-owner")
        self.owner.groups.add(self.registered)
        self.editor = User.objects.create_user(username="tag-editor")
        self.editor.groups.add(self.registered)
        self.prop = Property.objects.create(
            name="TagProp", owner=self.owner, publication_status="declined"
        )

    def _resolve(self, user, obj):
        from ..templatetags.moderation_tags import detail_or_review_url

        request = RequestFactory().get("/items/")
        request.user = user
        return detail_or_review_url({"request": request}, obj)

    def test_active_declined_owner_gets_review_url(self):
        url = self._resolve(self.owner, self.prop)
        self.assertIn("review", url)
        self.assertIn(str(self.prop.pk), url)

    def test_inactive_declined_owner_keeps_plain_url(self):
        inactive = User.objects.create_user(username="tag-inactive", is_active=False)
        inactive.groups.add(self.registered)
        self.prop.owner = inactive
        self.prop.save()
        url = self._resolve(inactive, self.prop)
        self.assertNotIn("review", url)

    def test_active_editor_declined_gets_review_url(self):
        self.prop.add_editor(self.editor, granted_by=self.owner)
        url = self._resolve(self.editor, self.prop)
        self.assertIn("review", url)
        self.assertIn(str(self.prop.pk), url)


@override_settings(
    ROOT_URLCONF="utils.object_management.tests.test_shared_adapter_http"
)
class CreateAuthorizationInsideBoundaryTests(TestCase):
    """The authoritative create check must execute inside the atomic write
    boundary, not before it — a revoked capability can otherwise slip a row
    through between decision and save."""

    @classmethod
    def setUpTestData(cls):
        call_command("sync_roles", "--apply", stdout=io.StringIO())

    def setUp(self):
        self.registered = Group.objects.get(name="registered")
        self.owner = User.objects.create_user(username="ab-owner")
        self.owner.groups.add(self.registered)

    def test_authorize_create_runs_inside_atomic_block(self):
        from django.db import connection

        from utils.object_management import viewsets as om_viewsets

        for cls in (_UCOPropertyViewSet, _AutoPermPropertyViewSet):
            with self.subTest(viewset=cls.__name__):
                Property.objects.filter(name="Inside").delete()
                before = len(connection.atomic_blocks)
                state = {}
                real = om_viewsets.authorize_create

                def spy(
                    actor,
                    model,
                    *,
                    parent=None,
                    _real=real,
                    _state=state,
                    _conn=connection,
                ):
                    _state["depth"] = len(_conn.atomic_blocks)
                    return _real(actor, model, parent=parent)

                serializer = _PropertySerializer(data={"name": "Inside"})
                self.assertTrue(serializer.is_valid(), serializer.errors)
                view = cls()
                view.request = SimpleNamespace(user=self.owner)
                view.kwargs = {}
                with patch.object(om_viewsets, "authorize_create", side_effect=spy):
                    view.perform_create(serializer)
                prop = Property.objects.get(name="Inside")
                self.assertGreater(
                    state.get("depth", 0),
                    before,
                    "authorize_create executed outside the write boundary",
                )
                self.assertEqual(prop.publication_status, "private")
                self.assertEqual(prop.content_revision, 1)
                self.assertEqual(_events(prop, "created").count(), 1)
                prop.delete()
