"""HTTP transport tests for revision-bound review actions.

Covers the normal HTML review path, the approve modal GET/POST contract,
the review-queue and comment APIs, and protected write-payload fields.
"""

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from utils.properties.models import Property, Unit

from ..models import ReviewAction


def _perm(model, codename):
    return Permission.objects.get(
        codename=codename, content_type=ContentType.objects.get_for_model(model)
    )


def _ct(obj):
    return ContentType.objects.get_for_model(obj.__class__)


def _actions_for(obj, action=None):
    qs = ReviewAction.objects.filter(content_type=_ct(obj), object_id=obj.pk)
    if action is not None:
        qs = qs.filter(action=action)
    return qs


class RevisionHttpBase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="http-owner")
        self.owner.user_permissions.add(
            _perm(Property, "add_property"),
            _perm(Property, "change_property"),
            _perm(Property, "delete_property"),
        )
        self.moderator = User.objects.create_user(username="http-moderator")
        self.moderator.user_permissions.add(_perm(Property, "can_moderate_property"))
        self.prop = Property.objects.create(
            name="HTTP Property", owner=self.owner, publication_status="review"
        )
        self.ct = _ct(self.prop)

    def _url(self, name, **kwargs):
        base = {"content_type_id": self.ct.pk, "object_id": self.prop.pk}
        base.update(kwargs)
        return reverse(f"object_management:{name}", kwargs=base)


class HtmlApproveTests(RevisionHttpBase):
    def test_approve_post_without_revision_denied(self):
        self.client.force_login(self.moderator)
        response = self.client.post(self._url("approve_item"))
        self.assertEqual(response.status_code, 302)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.publication_status, "review")
        self.assertFalse(_actions_for(self.prop, "approved").exists())

    def test_approve_post_with_malformed_revision_denied(self):
        self.client.force_login(self.moderator)
        for bad in ("abc", "true", "-1"):
            self.client.post(self._url("approve_item"), {"expected_revision": bad})
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.publication_status, "review")

    def test_approve_post_with_current_revision_publishes(self):
        self.client.force_login(self.moderator)
        response = self.client.post(
            self._url("approve_item"),
            {"expected_revision": self.prop.content_revision},
        )
        self.assertEqual(response.status_code, 302)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.publication_status, "published")
        event = _actions_for(self.prop, "approved").get()
        self.assertEqual(event.content_revision, 1)

    def test_stale_approval_shows_reload_error(self):
        self.client.force_login(self.moderator)
        inspected = self.prop.content_revision
        self.prop.name = "renamed"
        self.prop.content_revision += 1
        self.prop.save(update_fields=["name", "content_revision"])
        response = self.client.post(
            self._url("approve_item"), {"expected_revision": inspected}
        )
        self.assertEqual(response.status_code, 302)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.publication_status, "review")
        messages = [str(m) for m in response.wsgi_request._messages]
        self.assertTrue(
            any("Reload the review" in message for message in messages),
            messages,
        )


