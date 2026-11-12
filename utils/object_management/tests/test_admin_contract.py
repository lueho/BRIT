"""Admin adapter contract: policy-governed admin surfaces honor the
canonical authorization boundary, never staff shortcuts."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from bibliography.models import Author, Source
from utils.object_management.models import ReviewAction
from utils.tests.testcases import ensure_test_default_owner


def _source_ct():
    return ContentType.objects.get_for_model(Source)


class AdminPolicyFixture(TestCase):
    """Personas: registered contributor + staff-eligible writer, non-staff
    app admin (``administer_objects`` + model caps), pure staff, inactive."""

    @classmethod
    def setUpTestData(cls):
        cls._role_output = StringIO()
        with redirect_stdout(cls._role_output), redirect_stderr(cls._role_output):
            call_command("sync_roles", "--apply", stdout=cls._role_output)

    def setUp(self):
        ensure_test_default_owner()
        self.owner = User.objects.create_user(username="adm-owner", is_staff=True)
        self.writer = User.objects.create_user(username="adm-writer")
        self.writer.is_staff = True
        self.writer.save()
        self.admin = User.objects.create_user(username="adm-admin", is_staff=True)
        self.admin.user_permissions.add(
            Permission.objects.get(codename="administer_objects")
        )
        self.staff = User.objects.create_user(username="adm-staff", is_staff=True)
        self.staff.groups.clear()
        self.staff.user_permissions.clear()
        # App administration is NOT site eligibility: a non-staff actor with
        # administer_objects still cannot enter the admin site.
        self.nonstaff_admin = User.objects.create_user(
            username="adm-nonstaff-admin", is_staff=False
        )
        self.nonstaff_admin.user_permissions.add(
            Permission.objects.get(codename="administer_objects")
        )
        # Inactive staff+administrator must be denied on both gates.
        self.inactive_admin = User.objects.create_user(
            username="adm-inactive-admin", is_staff=True, is_active=False
        )
        self.inactive_admin.user_permissions.add(
            Permission.objects.get(codename="administer_objects")
        )
        self.foreign_private = Source.objects.create(
            owner=self.owner,
            title="Foreign private",
            publication_status="private",
        )
        self.owner_review = Source.objects.create(
            owner=self.owner,
            title="Owner review",
            publication_status="review",
        )
        self.ct = _source_ct()

    def _admin_url(self, model, action, pk=None):
        name = f"admin:{model._meta.app_label}_{model._meta.model_name}_{action}"
        kwargs = {"object_id": pk} if pk is not None else {}
        return reverse(name, kwargs=kwargs)


class AdminAccessContractTests(AdminPolicyFixture):
    """The governed admin honors the same canonical decisions as every
    other adapter — staff status is admission, not authority."""

    def test_foreign_private_change_denied(self):
        self.client.force_login(self.staff)
        response = self.client.get(
            self._admin_url(Source, "change", self.foreign_private.pk)
        )
        # Staff admission without a visible object must not reveal it.
        self.assertIn(response.status_code, (302, 403, 404))

    def test_owner_review_edit_keeps_review_and_bumps_once(self):
        self.client.force_login(self.owner)
        before_rev = self.owner_review.content_revision
        # The admin changeform accepts the edit through the policy boundary.
        self.client.post(
            self._admin_url(Source, "change", self.owner_review.pk),
            data=self._changeform_payload(self.owner_review, title="Renamed"),
        )
        self.owner_review.refresh_from_db()
        self.assertEqual(self.owner_review.publication_status, "review")
        self.assertEqual(self.owner_review.content_revision, before_rev + 1)
        self.assertTrue(
            ReviewAction.objects.filter(
                content_type=self.ct,
                object_id=self.owner_review.pk,
                action="edited",
            ).exists()
        )

    def test_nonstaff_app_admin_denied_at_site(self):
        self.client.force_login(self.nonstaff_admin)
        response = self.client.get(self._admin_url(Source, "changelist"), follow=False)
        # Not staff -> redirected to the admin login, never 200.
        self.assertIn(response.status_code, (302, 403))
        if response.status_code == 302:
            self.assertIn("login", response.url)

    def test_inactive_admin_denied(self):
        self.client.force_login(self.inactive_admin)
        response = self.client.get(self._admin_url(Source, "changelist"), follow=False)
        self.assertIn(response.status_code, (302, 403))

    def _changeform_payload(self, obj, **changes):
        payload = {
            "title": getattr(obj, "title", ""),
            "citation_key": getattr(obj, "citation_key", ""),
            "type": "misc",
            "licence": "",
            "sourceauthors-TOTAL_FORMS": "0",
            "sourceauthors-INITIAL_FORMS": "0",
            "sourceauthors-MIN_NUM_FORMS": "0",
            "sourceauthors-MAX_NUM_FORMS": "1000",
            "_save": "Save",
        }
        payload.update(changes)
        return payload

    def test_metadata_owner_status_readonly(self):
        self.client.force_login(self.owner)
        before_rev = self.owner_review.content_revision
        # An otherwise-valid payload carrying forged metadata: the post
        # succeeds on the content fields while owner/status are never taken
        # from the form.
        response = self.client.post(
            self._admin_url(Source, "change", self.owner_review.pk),
            data=self._changeform_payload(
                self.owner_review,
                title="Still mine",
                owner=str(self.staff.pk),
                publication_status="published",
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.owner_review.refresh_from_db()
        self.assertEqual(self.owner_review.title, "Still mine")
        self.assertEqual(self.owner_review.owner, self.owner)
        self.assertEqual(self.owner_review.publication_status, "review")
        self.assertEqual(self.owner_review.content_revision, before_rev + 1)

    def test_bulk_action_confirm_does_not_delete(self):
        self.client.force_login(self.admin)
        self.client.post(
            self._admin_url(Source, "changelist"),
            data={
                "action": "delete_selected",
                "_selected_action": [str(self.foreign_private.pk)],
            },
        )
        # Confirmation rendered; nothing deleted yet.
        self.assertTrue(Source.objects.filter(pk=self.foreign_private.pk).exists())

    def test_reviewaction_immutable_even_for_superuser(self):
        superuser = User.objects.create_user(
            username="adm-super", is_staff=True, is_superuser=True
        )
        self.client.force_login(superuser)
        # A posted reviewaction change must not mutate the audit row.
        event = ReviewAction.objects.create(
            content_type=self.ct,
            object_id=self.foreign_private.pk,
            action="created",
            user=self.owner,
        )
        self.client.post(
            self._admin_url(ReviewAction, "change", event.pk),
            data={"action": "deleted", "_save": "Save"},
        )
        event.refresh_from_db()
        self.assertEqual(event.action, "created")


class AdminOwnedInlineContractTests(AdminPolicyFixture):
    """Owned inline rows inherit the parent's decision — no child grants."""

    def test_source_add_with_author_row_parent_governed(self):
        # A registered contributor (registered-role create_source) posts a
        # Source + one SourceAuthor inline through the compound addform.
        author = Author.objects.create(
            owner=self.owner,
            first_names="Ada",
            last_names="Tester",
            publication_status="private",
        )
        self.client.force_login(self.owner)
        self.client.post(
            self._admin_url(Source, "add"),
            data={
                "title": "Compound",
                "citation_key": "compound-1",
                "type": "misc",
                "licence": "",
                "sourceauthors-TOTAL_FORMS": "1",
                "sourceauthors-INITIAL_FORMS": "0",
                "sourceauthors-0-id": "",
                "sourceauthors-0-author": str(author.pk),
                "sourceauthors-0-position": "1",
                "_save": "Save",
            },
        )
        source = Source.objects.filter(citation_key="compound-1").first()
        self.assertIsNotNone(source)
        self.assertEqual(source.owner, self.owner)
        self.assertEqual(source.publication_status, "private")
        self.assertTrue(source.sourceauthors.filter(author=author).exists())
