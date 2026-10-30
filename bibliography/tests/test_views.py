import json
import time
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core import signing
from django.db.models.signals import post_save
from django.urls import reverse
from django.utils.html import escape
from factory.django import mute_signals

from utils.object_management.models import User
from utils.tests.testcases import (
    AbstractTestCases,
    CheckUrlButtonVisibilityTestMixin,
    ViewWithPermissionsTestCase,
)

from ..models import Author, Licence, Source, SourceAuthor, check_url_valid


def setUpModule():
    post_save.disconnect(check_url_valid, sender=Source)


def tearDownModule():
    post_save.connect(check_url_valid, sender=Source)


# ----------- Author CRUD ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AuthorCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    modal_detail_view = True
    modal_update_view = True
    modal_create_view = True
    add_scope_query_param_to_list_urls = True

    model = Author

    view_explorer_name = "bibliography-explorer"
    view_create_name = "author-create"
    view_modal_create_name = "author-create-modal"
    view_published_list_name = "author-list"
    view_private_list_name = "author-list-owned"
    view_detail_name = "author-detail"
    view_modal_detail_name = "author-detail-modal"
    view_update_name = "author-update"
    view_modal_update_name = "author-update-modal"
    view_delete_name = "author-delete-modal"

    create_object_data = {"last_names": "Test Author"}
    update_object_data = {"last_names": "Updated Author"}


# ----------- Author Utils ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AuthorAutoCompleteViewTestCase(ViewWithPermissionsTestCase):
    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse("author-autocomplete"))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("author-autocomplete"))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("author-autocomplete"))
        self.assertEqual(response.status_code, 200)

    def test_get_returns_only_authors_with_given_string_in_name(self):
        test_author = Author.objects.create(
            first_names="Test", last_names="Author", publication_status="published"
        )
        Author.objects.create(
            first_names="Another", last_names="Author", publication_status="published"
        )
        response = self.client.get(reverse("author-autocomplete"), {"q": "Test"})

        expected_result = {
            "id": test_author.pk,
            "label": "Author, Test",
            "first_names": "Test",
            "last_names": "Author",
            "can_view": True,
            "can_update": True,
            "can_delete": True,
        }

        self.assertEqual(1, len(response.json()["results"]))
        self.assertDictEqual(expected_result, response.json()["results"][0])

    def test_get_excludes_person_authors_without_letters_in_surname(self):
        """Legacy rows that bypassed clean() must not pollute the dropdown."""
        Author.objects.create(
            first_names="", last_names="30.379", publication_status="published"
        )
        valid = Author.objects.create(
            first_names="Test", last_names="Author", publication_status="published"
        )
        response = self.client.get(reverse("author-autocomplete"))
        ids = [result["id"] for result in response.json()["results"]]
        self.assertIn(valid.pk, ids)
        self.assertNotIn(Author.objects.get(last_names="30.379").pk, ids)

    def test_get_excludes_organizations_without_letters_in_name(self):
        Author.objects.create(
            author_type="organization",
            organization_name="70",
            publication_status="published",
        )
        valid = Author.objects.create(
            author_type="organization",
            organization_name="3M Company",
            publication_status="published",
        )
        response = self.client.get(reverse("author-autocomplete"))
        ids = [result["id"] for result in response.json()["results"]]
        self.assertIn(valid.pk, ids)
        self.assertNotIn(Author.objects.get(organization_name="70").pk, ids)


class AuthorQuickCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ["add_author"]

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        response = self.client.post(
            reverse("author-quick-create"),
            data=json.dumps({"first_names": "Ada", "last_names": "Lovelace"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_authenticated_without_permission(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse("author-quick-create"),
            data=json.dumps({"first_names": "Ada", "last_names": "Lovelace"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_400_bad_request_when_last_name_is_blank(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("author-quick-create"),
            data=json.dumps({"first_names": "Ada", "last_names": "   "}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_post_http_400_bad_request_when_last_name_has_no_letter(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("author-quick-create"),
            data=json.dumps({"first_names": "", "last_names": "70"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Author.objects.filter(last_names="70").exists())

    def test_post_http_400_bad_request_when_organization_name_has_no_letter(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("author-quick-create"),
            data=json.dumps(
                {"author_type": "organization", "organization_name": "30.379,"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Author.objects.filter(organization_name="30.379,").exists())

    def test_post_http_201_creates_author_for_member(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("author-quick-create"),
            data=json.dumps({"first_names": "Ada", "last_names": "Lovelace"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        author = Author.objects.get(pk=payload["id"])

        self.assertEqual(author.first_names, "Ada")
        self.assertEqual(author.last_names, "Lovelace")
        self.assertEqual(author.owner, self.member)

    def test_post_http_200_returns_existing_author(self):
        self.client.force_login(self.member)
        existing = Author.objects.create(
            owner=self.member,
            first_names="Ada",
            last_names="Lovelace",
        )

        response = self.client.post(
            reverse("author-quick-create"),
            data=json.dumps({"first_names": "Ada", "last_names": "Lovelace"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], existing.pk)
        self.assertEqual(Author.objects.filter(last_names="Lovelace").count(), 1)

    def test_post_http_201_creates_organisation_author_with_empty_first_names(self):
        """Organisation names passed as last_names should be stored verbatim."""
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("author-quick-create"),
            data=json.dumps(
                {"first_names": "", "last_names": "European Environment Agency"}
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        author = Author.objects.get(pk=payload["id"])

        self.assertEqual(author.first_names, "")
        self.assertEqual(author.last_names, "European Environment Agency")
        self.assertEqual(payload["label"], "European Environment Agency")

    def test_post_http_201_creates_organisation_author_with_author_type(self):
        """An explicit author_type=organization creates an organization author."""
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("author-quick-create"),
            data=json.dumps(
                {
                    "author_type": "organization",
                    "organization_name": "European Environment Agency",
                    "organization_abbreviation": "EEA",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        author = Author.objects.get(pk=payload["id"])

        self.assertEqual(author.author_type, "organization")
        self.assertEqual(author.organization_name, "European Environment Agency")
        self.assertEqual(author.organization_abbreviation, "EEA")
        self.assertEqual(payload["label"], "European Environment Agency")

    def test_post_http_200_returns_existing_organisation_author(self):
        """Duplicate organization quick-create returns the existing record."""
        self.client.force_login(self.member)
        existing = Author.objects.create(
            owner=self.member,
            author_type="organization",
            organization_name="European Environment Agency",
        )

        response = self.client.post(
            reverse("author-quick-create"),
            data=json.dumps(
                {
                    "author_type": "organization",
                    "organization_name": "European Environment Agency",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], existing.pk)
        self.assertEqual(
            Author.objects.filter(
                organization_name="European Environment Agency"
            ).count(),
            1,
        )


# ----------- Licence CRUD ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class LicenceCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    modal_detail_view = True
    modal_update_view = True
    modal_create_view = True
    add_scope_query_param_to_list_urls = True

    model = Licence

    view_explorer_name = "bibliography-explorer"
    view_create_name = "licence-create"
    view_modal_create_name = "licence-create-modal"
    view_published_list_name = "licence-list"
    view_private_list_name = "licence-list-owned"
    view_detail_name = "licence-detail"
    view_modal_detail_name = "licence-detail-modal"
    view_update_name = "licence-update"
    view_modal_update_name = "licence-update-modal"
    view_delete_name = "licence-delete-modal"

    create_object_data = {"name": "Test Licence"}
    update_object_data = {"name": "Updated Test Licence"}


# ----------------------------------------------------------------------------------------------------------------------


class SourceCRUDViewsTestCase(
    CheckUrlButtonVisibilityTestMixin,
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase,
):
    model = Source
    add_scope_query_param_to_list_urls = True

    view_explorer_name = "bibliography-explorer"

    modal_detail_view = True
    modal_create_view = True

    view_explorer_name = "bibliography-explorer"
    view_create_name = "source-create"
    view_modal_create_name = "source-create-modal"
    view_published_list_name = "source-list"
    view_private_list_name = "source-list-owned"
    view_review_list_name = "source-list-review"
    view_detail_name = "source-detail"
    view_modal_detail_name = "source-detail-modal"
    view_update_name = "source-update"
    view_modal_update_name = "source-update-modal"
    view_delete_name = "source-delete-modal"

    allow_create_for_any_authenticated_user = True

    create_object_data = {
        "title": "Test source",
        "citation_key": "TEST",
        "type": "online",
        "url": "https://example.com",
    }
    update_object_data = {
        "title": "Updated source",
        "citation_key": "UPD",
        "type": "online",
        "url": "https://example.org",
    }

    def test_detail_context_navigation_preserves_safe_results_url(self):
        results_url = reverse("source-list") + "?scope=published&title=compost&page=2"
        for user in (None, self.owner_user):
            for back in (results_url, "https://testserver" + results_url):
                with self.subTest(user=user, back=back):
                    self.client.logout()
                    if user:
                        self.client.force_login(user)
                    response = self.client.get(
                        self.published_object.get_absolute_url(),
                        {"back": back},
                        secure=True,
                    )
                    self.assertEqual(response.context["back_url"], back)
                    self.assertContains(response, f'href="{escape(back)}"')
                    self.assertContains(response, "Back to results", count=1)
                    self.assertTemplateUsed(
                        response, "bibliography/includes/source_context_nav.html"
                    )

    def test_detail_context_navigation_omits_unsafe_or_missing_results_url(self):
        for back in (
            None,
            "",
            "https://external.example/",
            "//external.example/",
            "javascript:alert(1)",
            "data:text/html,test",
            "http://testserver/bibliography/sources/",
            "/\\external.example/",
            "/bibliography/sources/1/modal/",
        ):
            with self.subTest(back=back):
                self.client.logout()
                response = self.client.get(
                    self.published_object.get_absolute_url(),
                    {"back": back} if back is not None else {},
                    secure=True,
                )
                self.assertEqual(response.context["back_url"], "")
                self.assertNotContains(response, "Back to results")
                self.assertContains(response, 'aria-label="Source navigation"')
                self.assertContains(response, "All sources")
                self.assertContains(response, "Bibliography explorer")

    def test_list_letter_filter_narrows_by_citation_key(self):
        zeta = Source.objects.create(
            owner=self.owner_user,
            publication_status="published",
            title="Zeta source",
            citation_key="ZETA",
            type="online",
            url="https://zeta.example.org",
        )

        response = self.client.get(
            reverse("source-list"), {"scope": "published", "letter": "Z"}
        )

        self.assertEqual(response.status_code, 200)
        result_pks = {obj.pk for obj in response.context["object_list"]}
        self.assertIn(zeta.pk, result_pks)
        self.assertNotIn(self.published_object.pk, result_pks)

    def test_list_renders_letter_index(self):
        response = self.client.get(reverse("source-list"), {"scope": "published"})

        self.assertContains(response, 'aria-label="Filter by first letter"')

    def test_list_filter_form_carries_active_letter(self):
        response = self.client.get(
            reverse("source-list"), {"scope": "published", "letter": "Z"}
        )

        self.assertContains(
            response, '<input type="hidden" name="letter" value="Z">', html=True
        )

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        from django.contrib.contenttypes.models import ContentType

        moderator = User.objects.create(username="moderator")
        content_type = ContentType.objects.get_for_model(Source)
        permission, _ = Permission.objects.get_or_create(
            codename="can_moderate_source",
            content_type=content_type,
            defaults={"name": "Can moderate sources"},
        )
        moderator.user_permissions.add(permission)
        cls.util_objects["moderator"] = moderator

        author_1 = Author.objects.create(
            last_names="Test Author",
            first_names="One",
            publication_status="published",
        )
        author_2 = Author.objects.create(
            last_names="Test Author",
            first_names="Two",
            publication_status="published",
        )

        cls.source_author_1 = SourceAuthor.objects.create(
            source=cls.published_object,
            author=author_1,
            position=1,
        )
        cls.source_author_2 = SourceAuthor.objects.create(
            source=cls.published_object,
            author=author_2,
            position=2,
        )
        cls.source_author_3 = SourceAuthor.objects.create(
            source=cls.unpublished_object,
            author=author_1,
            position=1,
        )
        cls.source_author_4 = SourceAuthor.objects.create(
            source=cls.unpublished_object,
            author=author_2,
            position=2,
        )

    def related_objects_post_data(self):
        return {
            "sourceauthors-TOTAL_FORMS": 2,
            "sourceauthors-INITIAL_FORMS": 0,
            "sourceauthors-0-id": "",
            "sourceauthors-0-source": "",
            "sourceauthors-0-author": self.source_author_1.author.pk,
            "sourceauthors-1-id": "",
            "sourceauthors-1-source": "",
            "sourceauthors-1-author": self.source_author_2.author.pk,
        }

    def test_detail_view_published_contains_check_url_button_for_staff(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(self.get_detail_url(self.published_object.pk))
        self.assertContains(response, "check url")

    def test_detail_view_published_contains_check_url_button_for_moderator(self):
        self.client.force_login(self.util_objects["moderator"])
        response = self.client.get(self.get_detail_url(self.published_object.pk))
        self.assertContains(response, "check url")

    def test_create_source_without_author_succeeds(self):
        """
        Regression test: Creating a Source without any authors should succeed and not create a SourceAuthor row.
        """
        self.client.force_login(self.user_with_add_perm)
        post_data = self.create_object_data.copy()
        # Simulate no authors in the inline formset
        related_post_data = {
            "sourceauthors-TOTAL_FORMS": 1,
            "sourceauthors-INITIAL_FORMS": 0,
            "sourceauthors-0-id": "",
            "sourceauthors-0-source": "",
            "sourceauthors-0-author": "",  # No author selected
        }
        post_data.update(related_post_data)
        response = self.client.post(self.get_create_url(), post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        from ..models import Source

        source = Source.objects.latest("pk")
        self.assertEqual(source.sourceauthors.count(), 0)

    def test_create_source_with_inline_author_runs_in_create_boundary(self):
        """A create posting an inline SourceAuthor row is a governed write:
        the child row is persisted inside the bound create boundary, so a
        single ``created`` audit event covers the whole compound write."""
        from django.contrib.contenttypes.models import ContentType

        from utils.object_management.models import ReviewAction

        self.client.force_login(self.owner_user)
        post_data = {
            "title": "Inline governed source",
            "citation_key": "IGS",
            "type": "misc",
            "url": "https://example.org/inline",
            "sourceauthors-TOTAL_FORMS": 1,
            "sourceauthors-INITIAL_FORMS": 0,
            "sourceauthors-0-id": "",
            "sourceauthors-0-source": "",
            "sourceauthors-0-author": self.source_author_1.author.pk,
        }
        response = self.client.post(self.get_create_url(), post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        source = Source.objects.get(citation_key="IGS")
        self.assertEqual(source.sourceauthors.count(), 1)
        self.assertEqual(source.content_revision, 1)
        events = ReviewAction.objects.filter(
            content_type=ContentType.objects.get_for_model(Source),
            object_id=source.pk,
            action=ReviewAction.ACTION_CREATED,
        )
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.get().changed_fields, ["created"])

    def test_create_source_denial_inside_boundary_rolls_back_inline_writes(self):
        """A deactivation committed while the create boundary waited on the
        actor denies the whole write: no source row, no inline rows and no
        audit survive."""
        from django.contrib.contenttypes.models import ContentType

        from utils.object_management import services
        from utils.object_management.models import ReviewAction

        self.client.force_login(self.owner_user)
        source_ct = ContentType.objects.get_for_model(Source)
        baseline_authors = SourceAuthor.objects.count()
        baseline_actions = ReviewAction.objects.filter(content_type=source_ct).count()
        real_fresh_actor = services._fresh_actor

        def deactivate_then_fresh_actor(user):
            User.objects.filter(pk=user.pk).update(is_active=False)
            return real_fresh_actor(user)

        post_data = {
            "title": "Denied source",
            "citation_key": "DND",
            "type": "misc",
            "sourceauthors-TOTAL_FORMS": 1,
            "sourceauthors-INITIAL_FORMS": 0,
            "sourceauthors-0-id": "",
            "sourceauthors-0-source": "",
            "sourceauthors-0-author": self.source_author_1.author.pk,
        }
        with patch.object(
            services, "_fresh_actor", side_effect=deactivate_then_fresh_actor
        ):
            response = self.client.post(self.get_create_url(), post_data)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Source.objects.filter(citation_key="DND").exists())
        self.assertEqual(SourceAuthor.objects.count(), baseline_authors)
        self.assertEqual(
            ReviewAction.objects.filter(content_type=source_ct).count(),
            baseline_actions,
        )

    def test_create_source_inline_failure_rolls_back_parent_row_and_audit(self):
        """If persisting a stashed inline formset fails inside the boundary,
        the whole governed create rolls back: no source row and no
        ``created`` audit event survive."""
        from django.contrib.contenttypes.models import ContentType

        from utils.object_management.models import ReviewAction

        from ..forms import SourceAuthorFormSet

        self.client.force_login(self.owner_user)
        post_data = {
            "title": "Rolled back source",
            "citation_key": "RBS",
            "type": "misc",
            "sourceauthors-TOTAL_FORMS": 1,
            "sourceauthors-INITIAL_FORMS": 0,
            "sourceauthors-0-id": "",
            "sourceauthors-0-source": "",
            "sourceauthors-0-author": self.source_author_1.author.pk,
        }
        with (
            patch.object(
                SourceAuthorFormSet,
                "save",
                side_effect=RuntimeError("inline save failed"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.client.post(self.get_create_url(), post_data)
        self.assertFalse(Source.objects.filter(citation_key="RBS").exists())
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Source),
            ).exists()
        )

    def test_update_source_inline_only_change_runs_in_mutation_boundary(self):
        """An update that only adds an inline SourceAuthor row is a governed
        write: it runs inside the root's content_mutation boundary, so the
        snapshot diff records the created child row, bumps
        ``content_revision`` and writes one ``edited`` audit event."""
        from django.contrib.contenttypes.models import ContentType
        from django.utils import timezone

        from utils.object_management.models import ReviewAction

        source = Source.objects.create(
            owner=self.owner_user,
            publication_status="private",
            title="Inline governed source",
            citation_key="IGS",
            type="misc",
            url="https://example.org/inline",
            last_accessed=timezone.now().date(),
        )
        self.assertEqual(source.content_revision, 1)
        self.client.force_login(self.owner_user)
        post_data = {
            "title": source.title,
            "citation_key": source.citation_key,
            "type": source.type,
            "url": source.url,
            "sourceauthors-TOTAL_FORMS": 1,
            "sourceauthors-INITIAL_FORMS": 0,
            "sourceauthors-0-id": "",
            "sourceauthors-0-source": "",
            "sourceauthors-0-author": self.source_author_1.author.pk,
        }
        response = self.client.post(
            self.get_update_url(source.pk), post_data, follow=True
        )
        self.assertEqual(response.status_code, 200)
        source.refresh_from_db()
        self.assertEqual(source.sourceauthors.count(), 1)
        self.assertEqual(source.content_revision, 2)
        events = ReviewAction.objects.filter(
            content_type=ContentType.objects.get_for_model(Source),
            object_id=source.pk,
            action=ReviewAction.ACTION_EDITED,
        )
        self.assertEqual(events.count(), 1)
        link = source.sourceauthors.get()
        self.assertIn(
            f"bibliography.sourceauthor#{link.pk}:created",
            events.get().changed_fields,
        )

    def test_update_source_post_lock_denial_rolls_back_inline_writes(self):
        """A lifecycle change committed while the view waits on the row lock
        denies the whole mutation: no form update, no inline rows, no audit."""
        from django.contrib.contenttypes.models import ContentType

        from utils.object_management import services
        from utils.object_management.models import ReviewAction

        source = Source.objects.create(
            owner=self.owner_user,
            publication_status="private",
            title="Locked source",
            citation_key="LCK",
            type="misc",
        )
        self.client.force_login(self.owner_user)
        real_lock = services._lock_instance

        def publish_then_lock(obj):
            Source.objects.filter(pk=source.pk).update(publication_status="published")
            return real_lock(obj)

        post_data = {
            "title": "Changed title",
            "citation_key": source.citation_key,
            "type": source.type,
            "sourceauthors-TOTAL_FORMS": 1,
            "sourceauthors-INITIAL_FORMS": 0,
            "sourceauthors-0-id": "",
            "sourceauthors-0-source": "",
            "sourceauthors-0-author": self.source_author_1.author.pk,
        }
        with patch.object(services, "_lock_instance", side_effect=publish_then_lock):
            response = self.client.post(self.get_update_url(source.pk), post_data)
        self.assertEqual(response.status_code, 403)
        source.refresh_from_db()
        self.assertEqual(source.title, "Locked source")
        self.assertEqual(source.content_revision, 1)
        self.assertFalse(SourceAuthor.objects.filter(source=source).exists())
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Source),
                object_id=source.pk,
            ).exists()
        )

    def test_update_source_add_authors(self):
        """
        Test updating a Source that was created with no authors to add one or more authors.
        """
        self.user_with_add_perm.user_permissions.add(
            Permission.objects.get(codename="change_source")
        )
        self.client.force_login(self.user_with_add_perm)
        post_data = self.create_object_data.copy()
        # Create Source with no authors
        related_post_data = {
            "sourceauthors-TOTAL_FORMS": 1,
            "sourceauthors-INITIAL_FORMS": 0,
            "sourceauthors-0-id": "",
            "sourceauthors-0-source": "",
            "sourceauthors-0-author": "",  # No author selected
        }
        post_data.update(related_post_data)
        self.client.post(self.get_create_url(), post_data, follow=True)
        from ..models import Source

        source = Source.objects.latest("pk")
        self.assertEqual(source.sourceauthors.count(), 0)

        # Now update the Source to add two authors
        update_url = self.get_update_url(source.pk)
        update_data = self.update_object_data.copy()
        update_related_post_data = {
            "sourceauthors-TOTAL_FORMS": 2,
            "sourceauthors-INITIAL_FORMS": 0,
            "sourceauthors-0-id": "",
            "sourceauthors-0-source": source.pk,
            "sourceauthors-0-author": self.source_author_1.author.pk,
            "sourceauthors-1-id": "",
            "sourceauthors-1-source": source.pk,
            "sourceauthors-1-author": self.source_author_2.author.pk,
        }
        update_data.update(update_related_post_data)
        self.client.post(update_url, update_data, follow=True)
        source.refresh_from_db()
        self.assertEqual(source.sourceauthors.count(), 2)
        author_ids = set(source.sourceauthors.values_list("author_id", flat=True))
        self.assertSetEqual(
            author_ids, {self.source_author_1.author.pk, self.source_author_2.author.pk}
        )


class SourceReviewListRegressionTest(ViewWithPermissionsTestCase):
    member_permissions = ["can_moderate_source"]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.review_source = Source.objects.create(
            owner=cls.outsider,
            title="Review Source",
            publication_status="review",
        )

    def test_review_list_is_reachable_for_moderator(self):
        self.client.force_login(self.member)

        response = self.client.get(reverse("source-list-review"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.redirect_chain,
            [(f"{reverse('source-list-review')}?scope=review", 302)],
        )
        self.assertContains(response, self.review_source.title)

    def test_row_action_dropdown_escapes_table_scroll_container(self):
        self.client.force_login(self.member)

        response = self.client.get(reverse("source-list-review"), {"scope": "review"})

        self.assertContains(response, self.review_source.title)
        self.assertContains(
            response,
            """data-bs-popper-config='{"strategy":"fixed"}'""",
            html=False,
        )
        self.assertNotContains(response, 'data-bs-container="body"', html=False)

    def test_private_list_uses_dedicated_review_route_for_scope_toggle(self):
        self.client.force_login(self.member)

        response = self.client.get(reverse("source-list-owned"), {"scope": "private"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["review_representation_url"],
            reverse("source-list-review"),
        )
        self.assertContains(
            response,
            f'href="{reverse("source-list-review")}?scope=review"',
            html=False,
        )


class AuthorReviewListRegressionTest(ViewWithPermissionsTestCase):
    member_permissions = ["can_moderate_author"]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.review_author = Author.objects.create(
            owner=cls.outsider,
            first_names="Review",
            last_names="Author",
            publication_status="review",
        )

    def test_review_list_is_reachable_for_moderator(self):
        self.client.force_login(self.member)

        response = self.client.get(reverse("author-list-review"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.redirect_chain,
            [(f"{reverse('author-list-review')}?scope=review", 302)],
        )
        self.assertContains(response, str(self.review_author))

    def test_private_list_uses_dedicated_review_route_for_scope_toggle(self):
        self.client.force_login(self.member)

        response = self.client.get(reverse("author-list-owned"), {"scope": "private"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["review_representation_url"],
            reverse("author-list-review"),
        )
        self.assertContains(
            response,
            f'href="{reverse("author-list-review")}?scope=review"',
            html=False,
        )


class LicenceReviewListRegressionTest(ViewWithPermissionsTestCase):
    member_permissions = ["can_moderate_licence"]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.review_licence = Licence.objects.create(
            owner=cls.outsider,
            name="Review Licence",
            publication_status="review",
        )

    def test_review_list_is_reachable_for_moderator(self):
        self.client.force_login(self.member)

        response = self.client.get(reverse("licence-list-review"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.redirect_chain,
            [(f"{reverse('licence-list-review')}?scope=review", 302)],
        )
        self.assertContains(response, self.review_licence.name)

    def test_private_list_uses_dedicated_review_route_for_scope_toggle(self):
        self.client.force_login(self.member)

        response = self.client.get(reverse("licence-list-owned"), {"scope": "private"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["review_representation_url"],
            reverse("licence-list-review"),
        )
        self.assertContains(
            response,
            f'href="{reverse("licence-list-review")}?scope=review"',
            html=False,
        )


class SourceCheckUrlViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ["can_moderate_source"]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        with mute_signals(post_save):
            cls.source = Source.objects.create(
                title="Test Source from the Web",
                abbreviation="WORKING",
                url="https://httpbin.org/status/200",
                owner=cls.owner,
            )

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        request_url = reverse("source-check-url", kwargs={"pk": self.source.pk})
        response = self.client.get(request_url, follow=True)
        self.assertRedirects(
            response,
            f"{reverse('auth_login')}?next={reverse('source-check-url', kwargs={'pk': self.source.pk})}",
            status_code=302,
            target_status_code=200,
        )

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("source-check-url", kwargs={"pk": self.source.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_owner(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("source-check-url", kwargs={"pk": self.source.pk})
        )
        self.assertEqual(200, response.status_code)

    def test_get_http_200_ok_for_staff(self):
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("source-check-url", kwargs={"pk": self.source.pk})
        )
        self.assertEqual(200, response.status_code)

    def test_get_http_200_ok_for_moderator(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("source-check-url", kwargs={"pk": self.source.pk})
        )
        self.assertEqual(200, response.status_code)

    def test_get_http_404_for_nonexistent_source(self):
        self.client.force_login(self.owner)
        missing_pk = Source.objects.order_by("-pk").values_list("pk", flat=True)[0] + 1
        response = self.client.get(
            reverse("source-check-url", kwargs={"pk": missing_pk})
        )
        self.assertEqual(404, response.status_code)


class SourceAutocompleteViewTestCase(ViewWithPermissionsTestCase):
    def test_owner_review_source_is_returned_when_many_author_join_duplicates_exist(
        self,
    ):
        self.client.force_login(self.member)

        author_1 = Author.objects.create(
            first_names="Alice",
            last_names="Autocomplete",
            publication_status="published",
        )
        author_2 = Author.objects.create(
            first_names="Bob",
            last_names="Autocomplete",
            publication_status="published",
        )

        # Create enough published sources with two authors each so a non-distinct
        # author JOIN would produce more than one page of rows (page_size=10).
        for idx in range(6):
            source = Source.objects.create(
                owner=self.outsider,
                title=f"Query Published {idx}",
                abbreviation=f"QP{idx}",
                publication_status="published",
            )
            SourceAuthor.objects.create(source=source, author=author_1, position=1)
            SourceAuthor.objects.create(source=source, author=author_2, position=2)

        target_source = Source.objects.create(
            owner=self.member,
            title="Query Review Target",
            abbreviation="QRT",
            publication_status="review",
        )

        response = self.client.get(reverse("source-autocomplete"), {"q": "Query"})

        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        returned_ids = [result["id"] for result in results]

        # Regression assertions:
        # 1) no duplicate rows from M2M author joins,
        # 2) owner's in-review source remains discoverable on first page.
        self.assertEqual(len(returned_ids), len(set(returned_ids)))
        self.assertIn(target_source.pk, returned_ids)

    def test_label_abbreviation_returns_short_source_labels(self):
        source = Source.objects.create(
            owner=self.member,
            title="A Rather Long Source Title That Makes Tall Selection Chips",
            abbreviation="SRC1",
            publication_status="published",
        )
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("source-autocomplete"),
            {"q": "Rather Long", "label": "abbreviation"},
        )
        self.assertEqual(response.status_code, 200)
        result = next(r for r in response.json()["results"] if r["id"] == source.pk)
        self.assertEqual(result["label"], "SRC1")
        self.assertEqual(result["text"], "SRC1")
        self.assertEqual(result["selected_text"], "SRC1")

    def test_scope_filter_published_excludes_private_sources_for_staff(self):
        """The source filter widgets send ``f=scope__name=<scope>``. Under the
        published scope, private sources must not be suggested — even to staff,
        who otherwise bypass object visibility checks."""
        private_source = Source.objects.create(
            owner=self.outsider,
            title="Hidden Draft Title",
            publication_status="private",
        )
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("source-autocomplete"),
            {"q": "Hidden Draft", "f": "scope__name=published"},
        )
        self.assertEqual(response.status_code, 200)
        returned_ids = [r["id"] for r in response.json()["results"]]
        self.assertNotIn(private_source.pk, returned_ids)

    def test_scope_filter_private_returns_only_own_sources(self):
        own_source = Source.objects.create(
            owner=self.member,
            title="Own Draft Note",
            publication_status="private",
        )
        foreign_source = Source.objects.create(
            owner=self.outsider,
            title="Foreign Draft Note",
            publication_status="private",
        )
        published_source = Source.objects.create(
            owner=self.outsider,
            title="Draft Published Elsewhere",
            publication_status="published",
        )
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("source-autocomplete"),
            {"q": "Draft", "f": "scope__name=private"},
        )
        self.assertEqual(response.status_code, 200)
        returned_ids = [r["id"] for r in response.json()["results"]]
        self.assertIn(own_source.pk, returned_ids)
        self.assertNotIn(foreign_source.pk, returned_ids)
        self.assertNotIn(published_source.pk, returned_ids)

    def test_scope_filter_review_hides_other_users_review_items(self):
        own_review = Source.objects.create(
            owner=self.member,
            title="Review Item Mine",
            publication_status="review",
        )
        foreign_review = Source.objects.create(
            owner=self.outsider,
            title="Review Item Theirs",
            publication_status="review",
        )
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("source-autocomplete"),
            {"q": "Review Item", "f": "scope__name=review"},
        )
        self.assertEqual(response.status_code, 200)
        returned_ids = [r["id"] for r in response.json()["results"]]
        self.assertIn(own_review.pk, returned_ids)
        self.assertNotIn(foreign_review.pk, returned_ids)


class SourceListCheckUrlsViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ["change_source"]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        with mute_signals(post_save):
            Source.objects.create(
                title="Test Source from the Web",
                abbreviation="WORKING",
                url="https://httpbin.org/status/200",
            )
            Source.objects.create(
                title="Test Source from the Web",
                abbreviation="NOTWORKING",
                url="https://httpbin.org/status/404",
            )
            Source.objects.create(
                title="Test Source from the Web",
                abbreviation="NOTWORKING",
                url="https://httpbin.org/status/404",
            )

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        request_url = f"{reverse('source-list-check-urls')}?url_valid=False"
        response = self.client.get(request_url, follow=True)
        self.assertRedirects(
            response, f"{reverse('auth_login')}?next={request_url}", status_code=302
        )

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        request_url = f"{reverse('source-list-check-urls')}?url_valid=False"
        response = self.client.get(request_url)
        self.assertEqual(response.status_code, 403)

    @patch("bibliography.views.check_source_urls.delay")
    def test_get_http_200_ok_for_members(self, mock_delay):
        mock_task = mock_delay.return_value
        mock_task.task_id = "scheduler-task-id"
        self.client.force_login(self.member)
        request_url = f"{reverse('source-list-check-urls')}?url_valid=False&page=1"
        response = self.client.get(request_url)
        self.assertEqual(200, response.status_code)
        mock_delay.assert_called_once()
        self.assertEqual(response.json()["task_id"], "scheduler-task-id")


class SourceQuickCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ["add_source"]

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        response = self.client.post(
            reverse("source-quick-create"),
            data=json.dumps({"title": "Inline source"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_authenticated_without_permission(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse("source-quick-create"),
            data=json.dumps({"title": "Inline source"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_400_bad_request_when_title_is_blank(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("source-quick-create"),
            data=json.dumps({"title": "   "}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_post_http_201_creates_source_for_member(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("source-quick-create"),
            data=json.dumps({"title": "Inline source"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        source = Source.objects.get(pk=payload["id"])

        self.assertEqual(source.title, "Inline source")
        self.assertEqual(source.owner, self.member)
        self.assertEqual(source.type, "misc")
        self.assertEqual(payload["title"], "Inline source")

    def test_post_http_400_when_year_is_invalid(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("source-quick-create"),
            data=json.dumps({"title": "Inline source", "year": "not-a-year"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_post_http_403_when_new_author_payload_without_add_author_permission(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("source-quick-create"),
            data=json.dumps(
                {
                    "title": "Inline source",
                    "authors": [{"first_names": "Ada", "last_names": "Lovelace"}],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_201_creates_source_with_existing_author_and_year(self):
        self.client.force_login(self.member)
        author = Author.objects.create(
            owner=self.member,
            first_names="Ada",
            last_names="Lovelace",
        )

        response = self.client.post(
            reverse("source-quick-create"),
            data=json.dumps(
                {
                    "title": "Inline source",
                    "year": 2024,
                    "authors": [{"id": author.pk}],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        source = Source.objects.get(pk=payload["id"])

        self.assertEqual(source.year, 2024)
        self.assertEqual(source.sourceauthors.count(), 1)
        source_author = source.sourceauthors.first()
        self.assertEqual(source_author.author_id, author.pk)
        self.assertEqual(source_author.position, 1)
        self.assertEqual(payload["label"], "Lovelace, A.. Inline source")

    def test_post_skips_letterless_inline_authors(self):
        add_author_permission = Permission.objects.get(codename="add_author")
        self.member.user_permissions.add(add_author_permission)
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("source-quick-create"),
            data=json.dumps(
                {
                    "title": "Inline source",
                    "authors": [
                        {"first_names": "", "last_names": "70"},
                        {
                            "author_type": "organization",
                            "organization_name": "30.379",
                        },
                        {"first_names": "Ada", "last_names": "Lovelace"},
                    ],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        source = Source.objects.get(pk=response.json()["id"])
        self.assertEqual(
            list(source.authors.values_list("last_names", flat=True)), ["Lovelace"]
        )
        self.assertFalse(Author.objects.filter(last_names="70").exists())
        self.assertFalse(Author.objects.filter(organization_name="30.379").exists())

    def test_post_http_201_creates_source_and_new_author_when_permitted(self):
        add_author_permission = Permission.objects.get(codename="add_author")
        self.member.user_permissions.add(add_author_permission)
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("source-quick-create"),
            data=json.dumps(
                {
                    "title": "Inline source",
                    "authors": [{"first_names": "Ada", "last_names": "Lovelace"}],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        source = Source.objects.get(pk=payload["id"])

        self.assertEqual(source.sourceauthors.count(), 1)
        created_author = source.sourceauthors.first().author
        self.assertEqual(created_author.first_names, "Ada")
        self.assertEqual(created_author.last_names, "Lovelace")

    def test_failed_source_creation_does_not_leave_orphan_authors(self):
        """Inline authors must not persist when the source create fails."""
        add_author_permission = Permission.objects.get(codename="add_author")
        self.member.user_permissions.add(add_author_permission)
        self.client.force_login(self.member)

        with patch.object(Source.objects, "create") as mock_create:
            mock_create.side_effect = RuntimeError("simulated failure")
            with (
                self.assertLogs("django.request", level="ERROR"),
                self.assertRaises(RuntimeError),
            ):
                self.client.post(
                    reverse("source-quick-create"),
                    data=json.dumps(
                        {
                            "title": "Inline source",
                            "authors": [
                                {"first_names": "Ada", "last_names": "Lovelace"}
                            ],
                        }
                    ),
                    content_type="application/json",
                )

        self.assertFalse(Author.objects.filter(last_names="Lovelace").exists())
        self.assertEqual(Source.objects.count(), 0)

    def test_author_error_rolls_back_authors_created_earlier_in_request(self):
        add_author_permission = Permission.objects.get(codename="add_author")
        self.member.user_permissions.add(add_author_permission)
        self.client.force_login(self.member)

        add_author_checks = []

        def has_perm_revoked_after_first_author(user, perm, obj=None):
            if perm != "bibliography.add_author":
                return True
            add_author_checks.append(perm)
            return len(add_author_checks) == 1

        with patch.object(
            User,
            "has_perm",
            autospec=True,
            side_effect=has_perm_revoked_after_first_author,
        ):
            response = self.client.post(
                reverse("source-quick-create"),
                data=json.dumps(
                    {
                        "title": "Inline source",
                        "authors": [
                            {"first_names": "Ada", "last_names": "Lovelace"},
                            {"first_names": "Grace", "last_names": "Hopper"},
                        ],
                    }
                ),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Author.objects.filter(last_names="Lovelace").exists())
        self.assertEqual(Source.objects.count(), 0)

    def test_post_http_201_creates_source_with_new_organisation_author(self):
        add_author_permission = Permission.objects.get(codename="add_author")
        self.member.user_permissions.add(add_author_permission)
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("source-quick-create"),
            data=json.dumps(
                {
                    "title": "Inline source",
                    "authors": [
                        {
                            "author_type": "organization",
                            "organization_name": "European Environment Agency",
                        }
                    ],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        source = Source.objects.get(pk=payload["id"])

        self.assertEqual(source.sourceauthors.count(), 1)
        created_author = source.sourceauthors.first().author
        self.assertEqual(created_author.author_type, "organization")
        self.assertEqual(
            created_author.organization_name, "European Environment Agency"
        )

    def test_post_http_201_creates_source_with_mixed_new_authors(self):
        add_author_permission = Permission.objects.get(codename="add_author")
        self.member.user_permissions.add(add_author_permission)
        self.client.force_login(self.member)

        response = self.client.post(
            reverse("source-quick-create"),
            data=json.dumps(
                {
                    "title": "Inline source",
                    "authors": [
                        {"first_names": "Ada", "last_names": "Lovelace"},
                        {
                            "author_type": "organization",
                            "organization_name": "European Environment Agency",
                        },
                    ],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        source = Source.objects.get(pk=response.json()["id"])
        self.assertEqual(source.sourceauthors.count(), 2)

        person_author = source.sourceauthors.get(position=1).author
        self.assertEqual(person_author.author_type, "person")
        self.assertEqual(person_author.last_names, "Lovelace")

        organisation_author = source.sourceauthors.get(position=2).author
        self.assertEqual(organisation_author.author_type, "organization")
        self.assertEqual(
            organisation_author.organization_name, "European Environment Agency"
        )

    def test_delete_http_302_redirect_to_login_for_anonymous(self):
        self.client.force_login(self.member)
        source = Source.objects.create(owner=self.member, title="To delete")
        self.client.logout()

        response = self.client.delete(
            reverse("source-quick-create"),
            data=json.dumps({"id": source.pk}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 302)

    def test_delete_http_200_owner_can_delete_own_unpublished_source(self):
        self.client.force_login(self.member)
        source = Source.objects.create(owner=self.member, title="To delete")

        response = self.client.delete(
            reverse("source-quick-create"),
            data=json.dumps({"id": source.pk}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Source.objects.filter(pk=source.pk).exists())

    def _quick_create_with_authors(self, authors, title="Inline source"):
        response = self.client.post(
            reverse("source-quick-create"),
            data=json.dumps({"title": title, "authors": authors}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def _quick_delete(self, payload):
        return self.client.delete(
            reverse("source-quick-create"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_delete_with_cleanup_token_removes_authors_created_with_source(self):
        self.member.user_permissions.add(Permission.objects.get(codename="add_author"))
        self.client.force_login(self.member)
        existing = Author.objects.create(
            owner=self.member, first_names="Grace", last_names="Hopper"
        )
        created = self._quick_create_with_authors(
            [{"id": existing.pk}, {"first_names": "Ada", "last_names": "Lovelace"}]
        )

        response = self._quick_delete(
            {
                "id": created["id"],
                "author_cleanup_token": created["author_cleanup_token"],
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Source.objects.filter(pk=created["id"]).exists())
        self.assertFalse(Author.objects.filter(last_names="Lovelace").exists())
        self.assertTrue(Author.objects.filter(pk=existing.pk).exists())

    def test_delete_keeps_created_author_unlinked_from_source_beforehand(self):
        self.member.user_permissions.add(Permission.objects.get(codename="add_author"))
        self.client.force_login(self.member)
        created = self._quick_create_with_authors(
            [{"first_names": "Ada", "last_names": "Lovelace"}]
        )
        SourceAuthor.objects.filter(source_id=created["id"]).delete()

        response = self._quick_delete(
            {
                "id": created["id"],
                "author_cleanup_token": created["author_cleanup_token"],
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Author.objects.filter(last_names="Lovelace").exists())

    def test_delete_accepts_cleanup_token_older_than_a_day(self):
        self.member.user_permissions.add(Permission.objects.get(codename="add_author"))
        self.client.force_login(self.member)
        three_days_ago = signing.b62_encode(int(time.time()) - 3 * 86400)
        with patch.object(
            signing.TimestampSigner, "timestamp", return_value=three_days_ago
        ):
            created = self._quick_create_with_authors(
                [{"first_names": "Ada", "last_names": "Lovelace"}]
            )

        response = self._quick_delete(
            {
                "id": created["id"],
                "author_cleanup_token": created["author_cleanup_token"],
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Author.objects.filter(last_names="Lovelace").exists())

    def test_delete_keeps_created_authors_still_used_by_a_source_or_process(self):
        from processes.models import Process, ProcessAuthor

        self.member.user_permissions.add(Permission.objects.get(codename="add_author"))
        self.client.force_login(self.member)
        created = self._quick_create_with_authors(
            [
                {"first_names": "Ada", "last_names": "Lovelace"},
                {"first_names": "Grace", "last_names": "Hopper"},
            ]
        )
        other_source = Source.objects.create(owner=self.member, title="Other")
        other_source.sourceauthors.create(
            author=Author.objects.get(last_names="Lovelace"), position=1
        )
        process = Process.objects.create(name="Process", owner=self.member)
        ProcessAuthor.objects.create(
            process=process, author=Author.objects.get(last_names="Hopper")
        )

        response = self._quick_delete(
            {
                "id": created["id"],
                "author_cleanup_token": created["author_cleanup_token"],
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Source.objects.filter(pk=created["id"]).exists())
        self.assertTrue(Author.objects.filter(last_names="Lovelace").exists())
        self.assertTrue(Author.objects.filter(last_names="Hopper").exists())

    def test_delete_ignores_author_ids_without_a_matching_cleanup_token(self):
        self.member.user_permissions.add(Permission.objects.get(codename="add_author"))
        self.client.force_login(self.member)
        first = self._quick_create_with_authors(
            [{"first_names": "Ada", "last_names": "Lovelace"}], title="First"
        )
        second = Source.objects.create(owner=self.member, title="Second")
        unrelated = Author.objects.create(
            owner=self.member, first_names="Grace", last_names="Hopper"
        )

        forged = self._quick_delete(
            {
                "id": second.pk,
                "author_ids": [unrelated.pk],
                "author_cleanup_token": first["author_cleanup_token"],
            }
        )
        tampered = self._quick_delete(
            {"id": first["id"], "author_cleanup_token": "not-a-valid-token"}
        )

        self.assertEqual(forged.status_code, 200)
        self.assertEqual(tampered.status_code, 200)
        self.assertFalse(
            Source.objects.filter(pk__in=[first["id"], second.pk]).exists()
        )
        self.assertTrue(Author.objects.filter(pk=unrelated.pk).exists())
        self.assertTrue(Author.objects.filter(last_names="Lovelace").exists())

    def test_delete_keeps_authors_when_no_cleanup_token_is_sent(self):
        self.client.force_login(self.member)
        source = Source.objects.create(owner=self.member, title="To delete")
        author = Author.objects.create(
            owner=self.member, first_names="Ada", last_names="Lovelace"
        )
        source.sourceauthors.create(author=author, position=1)

        response = self.client.delete(
            reverse("source-quick-create"),
            data=json.dumps({"id": source.pk}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Author.objects.filter(pk=author.pk).exists())

    def test_delete_http_404_cannot_delete_another_users_source(self):
        self.client.force_login(self.member)
        other_source = Source.objects.create(owner=self.outsider, title="Other source")

        response = self.client.delete(
            reverse("source-quick-create"),
            data=json.dumps({"id": other_source.pk}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Source.objects.filter(pk=other_source.pk).exists())

    def test_delete_http_403_cannot_delete_published_source(self):
        self.client.force_login(self.member)
        source = Source.objects.create(
            owner=self.member,
            title="Published source",
            publication_status="published",
        )

        response = self.client.delete(
            reverse("source-quick-create"),
            data=json.dumps({"id": source.pk}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Source.objects.filter(pk=source.pk).exists())

    def test_delete_http_400_when_id_is_missing(self):
        self.client.force_login(self.member)

        response = self.client.delete(
            reverse("source-quick-create"),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)


class OrganizationAuthorDetailViewTestCase(ViewWithPermissionsTestCase):
    """Organization authors must render their organization fields on detail pages."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.organization_author = Author.objects.create(
            owner=cls.member,
            author_type="organization",
            organization_name="European Environment Agency",
            organization_abbreviation="EEA",
            publication_status="published",
        )

    def test_detail_view_shows_organization_name(self):
        url = reverse("author-detail", kwargs={"pk": self.organization_author.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "European Environment Agency")
        self.assertContains(response, "Organization")

    def test_detail_view_shows_organization_abbreviation(self):
        url = reverse("author-detail", kwargs={"pk": self.organization_author.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "EEA")

    def test_modal_detail_view_shows_organization_name(self):
        url = reverse("author-detail-modal", kwargs={"pk": self.organization_author.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "European Environment Agency")
        self.assertContains(response, "Organization")