class ApproveModalTests(RevisionHttpBase):
    def test_modal_without_revision_offers_no_approval(self):
        self.client.force_login(self.moderator)
        response = self.client.get(self._url("approve_item_modal"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn('name="expected_revision"', content)
        self.assertIn("inspected revision", content)

    def test_modal_preserves_rendered_revision(self):
        self.client.force_login(self.moderator)
        inspected = self.prop.content_revision
        self.prop.name = "renamed"
        self.prop.content_revision += 1
        self.prop.save(update_fields=["name", "content_revision"])
        response = self.client.get(
            self._url("approve_item_modal"), {"expected_revision": inspected}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(f'name="expected_revision" value="{inspected}"', content)
        self.assertNotIn(
            f'name="expected_revision" value="{self.prop.content_revision}"',
            content,
        )

    def test_modal_post_with_stale_revision_fails(self):
        self.client.force_login(self.moderator)
        inspected = self.prop.content_revision
        self.prop.name = "renamed"
        self.prop.content_revision += 1
        self.prop.save(update_fields=["name", "content_revision"])
        response = self.client.post(
            self._url("approve_item"), {"expected_revision": inspected}
        )
        self.assertEqual(response.status_code, 302)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.publication_status, "review")


class ReviewDetailTransportTests(RevisionHttpBase):
    def test_approve_link_carries_rendered_revision(self):
        self.client.force_login(self.moderator)
        response = self.client.get(self._url("review_item_detail"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            f"expected_revision={self.prop.content_revision}",
            response.content.decode(),
        )

    def test_comment_post_binds_watermark(self):
        self.client.force_login(self.moderator)
        response = self.client.post(
            self._url("add_review_comment"),
            {
                "message": "reviewed",
                "expected_revision": self.prop.content_revision,
            },
        )
        self.assertEqual(response.status_code, 302)
        action = _actions_for(self.prop, "comment").get()
        self.assertEqual(action.content_revision, self.prop.content_revision)

    def test_comment_post_without_watermark_unbound(self):
        self.client.force_login(self.moderator)
        self.client.post(self._url("add_review_comment"), {"message": "unbound note"})
        action = _actions_for(self.prop, "comment").get()
        self.assertIsNone(action.content_revision)


class ReviewApiTests(RevisionHttpBase):
    def test_comment_api_binds_expected_revision(self):
        self.client.force_login(self.moderator)
        response = self.client.post(
            self._url("api_add_review_comment"),
            data={
                "comment": "api note",
                "expected_revision": self.prop.content_revision,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json()["content_revision"], self.prop.content_revision
        )

    def test_comment_api_rejects_future_watermark(self):
        self.client.force_login(self.moderator)
        response = self.client.post(
            self._url("api_add_review_comment"),
            data={"comment": "x", "expected_revision": 99},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_queue_api_exposes_revisions(self):
        self.client.force_login(self.moderator)
        response = self.client.get(reverse("object_management:api_review_queue"))
        self.assertEqual(response.status_code, 200)
        results = {item["object_id"]: item for item in response.json()["results"]}
        item = results[self.prop.pk]
        self.assertEqual(item["content_revision"], self.prop.content_revision)
        self.assertIsNone(item["my_last_reviewed_revision"])

        self.client.post(
            self._url("api_add_review_comment"),
            data={
                "comment": "bound",
                "expected_revision": self.prop.content_revision,
            },
            content_type="application/json",
        )
        response = self.client.get(reverse("object_management:api_review_queue"))
        item = {entry["object_id"]: entry for entry in response.json()["results"]}[
            self.prop.pk
        ]
        self.assertEqual(item["my_last_reviewed_revision"], self.prop.content_revision)


class ProtectedPayloadTests(RevisionHttpBase):
    def test_html_update_cannot_forge_protected_fields(self):
        unit = Unit.objects.create(name="kg", symbol="kg", owner=self.owner)
        self.prop.publication_status = "private"
        self.prop.save(update_fields=["publication_status"])
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("property-update", kwargs={"pk": self.prop.pk}),
            {
                "name": "Forged",
                "description": "valid content edit",
                "allowed_units": [unit.pk],
                "owner": self.moderator.pk,
                "publication_status": "published",
                "content_revision": 99,
                "approved_by": self.moderator.pk,
            },
        )
        self.assertIn(response.status_code, (302, 403))
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.owner, self.owner)
        self.assertEqual(self.prop.publication_status, "private")
        self.assertEqual(self.prop.content_revision, 2)
        self.assertIsNone(self.prop.approved_by)

    def test_review_state_html_update_bumps_once_then_stale_approval_denied(self):
        unit = Unit.objects.create(name="kg", symbol="kg", owner=self.owner)
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("property-update", kwargs={"pk": self.prop.pk}),
            {
                "name": "Renamed once",
                "description": "content",
                "allowed_units": [unit.pk],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.publication_status, "review")
        self.assertEqual(self.prop.name, "Renamed once")
        self.assertEqual(self.prop.content_revision, 2)
        events = _actions_for(self.prop, "edited")
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.get().content_revision, 2)

        self.client.force_login(self.moderator)
        response = self.client.post(self._url("approve_item"), {"expected_revision": 1})
        self.assertEqual(response.status_code, 302)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.publication_status, "review")
        self.assertFalse(_actions_for(self.prop, "approved").exists())

    def test_modal_binds_revision_zero(self):
        self.client.force_login(self.moderator)
        Property.objects.filter(pk=self.prop.pk).update(content_revision=0)
        self.prop.refresh_from_db()
        response = self.client.get(
            self._url("approve_item_modal"), {"expected_revision": 0}
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('name="expected_revision" value="0"', content)
