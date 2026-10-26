from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.models import AnonymousUser, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate

from utils.properties.models import Property

from ..permissions import UserCreatedObjectPermission
from ..viewsets import GlobalObjectViewSet, UserCreatedObjectViewSet
from .models import TestGlobalObject


class BaseAPITestCase(TestCase):
    """Common DRF factory + user fixtures *and* a request builder helper."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        table_name = TestGlobalObject._meta.db_table
        if table_name not in connection.introspection.table_names():
            with connection.schema_editor() as schema_editor:
                schema_editor.create_model(TestGlobalObject)

    @classmethod
    def tearDownClass(cls):
        table_name = TestGlobalObject._meta.db_table
        if table_name in connection.introspection.table_names():
            with connection.schema_editor() as schema_editor:
                schema_editor.delete_model(TestGlobalObject)
        super().tearDownClass()

    #: mapping of http‑method → Factory function (populated in setUp).
    _VERB_MAP: dict[str, callable]

    @classmethod
    def setUpTestData(cls):
        cls.factory = APIRequestFactory()
        cls._VERB_MAP = {
            "get": cls.factory.get,
            "post": cls.factory.post,
            "put": cls.factory.put,
            "patch": cls.factory.patch,
            "delete": cls.factory.delete,
        }
        cls.staff_user = User.objects.create_user(username="staff", is_staff=True)
        cls.regular_user = User.objects.create_user(username="regular", is_staff=False)
        cls.anonymous_user = AnonymousUser()

    def _build_request(self, verb: str, path: str = "/", *, data: dict | None = None):
        """Return a raw *Django* `HttpRequest` for the given verb/path/data."""
        try:
            return self._VERB_MAP[verb.lower()](path, data or {})
        except KeyError as exc:  # pragma: no cover – catches typos early
            raise ValueError(f"Unsupported HTTP verb: {verb}") from exc


class GlobalObjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestGlobalObject
        fields = ["id", "name", "description"]


class UserObjectSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    name = serializers.CharField(required=False)
    owner = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False
    )
    publication_status = serializers.CharField(required=False)


class MockUserCreatedObject:  # minimal, deterministic pk
    objects = Mock()

    def __init__(self, **attrs):
        self.pk = attrs.pop("pk", 1)
        self.owner: User | None = attrs.pop("owner", None)
        self.publication_status: str = attrs.pop("publication_status", "private")
        for k, v in attrs.items():
            setattr(self, k, v)

    # realistic enough `_meta` for permission construction
    class _Meta:
        app_label = "test_app"
        model_name = "mockusercreatedobject"
        concrete_model = None

    _meta = _Meta()

    def register_for_review(self):
        if self.publication_status != "private":
            raise ValidationError("Only private objects can be registered for review")
        self.publication_status = "review"

    def withdraw_from_review(self):
        if self.publication_status != "review":
            raise ValidationError("Only objects in review can be withdrawn")
        self.publication_status = "private"

    def approve(self, user=None):
        if self.publication_status != "review":
            raise ValidationError("Only objects in review can be approved")
        self.publication_status = "published"

    def reject(self):
        if self.publication_status != "review":
            raise ValidationError("Only objects in review can be rejected")
        self.publication_status = "declined"

    def archive(self):
        if self.publication_status != "published":
            raise ValidationError("Only published objects can be archived")
        self.publication_status = "archived"


MockUserCreatedObject._meta.concrete_model = MockUserCreatedObject


class MockUserCreatedObjectViewSet(UserCreatedObjectViewSet):
    queryset = MockUserCreatedObject.objects.all()
    serializer_class = UserObjectSerializer
    permission_classes = [UserCreatedObjectPermission]


class GlobalObjectViewSetTests(BaseAPITestCase):
    """Read/write rules for *global* objects."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.example = TestGlobalObject.objects.create(
            name="Example", description="desc"
        )
        cls.admin_user = User.objects.create_user(username="gobj-admin")
        cls.admin_user.user_permissions.add(
            Permission.objects.get(codename="administer_objects")
        )

    # helper – centralised patch/dispatch logic
    def _response(
        self,
        verb: str,
        *,
        user: User | AnonymousUser | None = None,
        data: dict | None = None,
        pk: int | None = None,
    ):
        req = self._build_request(verb, "/fake-url/", data=data)
        req.user = user or AnonymousUser()

        with (
            patch.object(
                GlobalObjectViewSet,
                "get_queryset",
                return_value=TestGlobalObject.objects.all(),
            ),
            patch.object(
                GlobalObjectViewSet,
                "get_serializer_class",
                return_value=GlobalObjectSerializer,
            ),
        ):
            view = GlobalObjectViewSet.as_view(
                {
                    "get": "list",
                    "post": "create",
                    "put": "update",
                    "patch": "partial_update",
                    "delete": "destroy",
                }
            )
            return view(req, pk=pk) if pk else view(req)

    def test_unauthenticated_can_read(self):
        list_resp = self._response("get")
        detail_resp = self._response("get", pk=self.example.id)
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)

    def test_unauthenticated_cannot_write(self):
        for verb in ("post", "put", "patch", "delete"):
            with self.subTest(verb=verb):
                resp = self._response(verb, data={"name": "n"}, pk=self.example.id)
                self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_regular_user_cannot_write(self):
        for verb in ("post", "put", "patch", "delete"):
            with self.subTest(verb=verb):
                resp = self._response(
                    verb, user=self.regular_user, data={"name": "n"}, pk=self.example.id
                )
                self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_user_cannot_write(self):
        # Staff status alone is not an administrative capability.
        for verb in ("post", "put", "patch", "delete"):
            with self.subTest(verb=verb):
                resp = self._response(
                    verb,
                    user=self.staff_user,
                    data={"name": "n"},
                    pk=self.example.id,
                )
                self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_user_can_write(self):
        # create
        create = self._response(
            "post", user=self.admin_user, data={"name": "New", "description": "d"}
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        # update / partial-update / delete
        verbs = [
            ("put", {"name": "Updated", "description": "d"}),
            ("patch", {"description": "patched"}),
            ("delete", None),
        ]
        for verb, payload in verbs:
            resp = self._response(
                verb, user=self.admin_user, data=payload, pk=self.example.id
            )
            expected = (
                status.HTTP_204_NO_CONTENT if verb == "delete" else status.HTTP_200_OK
            )
            self.assertEqual(resp.status_code, expected)

    def test_duplicate_name_returns_400(self):
        self._response(
            "post", user=self.admin_user, data={"name": "Unique", "description": "d"}
        )
        dup = self._response(
            "post", user=self.admin_user, data={"name": "Unique", "description": "dup"}
        )
        self.assertEqual(dup.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", dup.data)

    def test_delete_unknown_pk_returns_404(self):
        resp = self._response("delete", user=self.admin_user, pk=9999)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class PropertyViewSet(UserCreatedObjectViewSet):
    queryset = Property.objects.all()
    serializer_class = UserObjectSerializer


def _grant(user, codename, model=Property):
    user.user_permissions.add(
        Permission.objects.get(
            codename=codename,
            content_type=ContentType.objects.get_for_model(model),
        )
    )


class UserCreatedObjectQueryTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.stranger = User.objects.create_user(username="stranger")
        self.moderator = User.objects.create_user(username="moderator")
        _grant(self.moderator, "can_moderate_property")
        self.admin = User.objects.create_user(username="policy-admin")
        self.admin.user_permissions.add(
            Permission.objects.get(codename="administer_objects")
        )
        self.seeded_published_pks = set(
            Property.objects.filter(publication_status="published").values_list(
                "pk", flat=True
            )
        )
        self.published = Property.objects.create(
            name="published",
            owner=self.stranger,
            publication_status="published",
        )
        self.own_private = Property.objects.create(
            name="own private",
            owner=self.regular_user,
            publication_status="private",
        )
        self.own_review = Property.objects.create(
            name="own review",
            owner=self.regular_user,
            publication_status="review",
        )
        self.other_private = Property.objects.create(
            name="other private",
            owner=self.stranger,
            publication_status="private",
        )
        self.other_review = Property.objects.create(
            name="other review",
            owner=self.stranger,
            publication_status="review",
        )
        self.view = PropertyViewSet

    def _get_qs(self, *, user: User | AnonymousUser, params: dict | None = None):
        params = params or {}
        req = self._build_request("get", "/objects/", data=params)
        if getattr(user, "is_authenticated", False):
            force_authenticate(req, user=user)
        view = PropertyViewSet()
        view.request = Request(req)
        return view.get_queryset()

    def _pks(self, qs):
        return set(qs.values_list("pk", flat=True))

    def test_regular_default_scope_is_all_readable(self):
        qs = self._get_qs(user=self.regular_user)
        self.assertEqual(
            self._pks(qs),
            {self.published.pk, self.own_private.pk, self.own_review.pk}
            | self.seeded_published_pks,
        )

    def test_regular_scope_private_is_own_workspace(self):
        qs = self._get_qs(user=self.regular_user, params={"scope": "private"})
        self.assertEqual(self._pks(qs), {self.own_private.pk, self.own_review.pk})

    def test_regular_scope_review(self):
        qs = self._get_qs(user=self.regular_user, params={"scope": "review"})
        self.assertEqual(self._pks(qs), {self.own_review.pk})

    def test_staff_without_role_is_an_ordinary_user(self):
        qs = self._get_qs(user=self.staff_user)
        self.assertEqual(self._pks(qs), {self.published.pk} | self.seeded_published_pks)

    def test_moderator_default_scope_includes_review_items(self):
        qs = self._get_qs(user=self.moderator)
        self.assertIn(self.other_review.pk, self._pks(qs))

    def test_moderator_scope_review_returns_all_review_objects(self):
        qs = self._get_qs(user=self.moderator, params={"scope": "review"})
        self.assertEqual(self._pks(qs), {self.own_review.pk, self.other_review.pk})

    def test_admin_default_scope_sees_everything(self):
        qs = self._get_qs(user=self.admin)
        self.assertEqual(
            self._pks(qs),
            {
                self.published.pk,
                self.own_private.pk,
                self.own_review.pk,
                self.other_private.pk,
                self.other_review.pk,
            }
            | self.seeded_published_pks,
        )

    def test_invalid_scope_returns_no_rows(self):
        for user in (self.regular_user, self.staff_user, self.admin):
            with self.subTest(user=user.username):
                qs = self._get_qs(user=user, params={"scope": "wat"})
                self.assertEqual(self._pks(qs), set())

    def test_anonymous_published_only(self):
        qs = self._get_qs(user=self.anonymous_user)
        self.assertEqual(self._pks(qs), {self.published.pk} | self.seeded_published_pks)

    def test_anonymous_private_scope_is_empty(self):
        qs = self._get_qs(user=self.anonymous_user, params={"scope": "private"})
        self.assertEqual(self._pks(qs), set())


class UserCreatedObjectCreationTests(BaseAPITestCase):
    def test_perform_create_sets_owner(self):
        self.regular_user.user_permissions.add(
            Permission.objects.get(codename="add_property")
        )
        serializer = Mock(save=Mock(return_value=MockUserCreatedObject()))
        serializer.Meta = SimpleNamespace(model=Property)
        viewset = MockUserCreatedObjectViewSet()
        req = self._build_request("post", "/objects/")
        force_authenticate(req, user=self.regular_user)
        viewset.request = Request(req)
        viewset.perform_create(serializer)
        serializer.save.assert_called_once_with(
            owner=self.regular_user, publication_status="private"
        )


class UserCreatedObjectWorkflowTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.moderator = User.objects.create_user(username="moderator")
        _grant(self.moderator, "can_moderate_property")
        self.other_user = User.objects.create_user(username="other")
        self.private_obj = Property.objects.create(
            name="private", owner=self.regular_user, publication_status="private"
        )
        self.review_obj = Property.objects.create(
            name="review", owner=self.regular_user, publication_status="review"
        )
        self.published_obj = Property.objects.create(
            name="published", owner=self.regular_user, publication_status="published"
        )

    def _action(self, action: str, obj, actor=None, data=None):
        actor = actor or self.regular_user
        req = self._build_request("post", f"/objects/{obj.pk}/action/", data=data or {})
        force_authenticate(req, user=actor)
        view = PropertyViewSet.as_view({"post": action})
        return view(req, pk=obj.pk)

    def test_register_for_review(self):
        resp = self._action("register_for_review", self.private_obj)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.private_obj.refresh_from_db()
        self.assertEqual(self.private_obj.publication_status, "review")

    def test_withdraw_from_review(self):
        resp = self._action("withdraw_from_review", self.review_obj)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.review_obj.refresh_from_db()
        self.assertEqual(self.review_obj.publication_status, "private")

    def test_register_for_review_denied_for_non_owner(self):
        resp = self._action(
            "register_for_review", self.private_obj, actor=self.other_user
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.private_obj.refresh_from_db()
        self.assertEqual(self.private_obj.publication_status, "private")

    def test_withdraw_from_review_denied_for_non_owner(self):
        resp = self._action(
            "withdraw_from_review", self.review_obj, actor=self.other_user
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.review_obj.refresh_from_db()
        self.assertEqual(self.review_obj.publication_status, "review")

    def test_owner_cannot_approve_own_object(self):
        resp = self._action("approve", self.review_obj)

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.review_obj.refresh_from_db()
        self.assertEqual(self.review_obj.publication_status, "review")

    def test_owner_cannot_reject_own_object(self):
        resp = self._action("reject", self.review_obj)

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.review_obj.refresh_from_db()
        self.assertEqual(self.review_obj.publication_status, "review")

    def test_approve_requires_inspected_revision(self):
        resp = self._action("approve", self.review_obj, actor=self.moderator)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.review_obj.refresh_from_db()
        self.assertEqual(self.review_obj.publication_status, "review")

    def test_approve_rejects_stale_revision(self):
        self.review_obj.name = "changed-while-inspecting"
        self.review_obj.content_revision += 1
        self.review_obj.save(update_fields=["name", "content_revision"])
        resp = self._action(
            "approve",
            self.review_obj,
            actor=self.moderator,
            data={"expected_revision": 1},
        )

        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.review_obj.refresh_from_db()
        self.assertEqual(self.review_obj.publication_status, "review")

    def test_approve_allows_moderator_for_another_users_object(self):
        resp = self._action(
            "approve",
            self.review_obj,
            actor=self.moderator,
            data={"expected_revision": self.review_obj.content_revision},
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.review_obj.refresh_from_db()
        self.assertEqual(self.review_obj.publication_status, "published")

    def test_reject_allows_moderator_for_another_users_object(self):
        resp = self._action("reject", self.review_obj, actor=self.moderator)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.review_obj.refresh_from_db()
        self.assertEqual(self.review_obj.publication_status, "declined")

    def test_archive_uses_dedicated_permission(self):
        with patch.object(
            UserCreatedObjectPermission,
            "has_archive_permission",
            return_value=False,
        ):
            resp = self._action("archive", self.published_obj, actor=self.moderator)

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.published_obj.refresh_from_db()
        self.assertEqual(self.published_obj.publication_status, "published")

    def test_archive_allows_moderator(self):
        resp = self._action("archive", self.published_obj, actor=self.moderator)

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.published_obj.refresh_from_db()
        self.assertEqual(self.published_obj.publication_status, "archived")


class UserCreatedObjectPermissionTests(BaseAPITestCase):
    def setUp(self):
        self.permission = UserCreatedObjectPermission()
        self.view = Mock(
            action=None,
            queryset=Property.objects.all(),
            get_queryset=Mock(return_value=Property.objects.all()),
        )
        self.admin = User.objects.create_user(username="policy-admin")
        self.admin.user_permissions.add(
            Permission.objects.get(codename="administer_objects")
        )
        _grant(self.admin, "change_property")
        self.moderator = User.objects.create_user(username="moderator")
        _grant(self.moderator, "can_moderate_property")

    def _post_request(self, user):
        req = self._build_request("post", "/objects/")
        req.user = user
        return req

    def _detail_request(self, verb: str, user):
        req = self._build_request(verb, "/objects/1/")
        req = Request(req)
        req.user = user
        return req

    def _obj(self, status_name, owner=None):
        return Property.objects.create(
            name=f"obj-{status_name}",
            owner=owner or self.regular_user,
            publication_status=status_name,
        )

    def test_has_permission_create(self):
        contributor = User.objects.create_user(username="contributor")
        _grant(contributor, "add_property")
        scenarios = [
            (self.staff_user, False),
            (contributor, True),
            (self.regular_user, False),
            (self.anonymous_user, False),
        ]
        self.view.action = "create"
        for user, expected in scenarios:
            with self.subTest(user=user):
                req = self._post_request(user)
                self.assertEqual(
                    self.permission.has_permission(req, self.view), expected
                )

    def test_owner_always_allowed(self):
        obj = self._obj("private")
        req = self._detail_request("get", self.regular_user)
        self.assertTrue(self.permission.has_object_permission(req, self.view, obj))

    def test_staff_denied_private_non_safe(self):
        obj = self._obj("private")
        req = self._detail_request("put", self.staff_user)
        self.assertFalse(self.permission.has_object_permission(req, self.view, obj))

    def test_non_owner_denied_private(self):
        another_user = User.objects.create_user("another")
        obj = self._obj("private")
        req = self._detail_request("get", another_user)
        self.assertFalse(self.permission.has_object_permission(req, self.view, obj))

    def test_anonymous_allowed_published_safe(self):
        obj = self._obj("published")
        req = self._detail_request("get", self.anonymous_user)
        self.assertTrue(self.permission.has_object_permission(req, self.view, obj))

    def test_owner_cannot_edit_published(self):
        _grant(self.regular_user, "change_property")
        obj = self._obj("published")
        req = self._detail_request("put", self.regular_user)
        self.assertFalse(self.permission.has_object_permission(req, self.view, obj))

    def test_owner_can_edit_review(self):
        _grant(self.regular_user, "change_property")
        obj = self._obj("review")
        req = self._detail_request("put", self.regular_user)
        self.assertTrue(self.permission.has_object_permission(req, self.view, obj))

    def test_owner_edit_requires_change_capability(self):
        obj = self._obj("review")
        req = self._detail_request("put", self.regular_user)
        self.assertFalse(self.permission.has_object_permission(req, self.view, obj))

    def test_admin_cannot_edit_published(self):
        obj = self._obj("published")
        req = self._detail_request("put", self.admin)
        self.assertFalse(self.permission.has_object_permission(req, self.view, obj))

    def test_admin_cannot_edit_archived(self):
        obj = self._obj("archived")
        req = self._detail_request("put", self.admin)
        self.assertFalse(self.permission.has_object_permission(req, self.view, obj))

    def test_owner_can_read_review(self):
        obj = self._obj("review")
        req = self._detail_request("get", self.regular_user)
        self.assertTrue(self.permission.has_object_permission(req, self.view, obj))

    def test_moderator_can_read_review(self):
        obj = self._obj("review")
        req = self._detail_request("get", self.moderator)
        self.assertTrue(self.permission.has_object_permission(req, self.view, obj))

    def test_owner_can_read_archived(self):
        obj = self._obj("archived")
        req = self._detail_request("get", self.regular_user)
        self.assertTrue(self.permission.has_object_permission(req, self.view, obj))

    def test_admin_can_read_archived(self):
        obj = self._obj("archived")
        req = self._detail_request("get", self.admin)
        self.assertTrue(self.permission.has_object_permission(req, self.view, obj))

    def test_anonymous_can_read_archived(self):
        # Archived records are public frozen historical data.
        obj = self._obj("archived")
        req = self._detail_request("get", self.anonymous_user)
        self.assertTrue(self.permission.has_object_permission(req, self.view, obj))

    def test_admin_can_read_private(self):
        obj = self._obj("private")
        req = self._detail_request("get", self.admin)
        self.assertTrue(self.permission.has_object_permission(req, self.view, obj))

    def test_staff_without_role_cannot_read_private(self):
        obj = self._obj("private")
        req = self._detail_request("get", self.staff_user)
        self.assertFalse(self.permission.has_object_permission(req, self.view, obj))
