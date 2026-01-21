from __future__ import annotations

from unittest.mock import Mock, patch

from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import Q
from django.test import TestCase
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate

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

    def setUp(self):  # noqa: D401 (simple docstring ok in tests)
        self.factory = APIRequestFactory()
        self._VERB_MAP = {
            "get": self.factory.get,
            "post": self.factory.post,
            "put": self.factory.put,
            "patch": self.factory.patch,
            "delete": self.factory.delete,
        }
        self.staff_user = User.objects.create_user(username="staff", is_staff=True)
        self.regular_user = User.objects.create_user(username="regular", is_staff=False)
        self.anonymous_user = AnonymousUser()

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

    _meta = _Meta()

    def register_for_review(self):
        if self.publication_status != "private":
            raise ValidationError("Only private objects can be registered for review")
        self.publication_status = "review"

    def withdraw_from_review(self):
        if self.publication_status != "review":
            raise ValidationError("Only objects in review can be withdrawn")
        self.publication_status = "private"


class MockUserCreatedObjectViewSet(UserCreatedObjectViewSet):
    queryset = MockUserCreatedObject.objects.all()
    serializer_class = UserObjectSerializer
    permission_classes = [UserCreatedObjectPermission]


class GlobalObjectViewSetTests(BaseAPITestCase):
    """Read/write rules for *global* objects."""

    def setUp(self):
        super().setUp()
        self.example = TestGlobalObject.objects.create(
            name="Example", description="desc"
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

    def test_staff_user_can_write(self):
        # create
        create = self._response(
            "post", user=self.staff_user, data={"name": "New", "description": "d"}
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
                verb, user=self.staff_user, data=payload, pk=self.example.id
            )
            expected = (
                status.HTTP_204_NO_CONTENT if verb == "delete" else status.HTTP_200_OK
            )
            self.assertEqual(resp.status_code, expected)

    def test_duplicate_name_returns_400(self):
        self._response(
            "post", user=self.staff_user, data={"name": "Unique", "description": "d"}
        )
        dup = self._response(
            "post", user=self.staff_user, data={"name": "Unique", "description": "dup"}
        )
        self.assertEqual(dup.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", dup.data)

    def test_delete_unknown_pk_returns_404(self):
        resp = self._response("delete", user=self.staff_user, pk=9999)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class UserCreatedObjectQueryTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.base_qs = Mock(name="base_qs", spec=["filter"])
        self.base_qs.filter.side_effect = lambda *a, **kw: self.base_qs
        MockUserCreatedObjectViewSet.queryset = self.base_qs

    def _get_qs(self, *, user: User | AnonymousUser, params: dict | None = None):
        params = params or {}
        req = self._build_request("get", "/objects/", data=params)
        if getattr(user, "is_authenticated", False):
            force_authenticate(req, user=user)
        view = MockUserCreatedObjectViewSet()
        view.request = Request(req)
        view.queryset = self.base_qs
        return view.get_queryset()

    def test_regular_default_scope_published(self):
        self._get_qs(user=self.regular_user)
        self.base_qs.filter.assert_called_once_with(publication_status="published")

    def test_regular_scope_private(self):
        self._get_qs(user=self.regular_user, params={"scope": "private"})
        self.base_qs.filter.assert_called_once_with(owner=self.regular_user)

    def test_regular_scope_review(self):
        self._get_qs(user=self.regular_user, params={"scope": "review"})
        q = self.base_qs.filter.call_args[0][0]
        self.assertIsInstance(q, Q)
        self.assertIn(("owner", self.regular_user), q.children)
        self.assertIn(("publication_status", "review"), q.children)

    def test_invalid_scope_fallback(self):
        self._get_qs(user=self.regular_user, params={"scope": "wat"})
        q = self.base_qs.filter.call_args[0][0]
        self.assertIn(("owner", self.regular_user), q.children)
        self.assertIn(("publication_status", "published"), q.children)

    def test_staff_sees_everything(self):
        qs = self._get_qs(user=self.staff_user)
        self.base_qs.filter.assert_not_called()
        self.assertIs(qs, self.base_qs)

    def test_anonymous_published_only(self):
        self._get_qs(user=self.anonymous_user)
        self.base_qs.filter.assert_called_once_with(publication_status="published")


class UserCreatedObjectCreationTests(BaseAPITestCase):
    def test_perform_create_sets_owner(self):
        serializer = Mock(save=Mock(return_value=MockUserCreatedObject()))
        viewset = MockUserCreatedObjectViewSet()
        req = self._build_request("post", "/objects/")
        force_authenticate(req, user=self.regular_user)
        viewset.request = Request(req)
        viewset.perform_create(serializer)
        serializer.save.assert_called_once_with(owner=self.regular_user)


class UserCreatedObjectWorkflowTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.viewset = MockUserCreatedObjectViewSet()
        self.viewset.queryset = Mock(model=MockUserCreatedObject)
        self.viewset.get_queryset = Mock(return_value=self.viewset.queryset)
        self.viewset.check_object_permissions = Mock()
        self.private_obj = MockUserCreatedObject(
            pk=1, owner=self.regular_user, publication_status="private"
        )
        self.review_obj = MockUserCreatedObject(
            pk=2, owner=self.regular_user, publication_status="review"
        )

    def _action(self, action: str, obj: MockUserCreatedObject):
        req = self._build_request("post", f"/objects/{obj.pk}/action/")
        force_authenticate(req, user=self.regular_user)
        self.viewset.request = Request(req)
        self.viewset.kwargs = {"pk": obj.pk}
        with (
            patch(
                "utils.object_management.viewsets.get_object_or_404", return_value=obj
            ),
            patch(
                "utils.object_management.viewsets.Response",
                side_effect=lambda d, status: Mock(status_code=status),
            ),
        ):
            return getattr(self.viewset, action)(req, pk=obj.pk)

    def test_register_for_review(self):
        resp = self._action("register_for_review", self.private_obj)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(self.private_obj.publication_status, "review")

    def test_withdraw_from_review(self):
        resp = self._action("withdraw_from_review", self.review_obj)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(self.review_obj.publication_status, "private")


class UserCreatedObjectPermissionTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.permission = UserCreatedObjectPermission()
        self.view = Mock(
            action=None,
            get_queryset=Mock(return_value=Mock(model=MockUserCreatedObject)),
        )

    def _post_request(self, user):
        req = self._build_request("post", "/objects/")
        req.user = user
        return req

    def _detail_request(self, verb: str, user):
        req = self._build_request(verb, "/objects/1/")
        req.user = user
        return req

    def test_has_permission_create(self):
        scenarios = [
            # (user, has_perm_return_value)
            (self.staff_user, True),
            (self.staff_user, False),
            (self.regular_user, True),
            (self.regular_user, False),
            (self.anonymous_user, False),
        ]
        self.view.action = "create"
        for user, has_perm in scenarios:
            with self.subTest(user=user, perm=has_perm):
                req = self._post_request(user)
                with patch.object(
                    user,
                    "has_perm",
                    return_value=has_perm if user.is_authenticated else False,
                ):
                    allowed = self.permission.has_permission(req, self.view)
                    expected = user.is_staff or (user.is_authenticated and has_perm)
                    self.assertEqual(allowed, expected)

    def test_owner_always_allowed(self):
        obj = MockUserCreatedObject(
            owner=self.regular_user, publication_status="private"
        )
        req = self._detail_request("get", self.regular_user)
        self.assertTrue(self.permission.has_object_permission(req, self.view, obj))

    def test_staff_denied_private_non_safe(self):
        obj = MockUserCreatedObject(
            owner=self.regular_user, publication_status="private"
        )
        req = self._detail_request("put", self.staff_user)
        req = Request(req)
        req.user = self.staff_user
        self.assertFalse(self.permission.has_object_permission(req, self.view, obj))

    def test_non_owner_denied_private(self):
        another_user = User.objects.create_user("another")
        obj = MockUserCreatedObject(
            owner=self.regular_user, publication_status="private"
        )
        req = self._detail_request("get", another_user)
        with patch.object(
            self.permission, "_check_safe_permissions", return_value=False
        ):
            self.assertFalse(self.permission.has_object_permission(req, self.view, obj))

    def test_anonymous_allowed_published_safe(self):
        obj = MockUserCreatedObject(
            owner=self.regular_user, publication_status="published"
        )
        req = self._detail_request("get", self.anonymous_user)
        with patch.object(
            self.permission, "_check_safe_permissions", return_value=True
        ):
            self.assertTrue(self.permission.has_object_permission(req, self.view, obj))

    def test_owner_cannot_edit_published(self):
        obj = MockUserCreatedObject(
            owner=self.regular_user, publication_status="published"
        )
        req = self._detail_request("put", self.regular_user)
        req = Request(req)
        req.user = self.regular_user
        self.assertFalse(self.permission.has_object_permission(req, self.view, obj))

    def test_owner_can_edit_review(self):
        obj = MockUserCreatedObject(
            owner=self.regular_user, publication_status="review"
        )
        req = self._detail_request("put", self.regular_user)
        req = Request(req)
        req.user = self.regular_user
        self.assertTrue(self.permission.has_object_permission(req, self.view, obj))

    def test_staff_can_edit_published(self):
        obj = MockUserCreatedObject(
            owner=self.regular_user, publication_status="published"
        )
        req = self._detail_request("put", self.staff_user)
        req = Request(req)
        req.user = self.staff_user
        self.assertTrue(self.permission.has_object_permission(req, self.view, obj))

    def test_staff_can_edit_archived(self):
        obj = MockUserCreatedObject(
            owner=self.regular_user, publication_status="archived"
        )
        req = self._detail_request("put", self.staff_user)
        req = Request(req)
        req.user = self.staff_user
        self.assertTrue(self.permission.has_object_permission(req, self.view, obj))

    def test_owner_can_read_review(self):
        obj = MockUserCreatedObject(
            owner=self.regular_user, publication_status="review"
        )
        req = self._detail_request("get", self.regular_user)
        self.assertTrue(self.permission.has_object_permission(req, self.view, obj))

    def test_staff_can_read_review(self):
        obj = MockUserCreatedObject(
            owner=self.regular_user, publication_status="review"
        )
        req = self._detail_request("get", self.staff_user)
        self.assertTrue(self.permission.has_object_permission(req, self.view, obj))

    def test_owner_can_read_archived(self):
        obj = MockUserCreatedObject(
            owner=self.regular_user, publication_status="archived"
        )
        req = self._detail_request("get", self.regular_user)
        self.assertTrue(self.permission.has_object_permission(req, self.view, obj))

    def test_staff_can_read_archived(self):
        obj = MockUserCreatedObject(
            owner=self.regular_user, publication_status="archived"
        )
        req = self._detail_request("get", self.staff_user)
        self.assertTrue(self.permission.has_object_permission(req, self.view, obj))

    def test_anonymous_cannot_read_archived(self):
        obj = MockUserCreatedObject(
            owner=self.regular_user, publication_status="archived"
        )
        req = self._detail_request("get", self.anonymous_user)
        self.assertFalse(self.permission.has_object_permission(req, self.view, obj))

    def test_staff_can_read_private(self):
        obj = MockUserCreatedObject(
            owner=self.regular_user, publication_status="private"
        )
        req = self._detail_request("get", self.staff_user)
        self.assertTrue(self.permission.has_object_permission(req, self.view, obj))
