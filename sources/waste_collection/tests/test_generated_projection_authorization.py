"""Authorization contract tests for source-bound generated projections.

Read and lifecycle eligibility on a projection always resolves through the
bound source row; copied metadata (status, owner) never grants access and
the projection surface is read-only for every actor. Fixture data reuses the
lead-authored synthetic numeric contract module via a module import.
"""

from decimal import Decimal
from io import StringIO

from django.contrib import admin
from django.contrib.auth.models import AnonymousUser, Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase
from django.urls import reverse

from sources.waste_collection.derived_values import create_or_update_derived_cpv
from sources.waste_collection.forms import CollectionPropertyValueModelForm
from sources.waste_collection.models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionPropertyValue,
)
from sources.waste_collection.serializers import CollectionPropertyValueSerializer
from sources.waste_collection.tests import (
    test_generated_pipeline_numeric as numeric_contracts,
)
from utils.object_management.models import ObjectEditorGrant, ReviewAction
from utils.object_management.permissions import get_object_policy
from utils.object_management.policy import (
    decide,
    scope_queryset,
    visible_queryset,
)
from utils.object_management.services import (
    content_mutation,
    perform_transition,
    record_comment,
)
from utils.properties.models import Property
from utils.tests.testcases import ensure_test_default_owner


class GeneratedProjectionAuthorizationTests(TestCase):
    _raw = numeric_contracts.GeneratedPipelineNumericalTests._raw
    _assert_output = numeric_contracts.GeneratedPipelineNumericalTests._assert_output

    @classmethod
    def setUpTestData(cls):
        ensure_test_default_owner()
        call_command("sync_roles", "--apply", stdout=StringIO())
        numeric_contracts.GeneratedPipelineNumericalTests.setUpTestData.__func__(cls)
        cls.app_admin = User.objects.create_user("acl-app-admin")
        cls.app_admin.user_permissions.add(
            Permission.objects.get(codename="administer_objects")
        )
        cls.superuser = User.objects.create_superuser(
            "acl-super", password="x", email="acl-super@example.com"
        )

    def setUp(self):
        numeric_contracts.GeneratedPipelineNumericalTests.setUp(self)
        self.source = self._raw(
            self.specific, self.specific_unit, "150", state="private"
        )
        self.projection = create_or_update_derived_cpv(
            self.source, owner=self.stranger, publication_status="published"
        )[0]

    def _cpv_qs(self):
        return CollectionPropertyValue.objects.all()

    def _snapshot(self):
        return (
            list(
                CollectionPropertyValue.objects.filter(
                    pk__in=[self.source.pk, self.projection.pk]
                )
                .order_by("pk")
                .values()
            ),
            list(ReviewAction.objects.order_by("pk").values()),
        )

    def _set_source_state(self, state):
        CollectionPropertyValue.objects.filter(pk=self.source.pk).update(
            publication_status=state
        )
        self.source.refresh_from_db()
        self.projection.refresh_from_db()

    # -- 1: read surface follows the bound source row --------------------

    def test_source_owner_reads_projection_regardless_of_copied_metadata(self):
        self.assertTrue(decide(self.owner, "read", self.projection).allowed)
        self.assertTrue(
            visible_queryset(self.owner, self._cpv_qs())
            .filter(pk=self.projection.pk)
            .exists()
        )

    def test_anonymous_and_stranger_cannot_read_private_source_projection(self):
        for actor in (AnonymousUser(), self.stranger):
            with self.subTest(actor=actor):
                self.assertFalse(decide(actor, "read", self.projection).allowed)
                self.assertFalse(
                    visible_queryset(actor, self._cpv_qs())
                    .filter(pk=self.projection.pk)
                    .exists()
                )

    def test_collection_ownership_never_grants_foreign_private_cpv_read(self):
        CollectionPropertyValue.objects.filter(pk=self.source.pk).update(
            owner_id=self.stranger.pk
        )
        CollectionPropertyValue.objects.filter(pk=self.projection.pk).update(
            owner_id=self.owner.pk
        )
        self.source.refresh_from_db()
        self.projection.refresh_from_db()
        self.assertFalse(decide(self.owner, "read", self.projection).allowed)
        self.assertFalse(
            visible_queryset(self.owner, self._cpv_qs())
            .filter(pk=self.projection.pk)
            .exists()
        )

    def test_public_source_projection_is_publicly_readable(self):
        CollectionPropertyValue.objects.filter(pk=self.projection.pk).update(
            publication_status="private"
        )
        self.projection.refresh_from_db()
        self._set_source_state("published")
        self.assertTrue(decide(AnonymousUser(), "read", self.projection).allowed)
        self.assertTrue(
            visible_queryset(AnonymousUser(), self._cpv_qs())
            .filter(pk=self.projection.pk)
            .exists()
        )
        self.assertTrue(
            scope_queryset(AnonymousUser(), self._cpv_qs(), "published")
            .filter(pk=self.projection.pk)
            .exists()
        )
        response = self.client.get(
            reverse(
                "collectionpropertyvalue-detail",
                kwargs={"pk": self.projection.pk},
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_archived_source_readable_but_out_of_published_scope(self):
        self._set_source_state("archived")
        self.assertTrue(decide(AnonymousUser(), "read", self.projection).allowed)
        self.assertFalse(
            scope_queryset(self.owner, self._cpv_qs(), "published")
            .filter(pk=self.projection.pk)
            .exists()
        )

    def test_inactive_owner_is_denied(self):
        self.assertTrue(decide(self.owner, "read", self.projection).allowed)
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        self.owner.refresh_from_db()
        self.assertEqual(self.source.owner_id, self.owner.pk)
        self.assertFalse(decide(self.owner, "read", self.projection).allowed)
        self.assertFalse(decide(self.owner, "edit", self.projection).allowed)
        self.assertFalse(
            visible_queryset(self.owner, self._cpv_qs())
            .filter(pk=self.projection.pk)
            .exists()
        )

    # -- 2: editor grants bind the source, never the projection ----------

    def test_source_editor_grant_reads_projection_not_edits_it(self):
        self.source.add_editor(self.stranger, granted_by=self.owner)
        self.projection.refresh_from_db()
        self.assertTrue(decide(self.stranger, "read", self.projection).allowed)
        self.assertTrue(decide(self.stranger, "edit", self.source).allowed)
        self.assertFalse(decide(self.stranger, "edit", self.projection).allowed)

    def test_revoked_source_editor_grant_denies_immediately(self):
        self.source.add_editor(self.stranger, granted_by=self.owner)
        self.projection.refresh_from_db()
        detail = reverse(
            "collectionpropertyvalue-detail",
            kwargs={"pk": self.projection.pk},
        )
        self.assertTrue(decide(self.stranger, "read", self.projection).allowed)
        self.assertTrue(
            visible_queryset(self.stranger, self._cpv_qs())
            .filter(pk=self.projection.pk)
            .exists()
        )
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.source.remove_editor(self.stranger)
        self.assertFalse(decide(self.stranger, "read", self.projection).allowed)
        self.assertFalse(
            visible_queryset(self.stranger, self._cpv_qs())
            .filter(pk=self.projection.pk)
            .exists()
        )
        with self.assertLogs("django.request", level="WARNING"):
            response = self.client.get(detail)
        self.assertEqual(response.status_code, 403)

    def test_editor_grant_on_projection_alone_is_inert(self):
        target = User.objects.create_user("acl-gp-grant-target")
        ObjectEditorGrant.objects.create(
            content_type=ContentType.objects.get_for_model(self.projection),
            object_id=self.projection.pk,
            editor=target,
            granted_by=self.stranger,
        )
        self.assertFalse(decide(target, "read", self.projection).allowed)
        self.assertFalse(decide(target, "edit", self.projection).allowed)

    def test_source_group_grant_and_membership_revoke(self):
        group = Group.objects.create(name="acl-editor-group")
        member = User.objects.create_user("acl-group-member")
        member.groups.add(group)
        self.source.add_editor_group(group, granted_by=self.owner)
        self.assertTrue(decide(member, "read", self.projection).allowed)
        self.assertTrue(
            visible_queryset(member, self._cpv_qs())
            .filter(pk=self.projection.pk)
            .exists()
        )
        member.groups.remove(group)
        self.assertFalse(decide(member, "read", self.projection).allowed)
        self.assertFalse(
            visible_queryset(member, self._cpv_qs())
            .filter(pk=self.projection.pk)
            .exists()
        )

    # -- 3: every projection write is denied for every actor -------------

    def _write_actions(self):
        return [
            "edit",
            "delete",
            "duplicate",
            "new_version",
            "manage_editors",
            "transfer_ownership",
            "submit",
            "withdraw",
            "approve",
            "reject",
            "archive",
        ]

    def test_all_projection_writes_denied_for_owner_admin_superuser(self):
        for actor in (self.owner, self.app_admin, self.superuser):
            for action in self._write_actions():
                with self.subTest(actor=actor, action=action):
                    self.assertFalse(decide(actor, action, self.projection).allowed)
        self.assertTrue(decide(self.owner, "edit", self.source).allowed)

    def test_object_policy_capabilities_all_false_on_projection(self):
        policy = get_object_policy(self.owner, self.projection)
        for flag in (
            "can_edit",
            "can_delete",
            "can_manage_editors",
            "can_transfer_ownership",
            "can_archive",
            "can_submit_review",
            "can_withdraw_review",
            "can_approve",
            "can_reject",
        ):
            with self.subTest(flag=flag):
                self.assertFalse(policy[flag])

    # -- 4: shared services enforce the stored marker --------------------

    def test_content_mutation_denies_before_callback(self):
        called = []
        before = self._snapshot()
        with self.assertRaises(PermissionDenied):
            with content_mutation(self.owner, self.projection) as locked:
                called.append(locked)
        self.assertEqual(called, [])
        self.assertEqual(self._snapshot(), before)

    def test_content_mutation_uses_stored_marker_not_forged_instance(self):
        forged = CollectionPropertyValue.objects.get(pk=self.projection.pk)
        forged.is_derived = False
        before = self._snapshot()
        with self.assertRaises(PermissionDenied):
            with content_mutation(self.owner, forged):
                pass
        self.assertEqual(self._snapshot(), before)

    def test_perform_transition_denies_projection_at_valid_source_states(self):
        actor_states = {
            "submit": "private",
            "withdraw": "review",
            "approve": "review",
            "reject": "review",
            "archive": "published",
        }
        for action, state in actor_states.items():
            with self.subTest(action=action):
                self._set_source_state(state)
                self.assertTrue(decide(self.app_admin, action, self.source).allowed)
                before = self._snapshot()
                with self.assertRaises(PermissionDenied):
                    perform_transition(self.app_admin, self.projection, action)
                self.source.refresh_from_db()
                self.assertEqual(self.source.publication_status, state)
                self.assertEqual(self._snapshot(), before)

    # -- 5: generic HTML CRUD routes deny projection writes --------------

    def test_generic_update_and_delete_views_deny_owner_and_admin(self):
        before = self._snapshot()
        for actor in (self.owner, self.app_admin, self.superuser):
            self.client.force_login(actor)
            for url_name in (
                "collectionpropertyvalue-update",
                "collectionpropertyvalue-delete-modal",
            ):
                url = reverse(url_name, kwargs={"pk": self.projection.pk})
                with self.subTest(actor=actor, url=url_name):
                    with self.assertLogs("django.request", level="WARNING"):
                        get_response = self.client.get(url)
                    self.assertEqual(get_response.status_code, 403)
                    with self.assertLogs("django.request", level="WARNING"):
                        post_response = self.client.post(url, {})
                    self.assertEqual(post_response.status_code, 403)
                    self.assertEqual(self._snapshot(), before)
        self.projection.refresh_from_db()
        self.assertTrue(self.projection.is_derived)
        self.assertEqual(self.projection.publication_status, "published")
        self.assertEqual(self.projection.average, Decimal("300"))

    def test_generic_detail_serves_owner_but_denies_stranger(self):
        self.client.force_login(self.owner)
        url = reverse(
            "collectionpropertyvalue-detail", kwargs={"pk": self.projection.pk}
        )
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.stranger)
        with self.assertLogs("django.request", level="WARNING"):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    # -- 6: comments and review dispatch bind the source -----------------

    def test_record_comment_binds_source_thread_and_revision(self):
        self.source.refresh_from_db()
        bound_revision = self.source.content_revision
        source_ct = ContentType.objects.get_for_model(self.source)
        projection_ct = ContentType.objects.get_for_model(self.projection)
        before = self._snapshot()
        event = record_comment(
            self.owner,
            self.projection,
            "bound to source",
            expected_revision=bound_revision,
        )
        after = self._snapshot()
        self.assertEqual(event.content_type, source_ct)
        self.assertEqual(event.object_id, self.source.pk)
        self.assertEqual(event.content_revision, bound_revision)
        self.source.refresh_from_db()
        self.assertEqual(self.source.content_revision, bound_revision)
        self.assertEqual(after[0], before[0])
        self.assertEqual(after[1][:-1], before[1])
        self.assertEqual(after[1][-1]["id"], event.pk)
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=projection_ct, object_id=self.projection.pk
            ).exists()
        )

    def test_review_detail_redirects_to_source_then_serves_it(self):
        projection_ct = ContentType.objects.get_for_model(self.projection)
        source_ct = ContentType.objects.get_for_model(self.source)
        projection_url = reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": projection_ct.pk,
                "object_id": self.projection.pk,
            },
        )
        source_url = reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": source_ct.pk,
                "object_id": self.source.pk,
            },
        )
        self.client.force_login(self.owner)
        response = self.client.get(projection_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], source_url)
        self.assertEqual(self.client.get(source_url).status_code, 200)

    # -- 7: malformed generated rows fail closed -------------------------

    def test_unlinked_legacy_generated_row_fails_closed(self):
        legacy = CollectionPropertyValue.objects.create(
            name="acl-legacy-unlinked",
            collection=self.collection,
            property=self.total,
            unit=self.total_unit,
            year=2024,
            average=Decimal("1"),
            owner=self.stranger,
            publication_status="published",
            is_derived=True,
            derived_from=None,
        )
        for actor in (self.owner, self.stranger, self.app_admin, self.superuser):
            with self.subTest(actor=actor):
                self.assertFalse(decide(actor, "read", legacy).allowed)

    def test_generated_chained_projection_fails_closed(self):
        chained = CollectionPropertyValue.objects.create(
            name="acl-legacy-chained",
            collection=self.collection,
            property=self.total,
            unit=self.total_unit,
            year=2024,
            average=Decimal("1"),
            owner=self.stranger,
            publication_status="published",
            is_derived=True,
            derived_from=self.projection,
        )
        for actor in (self.owner, self.app_admin, self.superuser):
            with self.subTest(actor=actor):
                self.assertFalse(decide(actor, "read", chained).allowed)

    # -- 7b: database constraints enforce the source-binding shape ---------

    def test_raw_row_rejects_source_pointer_constraint(self):
        before = self._snapshot()
        with self.assertRaises(IntegrityError) as ctx:
            with transaction.atomic():
                CollectionPropertyValue.objects.filter(pk=self.source.pk).update(
                    derived_from_id=self.source.pk
                )
        self.assertIn("soilcom_cpv_raw_without_source_pointer", str(ctx.exception))
        self.assertEqual(self._snapshot(), before)

    def test_unique_generated_source_constraint_rejects_duplicate(self):
        before = self._snapshot()
        clone = CollectionPropertyValue.objects.get(pk=self.projection.pk)
        clone.pk = None
        with self.assertRaises(IntegrityError) as ctx:
            with transaction.atomic():
                clone.save(force_insert=True)
        self.assertIn("wc_unique_generated_cpv_source", str(ctx.exception))
        self.assertEqual(self._snapshot(), before)

    # -- 10: staff status alone grants nothing ------------------------------

    def test_staff_only_user_denied_private_source_projection(self):
        staff = User.objects.create_user("acl-staff", is_staff=True)
        staff.groups.clear()
        staff.user_permissions.clear()
        self.assertFalse(decide(staff, "read", self.projection).allowed)
        self.assertFalse(decide(staff, "edit", self.projection).allowed)
        self.assertFalse(
            visible_queryset(staff, self._cpv_qs())
            .filter(pk=self.projection.pk)
            .exists()
        )

    # -- 8: rendered detail carries the source-bound generated contract ----

    def test_projection_detail_shows_banner_source_link_and_source_owner(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse(
                "collectionpropertyvalue-detail",
                kwargs={"pk": self.projection.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Generated Value (Read-Only)")
        source = response.context.get("generated_value_source")
        self.assertIsNotNone(source)
        self.assertEqual(source.pk, self.source.pk)
        self.assertContains(
            response,
            reverse(
                "collectionpropertyvalue-detail",
                kwargs={"pk": self.source.pk},
            ),
        )
        self.assertInHTML(
            f"<div><dt>Source owner</dt><dd>{self.source.owner}</dd></div>",
            response.content.decode(),
        )

    def test_raw_source_detail_has_no_generated_banner(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse(
                "collectionpropertyvalue-detail",
                kwargs={"pk": self.source.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Generated Value (Read-Only)")
        self.assertIsNone(response.context.get("generated_value_source"))

    # -- 9: form/serializer surfaces carry no mutation handles -----------

    def test_cpv_form_fields_exclude_generated_markers(self):
        fields = CollectionPropertyValueModelForm.Meta.fields
        self.assertNotIn("is_derived", fields)
        self.assertNotIn("derived_from", fields)

    def test_cpv_serializer_fields_all_read_only(self):
        serializer = CollectionPropertyValueSerializer()
        for name, field in serializer.fields.items():
            with self.subTest(field=name):
                self.assertTrue(field.read_only)

    def test_admin_form_marks_projection_fields_readonly(self):
        cpv_admin = admin.site._registry[CollectionPropertyValue]
        request = RequestFactory().get("/admin/")
        request.user = self.superuser
        readonly = set(cpv_admin.get_readonly_fields(request, self.source))
        self.assertIn("is_derived", readonly)
        self.assertIn("derived_from", readonly)
        form_class = cpv_admin.get_form(request, self.source)
        self.assertNotIn("is_derived", form_class.base_fields)
        self.assertNotIn("derived_from", form_class.base_fields)

    def test_governed_delete_cascades_only_bound_projection(self):
        actor = User.objects.get(pk=self.owner.pk)
        actor.user_permissions.add(
            Permission.objects.get(
                codename="delete_collectionpropertyvalue",
                content_type=ContentType.objects.get_for_model(CollectionPropertyValue),
            )
        )
        actor = User.objects.get(pk=actor.pk)
        foreign_source = self._raw(
            self.specific,
            self.specific_unit,
            "175",
            owner=self.stranger,
            state="private",
        )
        foreign_output = create_or_update_derived_cpv(
            foreign_source, owner=self.stranger, publication_status="published"
        )[0]
        before = list(
            CollectionPropertyValue.objects.filter(
                pk__in=[foreign_source.pk, foreign_output.pk]
            )
            .order_by("pk")
            .values()
        )
        source_revision = self.source.content_revision

        with content_mutation(actor, self.source, action="delete") as locked:
            locked.delete()

        self.assertFalse(
            CollectionPropertyValue.objects.filter(pk=self.source.pk).exists()
        )
        self.assertFalse(
            CollectionPropertyValue.objects.filter(pk=self.projection.pk).exists()
        )
        after = list(
            CollectionPropertyValue.objects.filter(
                pk__in=[foreign_source.pk, foreign_output.pk]
            )
            .order_by("pk")
            .values()
        )
        self.assertEqual(before, after)
        deleted_events = list(
            ReviewAction.objects.filter(action=ReviewAction.ACTION_DELETED)
        )
        self.assertEqual(len(deleted_events), 1)
        event = deleted_events[0]
        self.assertEqual(event.object_id, self.source.pk)
        self.assertEqual(
            event.content_type_id,
            ContentType.objects.get_for_model(CollectionPropertyValue).pk,
        )
        self.assertEqual(event.content_revision, source_revision)
        self.assertEqual(event.user_id, actor.pk)

    def test_admin_post_to_projection_is_denied(self):
        self.client.force_login(self.superuser)
        url = reverse(
            "admin:waste_collection_collectionpropertyvalue_change",
            args=(self.projection.pk,),
        )
        before = self._snapshot()
        with self.assertLogs("django.request", level="WARNING"):
            response = self.client.post(
                url,
                {
                    "average": "999",
                    "is_derived": "",
                    "derived_from": str(self.source.pk),
                    "publication_status": "private",
                },
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self._snapshot(), before)


class GeneratedReviewPreviewAuthorizationTests(TestCase):
    """Review preview must not leak rows outside the actor's moderated models."""

    _raw = numeric_contracts.GeneratedPipelineNumericalTests._raw
    _assert_output = numeric_contracts.GeneratedPipelineNumericalTests._assert_output

    @classmethod
    def setUpTestData(cls):
        ensure_test_default_owner()
        call_command("sync_roles", "--apply", stdout=StringIO())
        numeric_contracts.GeneratedPipelineNumericalTests.setUpTestData.__func__(cls)
        cls.collection_moderator = User.objects.create_user(
            "acl-preview-collection-mod"
        )
        cls.collection_moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_collection",
                content_type=ContentType.objects.get_for_model(Collection),
            )
        )
        cls.cpv_moderator = User.objects.create_user("acl-preview-cpv-mod")
        cls.cpv_moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_collection",
                content_type=ContentType.objects.get_for_model(Collection),
            ),
            Permission.objects.get(
                codename="can_moderate_collectionpropertyvalue",
                content_type=ContentType.objects.get_for_model(CollectionPropertyValue),
            ),
            Permission.objects.get(
                codename="can_moderate_aggregatedcollectionpropertyvalue",
                content_type=ContentType.objects.get_for_model(
                    AggregatedCollectionPropertyValue
                ),
            ),
        )
        cls.acpv_property = Property.objects.create(
            name="acl preview metric",
            owner=cls.owner,
            publication_status="published",
        )

    def setUp(self):
        numeric_contracts.GeneratedPipelineNumericalTests.setUp(self)
        Collection.objects.filter(pk=self.collection.pk).update(
            publication_status="review"
        )
        self.raw = self._raw(self.specific, self.specific_unit, "150", state="review")
        self.projection = create_or_update_derived_cpv(
            self.raw, owner=self.stranger, publication_status="private"
        )[0]
        self.acpv = AggregatedCollectionPropertyValue.objects.create(
            owner=self.stranger,
            property=self.acpv_property,
            year=2024,
            average=Decimal("5"),
            publication_status="review",
        )
        self.acpv.collections.add(self.collection)

    def _review_url(self):
        return reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(
                    self.collection
                ).pk,
                "object_id": self.collection.pk,
            },
        )

    def test_collection_only_moderator_sees_no_cpv_preview(self):
        self.client.force_login(self.collection_moderator)
        response = self.client.get(self._review_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["collection_property_values"]), [])

    def test_collection_only_moderator_sees_no_acpv_preview(self):
        self.client.force_login(self.collection_moderator)
        response = self.client.get(self._review_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["aggregated_collection_property_values"]), []
        )

    def test_cpv_moderator_sees_source_bound_preview_rows(self):
        self.client.force_login(self.cpv_moderator)
        response = self.client.get(self._review_url())
        self.assertEqual(response.status_code, 200)
        cpv_pks = {row.pk for row in response.context["collection_property_values"]}
        self.assertIn(self.raw.pk, cpv_pks)
        self.assertIn(self.projection.pk, cpv_pks)
        acpv_pks = {
            row.pk for row in response.context["aggregated_collection_property_values"]
        }
        self.assertIn(self.acpv.pk, acpv_pks)

    def test_preview_dedup_prefers_review_source_not_copied_review_status(self):
        published_source = self._raw(
            self.specific, self.specific_unit, "100", state="published"
        )
        copied_review = create_or_update_derived_cpv(
            published_source, owner=self.stranger, publication_status="review"
        )[0]
        self.client.force_login(self.cpv_moderator)
        response = self.client.get(self._review_url())
        self.assertEqual(response.status_code, 200)
        total_pks = {
            row.pk
            for row in response.context["collection_property_values"]
            if row.property_id == self.total.pk
        }
        self.assertIn(self.projection.pk, total_pks)
        self.assertNotIn(copied_review.pk, total_pks)
