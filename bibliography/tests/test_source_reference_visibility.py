from django.contrib.auth.models import AnonymousUser, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, TestCase
from django.urls import reverse

from bibliography.models import Author, Licence, Source, SourceAuthor
from bibliography.serializers import HyperlinkedSourceSerializer, SourceModelSerializer
from utils.object_management.models import ObjectEditorGrant, ReviewAction
from utils.object_management.policy import decide, visible_queryset


class SourceReferenceVisibilityTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("ref-owner")
        cls.stranger = User.objects.create_user("ref-stranger")
        cls.editor = User.objects.create_user("ref-editor")
        cls.staff = User.objects.create_user("ref-staff", is_staff=True)
        cls.grantee = User.objects.create_user("ref-grantee")
        cls.admin = User.objects.create_user(
            "ref-admin", is_staff=True, is_superuser=True
        )
        for user in (cls.owner, cls.stranger, cls.editor, cls.staff, cls.grantee):
            user.groups.clear()
        cls.editor.user_permissions.add(
            Permission.objects.get(
                codename="change_source",
                content_type=ContentType.objects.get_for_model(Source),
            )
        )
        cls.lic_pub = Licence.objects.create(
            name="lic-pub", owner=cls.owner, publication_status="published"
        )
        cls.lic_priv = Licence.objects.create(
            name="lic-priv", owner=cls.owner, publication_status="private"
        )
        cls.a_pub = Author.objects.create(
            last_names="Public", owner=cls.owner, publication_status="published"
        )
        cls.a_own = Author.objects.create(
            last_names="Own", owner=cls.owner, publication_status="private"
        )
        cls.a_for = Author.objects.create(
            last_names="Foreign", owner=cls.stranger, publication_status="private"
        )
        cls.source = Source.objects.create(
            title="Ref Source",
            year=2024,
            citation_key="PublicCitation",
            owner=cls.owner,
            publication_status="published",
            licence=cls.lic_priv,
        )
        cls.private_source = Source.objects.create(
            title="Private Source",
            year=2024,
            citation_key="PrivateCitation",
            owner=cls.owner,
            licence=cls.lic_priv,
        )
        for source in (cls.source, cls.private_source):
            for position, author in enumerate((cls.a_pub, cls.a_own, cls.a_for), 1):
                SourceAuthor.objects.create(
                    source=source, author=author, position=position
                )
            cls._grant(source, cls.editor)
        cls._grant(cls.a_own, cls.grantee)
        cls._grant(cls.lic_priv, cls.grantee)

    @staticmethod
    def _grant(obj, editor):
        ObjectEditorGrant.objects.create(
            content_type=ContentType.objects.get_for_model(obj),
            object_id=obj.pk,
            editor=editor,
        )

    def _context(self, user=None):
        request = RequestFactory().get(
            reverse("api-source-detail", args=[self.source.pk])
        )
        request.user = user or AnonymousUser()
        return {"request": request}

    def _snapshot(self):
        return {
            model._meta.label_lower: list(model.objects.order_by("pk").values())
            for model in (Source, Author, Licence, SourceAuthor, ReviewAction)
        }

    def _assert_references(self, data, authors, licence, hyperlinked=False):
        if hyperlinked:
            self.assertEqual(
                [entry["name"] for entry in data["authors"]],
                [str(author) for author in authors],
            )
        else:
            self.assertEqual(
                [entry["id"] for entry in data["authors"]],
                [author.pk for author in authors],
            )
        if licence is None:
            self.assertIsNone(data["licence"])
        else:
            self.assertEqual(data["licence"]["name"], licence.name)
        self.assertEqual(data["citation_key"], "PublicCitation")

    def test_http_list_and_detail_scope_references_for_each_persona(self):
        before = self._snapshot()
        for actor, authors, licence in (
            (None, [self.a_pub], None),
            (self.stranger, [self.a_pub, self.a_for], None),
            (self.owner, [self.a_pub, self.a_own], self.lic_priv),
            (self.editor, [self.a_pub], None),
            (self.staff, [self.a_pub], None),
            (self.grantee, [self.a_pub, self.a_own], self.lic_priv),
            (self.admin, [self.a_pub, self.a_own, self.a_for], self.lic_priv),
        ):
            with self.subTest(actor=actor):
                self.client.logout()
                if actor is not None:
                    self.client.force_login(actor)
                detail = self.client.get(
                    reverse("api-source-detail", args=[self.source.pk])
                )
                self.assertEqual(detail.status_code, 200)
                self._assert_references(detail.data, authors, licence)
                listing = self.client.get(reverse("api-source-list"))
                self.assertEqual(listing.status_code, 200)
                entry = next(row for row in listing.data if row["id"] == self.source.pk)
                self._assert_references(entry, authors, licence)
        self.assertEqual(self._snapshot(), before)

    def test_private_references_fail_own_read_policy_while_source_is_readable(self):
        anonymous = AnonymousUser()
        for obj in (self.a_own, self.a_for, self.lic_priv):
            with self.subTest(model=type(obj).__name__, pk=obj.pk):
                self.assertFalse(decide(anonymous, "read", obj).allowed)
                self.assertFalse(
                    visible_queryset(
                        anonymous, type(obj).objects.filter(pk=obj.pk)
                    ).exists()
                )
        response = self.client.get(reverse("api-source-detail", args=[self.source.pk]))
        self.assertEqual(response.status_code, 200)
        self._assert_references(response.data, [self.a_pub], None)

    def test_private_reference_api_details_deny_anonymous_readers(self):
        for name, pk in (
            ("api-author-detail", self.a_own.pk),
            ("api-author-detail", self.a_for.pk),
            ("api-licence-detail", self.lic_priv.pk),
        ):
            url = reverse(name, args=[pk])
            with self.subTest(url=url):
                with self.assertLogs("django.request", level="WARNING") as logs:
                    response = self.client.get(url)
                self.assertEqual(response.status_code, 404)
                self.assertTrue(
                    any(f"Not Found: {url}" in line for line in logs.output)
                )
        response = self.client.get(reverse("api-source-detail", args=[self.source.pk]))
        self.assertEqual(response.status_code, 200)
        self._assert_references(response.data, [self.a_pub], None)

    def test_both_serializers_keep_independent_read_scope(self):
        before = self._snapshot()
        for actor, authors, licence in (
            (None, [self.a_pub], None),
            (self.owner, [self.a_pub, self.a_own], self.lic_priv),
            (self.editor, [self.a_pub], None),
            (self.staff, [self.a_pub], None),
            (self.grantee, [self.a_pub, self.a_own], self.lic_priv),
            (self.admin, [self.a_pub, self.a_own, self.a_for], self.lic_priv),
        ):
            for serializer in (SourceModelSerializer, HyperlinkedSourceSerializer):
                with self.subTest(actor=actor, serializer=serializer.__name__):
                    data = serializer(self.source, context=self._context(actor)).data
                    self._assert_references(
                        data,
                        authors,
                        licence,
                        serializer is HyperlinkedSourceSerializer,
                    )
        self.assertEqual(self._snapshot(), before)

    def test_source_editor_can_read_private_parent_without_inheriting_references(self):
        self.assertTrue(decide(self.editor, "edit", self.private_source).allowed)
        self.client.force_login(self.editor)
        response = self.client.get(
            reverse("api-source-detail", args=[self.private_source.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [entry["id"] for entry in response.data["authors"]], [self.a_pub.pk]
        )
        self.assertIsNone(response.data["licence"])

    def test_missing_context_is_anonymous_and_public_or_null_licence_stays_correct(
        self,
    ):
        data = SourceModelSerializer(self.source).data
        self._assert_references(data, [self.a_pub], None)
        for licence in (self.lic_pub, None):
            self.source.licence = licence
            self.source.save(update_fields=["licence"])
            for serializer in (SourceModelSerializer, HyperlinkedSourceSerializer):
                with self.subTest(licence=licence, serializer=serializer.__name__):
                    data = serializer(self.source, context=self._context()).data
                    self._assert_references(
                        data,
                        [self.a_pub],
                        licence,
                        serializer is HyperlinkedSourceSerializer,
                    )

    def test_visible_link_order_survives_private_gaps_and_links_from_other_sources(
        self,
    ):
        first = Author.objects.create(
            last_names="Zulu", owner=self.owner, publication_status="published"
        )
        SourceAuthor.objects.filter(source=self.source, author=self.a_pub).update(
            position=4
        )
        SourceAuthor.objects.create(source=self.source, author=first, position=1)
        SourceAuthor.objects.create(
            source=self.private_source, author=first, position=99
        )
        for serializer in (SourceModelSerializer, HyperlinkedSourceSerializer):
            with self.subTest(serializer=serializer.__name__):
                data = serializer(self.source, context=self._context()).data
                self._assert_references(
                    data,
                    [first, self.a_pub],
                    None,
                    serializer is HyperlinkedSourceSerializer,
                )
