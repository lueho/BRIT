import json
from contextlib import contextmanager
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, TestCase
from django.urls import reverse

from bibliography import services
from bibliography.forms import SourceBibtexArticleImportForm
from bibliography.models import Author, Source
from bibliography.serializers import SourceCreateSerializer
from utils.object_management.models import ReviewAction


class SourceCreationFinalizationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = User.objects.create_user("bib-actor")
        cls.actor.groups.clear()
        for model in (Source, Author):
            cls.actor.user_permissions.add(
                Permission.objects.get(
                    codename=f"add_{model._meta.model_name}",
                    content_type=ContentType.objects.get_for_model(model),
                )
            )
        cls.hopper = Author.objects.create(
            first_names="Grace",
            last_names="Hopper",
            owner=cls.actor,
            publication_status="published",
        )
        cls.lovelace = Author.objects.create(
            first_names="Ada",
            last_names="Lovelace",
            owner=cls.actor,
            publication_status="published",
        )
        cls.turing = Author.objects.create(
            first_names="Alan",
            last_names="Turing",
            owner=cls.actor,
            publication_status="published",
        )

    @contextmanager
    def _creation_boundary(self):
        snapshots = []
        original = services.record_creation

        def record(actor, obj, *args, **kwargs):
            if isinstance(obj, Source):
                snapshots.append(
                    Source.objects.values("citation_key", "content_revision").get(
                        pk=obj.pk
                    )
                )
            return original(actor, obj, *args, **kwargs)

        with patch.object(services, "record_creation", side_effect=record):
            yield snapshots

    def _assert_created(self, source, snapshots, expected):
        self.assertEqual(snapshots, [{"citation_key": expected, "content_revision": 1}])
        source.refresh_from_db()
        self.assertEqual(source.citation_key, expected)
        self.assertEqual(source.content_revision, 1)
        self.assertEqual(source.owner_id, self.actor.pk)
        self.assertEqual(source.publication_status, "private")
        self.assertEqual(
            list(
                ReviewAction.objects.filter(
                    content_type=ContentType.objects.get_for_model(Source),
                    object_id=source.pk,
                ).values_list("action", flat=True)
            ),
            ["created"],
        )

    def test_service_finalizes_complete_author_set_before_creation(self):
        for authors, expected in (
            ([self.lovelace, self.hopper], "Lovelace & Hopper 2024"),
            ([self.hopper, self.lovelace, self.turing], "Hopper et al. 2024"),
            ([], "Notes 2024"),
        ):
            with (
                self.subTest(expected=expected),
                self._creation_boundary() as snapshots,
            ):
                source = services.create_source_with_authors(
                    self.actor,
                    {"title": "Notes", "year": 2024},
                    [{"id": author.pk} for author in authors],
                )
                self._assert_created(source, snapshots, expected)

    def test_explicit_keys_survive_author_signals_before_creation(self):
        for key in ("MYKEY", "Notes CustomKey"):
            with self.subTest(key=key), self._creation_boundary() as snapshots:
                source = services.create_source_with_authors(
                    self.actor,
                    {"title": "Notes", "year": 2024, "citation_key": key},
                    [{"id": self.lovelace.pk}, {"id": self.hopper.pk}],
                )
                self._assert_created(source, snapshots, key)

    def test_bibtex_import_does_not_repair_citation_after_creation(self):
        form = SourceBibtexArticleImportForm(
            data={
                "bibtex_entry": (
                    "@article{notes, author={Lovelace, Ada and Hopper, Grace}, "
                    "title={Notes}, journal={Journal}, year={2024}}"
                )
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        with self._creation_boundary() as snapshots:
            source = form.create_source(owner=self.actor)
        self._assert_created(source, snapshots, "Lovelace & Hopper 2024")

    def test_quick_create_http_finalizes_before_creation(self):
        self.client.force_login(self.actor)
        with self._creation_boundary() as snapshots:
            response = self.client.post(
                reverse("source-quick-create"),
                data=json.dumps(
                    {
                        "title": "Notes",
                        "year": 2024,
                        "authors": [
                            {"id": self.lovelace.pk},
                            {"id": self.hopper.pk},
                        ],
                    }
                ),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 201, response.content)
        source = Source.objects.get(pk=response.json()["id"])
        self._assert_created(source, snapshots, "Lovelace & Hopper 2024")

    def test_api_create_returns_final_citation_and_single_creation(self):
        self.client.force_login(self.actor)
        with self._creation_boundary() as snapshots:
            response = self.client.post(
                reverse("api-source-create"),
                data=json.dumps(
                    {
                        "title": "Notes",
                        "type": "article",
                        "year": 2024,
                        "authors": [
                            {"id": self.lovelace.pk},
                            {"id": self.hopper.pk},
                        ],
                    }
                ),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["citation_key"], "Lovelace & Hopper 2024")
        source = Source.objects.get(pk=response.json()["id"])
        self._assert_created(source, snapshots, "Lovelace & Hopper 2024")

    def test_create_serializer_uses_same_finalization_boundary(self):
        request = RequestFactory().post(reverse("api-source-create"))
        request.user = self.actor
        serializer = SourceCreateSerializer(
            data={
                "title": "Notes",
                "year": 2024,
                "authors": [{"id": self.lovelace.pk}, {"id": self.hopper.pk}],
            },
            context={"request": request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with self._creation_boundary() as snapshots:
            source = serializer.save()
        self._assert_created(source, snapshots, "Lovelace & Hopper 2024")
