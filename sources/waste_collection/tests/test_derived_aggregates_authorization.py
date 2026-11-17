"""Authorization contract tests for source-bound generated aggregates.

Read and lifecycle eligibility on a generated aggregate always resolves
through the bound source row; copied metadata (status, owner) never grants
access and the projection surface is read-only for every actor. Fixture
data reuses the synthetic numeric contract module via a module import.
"""

from decimal import Decimal
from io import StringIO

from django.contrib import admin
from django.contrib.auth.models import AnonymousUser, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase
from django.urls import reverse

from sources.waste_collection.derived_aggregates import (
    create_or_update_derived_acpv,
)
from sources.waste_collection.forms import (
    AggregatedCollectionPropertyValueModelForm,
)
from sources.waste_collection.models import (
    AggregatedCollectionPropertyValue,
)
from sources.waste_collection.tests import (
    test_derived_aggregates_numeric as numeric_contracts,
)
from sources.waste_collection.waste_atlas.viewsets import (
    _map_aggregated_property_value_q,
)
from utils.object_management.models import ObjectEditorGrant, ReviewAction
from utils.object_management.permissions import get_object_policy
from utils.object_management.policy import (
    decide,
    editable_queryset,
    publication_states_queryset,
    reviewable_queryset,
    scope_queryset,
    visible_queryset,
)
from utils.object_management.services import (
    content_mutation,
    perform_transition,
    record_comment,
)
from utils.tests.testcases import ensure_test_default_owner


class GeneratedAggregateAuthorizationTests(TestCase):
    _raw = numeric_contracts.GeneratedAggregateNumericalTests._raw
    _assert_output = numeric_contracts.GeneratedAggregateNumericalTests._assert_output
    _nuts = numeric_contracts.GeneratedAggregateNumericalTests.__dict__["_nuts"]
    _observe = numeric_contracts.GeneratedAggregateNumericalTests.__dict__["_observe"]
    _catchment = numeric_contracts.GeneratedAggregateNumericalTests.__dict__[
        "_catchment"
    ]
    _collection = numeric_contracts.GeneratedAggregateNumericalTests.__dict__[
        "_collection"
    ]

    @classmethod
    def setUpTestData(cls):
        ensure_test_default_owner()
        call_command("sync_roles", "--apply", stdout=StringIO())
        numeric_contracts.GeneratedAggregateNumericalTests.setUpTestData.__func__(cls)
        cls.app_admin = User.objects.create_user("acl-agg-app-admin")
        cls.app_admin.user_permissions.add(
            Permission.objects.get(codename="administer_objects")
        )
        cls.superuser = User.objects.create_superuser(
            "acl-agg-super", password="x", email="acl-agg-super@example.com"
        )

    def setUp(self):
        numeric_contracts.GeneratedAggregateNumericalTests.setUp(self)
        self.source = self._raw(
            self.specific,
            self.specific_unit,
            "150",
            [self.collection],
            state="private",
        )
        self.projection = create_or_update_derived_acpv(
            self.source, owner=self.stranger, publication_status="published"
        )[0]

    def _acpv_qs(self):
        return AggregatedCollectionPropertyValue.objects.all()

    def _snapshot(self):
        return (
            list(
                AggregatedCollectionPropertyValue.objects.filter(
                    pk__in=[self.source.pk, self.projection.pk]
                )
                .order_by("pk")
                .values()
            ),
            list(ReviewAction.objects.order_by("pk").values()),
        )

    def _set_source_state(self, state):
        AggregatedCollectionPropertyValue.objects.filter(pk=self.source.pk).update(
            publication_status=state
        )
        self.source.refresh_from_db()
        self.projection.refresh_from_db()

    # -- 1: read surface follows the bound source row --------------------

    def test_source_owner_reads_projection_regardless_of_copied_metadata(self):
        self.assertTrue(decide(self.owner, "read", self.projection).allowed)
        self.assertTrue(
            visible_queryset(self.owner, self._acpv_qs())
            .filter(pk=self.projection.pk)
            .exists()
        )

    def test_anonymous_and_stranger_cannot_read_private_source_projection(self):
        for actor in (AnonymousUser(), self.stranger):
            with self.subTest(actor=actor):
                self.assertFalse(decide(actor, "read", self.projection).allowed)
                self.assertFalse(
                    visible_queryset(actor, self._acpv_qs())
                    .filter(pk=self.projection.pk)
                    .exists()
                )

    def test_public_source_projection_is_publicly_readable(self):
        self._set_source_state("published")
        for actor in (AnonymousUser(), self.stranger, self.owner):
            with self.subTest(actor=actor):
                self.assertTrue(decide(actor, "read", self.projection).allowed)

    def test_source_revocation_hides_projection_immediately(self):
        self._set_source_state("published")
        self.assertTrue(decide(AnonymousUser(), "read", self.projection).allowed)
        self.assertTrue(
            visible_queryset(AnonymousUser(), self._acpv_qs())
            .filter(pk=self.projection.pk)
            .exists()
        )
        self._set_source_state("private")
        self.assertFalse(decide(AnonymousUser(), "read", self.projection).allowed)
        self.assertFalse(
            visible_queryset(AnonymousUser(), self._acpv_qs())
            .filter(pk=self.projection.pk)
            .exists()
        )

    def test_archived_source_readable_but_out_of_published_scope(self):
        self._set_source_state("archived")
        self.assertTrue(decide(AnonymousUser(), "read", self.projection).allowed)
        self.assertFalse(
            publication_states_queryset(AnonymousUser(), self._acpv_qs(), ["published"])
            .filter(pk=self.projection.pk)
            .exists()
        )

    def test_source_status_drives_state_and_scope_queries(self):
        for state in ("private", "review", "published", "declined", "archived"):
            with self.subTest(state=state):
                self._set_source_state(state)
                self.assertEqual(
                    publication_states_queryset(
                        self.app_admin, self._acpv_qs(), [state]
                    )
                    .filter(pk=self.projection.pk)
                    .exists(),
                    True,
                )
                for other in ("private", "review", "published", "declined"):
                    if other == state:
                        continue
                    self.assertFalse(
                        publication_states_queryset(
                            self.app_admin, self._acpv_qs(), [other]
                        )
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
            "aggregatedcollectionpropertyvalue-detail",
            kwargs={"pk": self.projection.pk},
        )
        self.assertTrue(decide(self.stranger, "read", self.projection).allowed)
        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.source.remove_editor(self.stranger)
        self.assertFalse(decide(self.stranger, "read", self.projection).allowed)
        self.assertFalse(
            visible_queryset(self.stranger, self._acpv_qs())
            .filter(pk=self.projection.pk)
            .exists()
        )
        with self.assertLogs("django.request", level="WARNING"):
            response = self.client.get(detail)
        self.assertEqual(response.status_code, 403)

    def test_editor_grant_on_projection_alone_is_inert(self):
        target = User.objects.create_user("acl-agg-grant-target")
        ObjectEditorGrant.objects.create(
            content_type=ContentType.objects.get_for_model(self.projection),
            object_id=self.projection.pk,
            editor=target,
            granted_by=self.stranger,
        )
        self.assertFalse(decide(target, "read", self.projection).allowed)
        self.assertFalse(decide(target, "edit", self.projection).allowed)

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

    def test_generated_rows_never_enter_edit_or_review_querysets(self):
        self._set_source_state("published")
        for actor in (self.owner, self.app_admin, self.superuser):
            with self.subTest(actor=actor):
                self.assertFalse(
                    editable_queryset(actor, self._acpv_qs())
                    .filter(pk=self.projection.pk)
                    .exists()
                )
        self._set_source_state("review")
        moderator = User.objects.create_user("acl-agg-moderator")
        moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_aggregatedcollectionpropertyvalue",
                content_type=ContentType.objects.get_for_model(
                    AggregatedCollectionPropertyValue
                ),
            )
        )
        self.assertFalse(
            reviewable_queryset(moderator, self._acpv_qs())
            .filter(pk=self.projection.pk)
            .exists()
        )
        self.assertTrue(
            reviewable_queryset(moderator, self._acpv_qs())
            .filter(pk=self.source.pk)
            .exists()
        )

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
        forged = AggregatedCollectionPropertyValue.objects.get(pk=self.projection.pk)
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
                "aggregatedcollectionpropertyvalue-update",
                "aggregatedcollectionpropertyvalue-delete-modal",
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
            "aggregatedcollectionpropertyvalue-detail",
            kwargs={"pk": self.projection.pk},
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
        legacy = AggregatedCollectionPropertyValue.objects.create(
            name="acl-agg-legacy-unlinked",
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
        chained = AggregatedCollectionPropertyValue.objects.create(
            name="acl-agg-chained",
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

    # -- 7b: database constraints enforce the source-binding shape --------

    def test_raw_row_rejects_source_pointer_constraint(self):
        before = self._snapshot()
        with self.assertRaises(IntegrityError) as ctx:
            with transaction.atomic():
                AggregatedCollectionPropertyValue.objects.filter(
                    pk=self.source.pk
                ).update(derived_from_id=self.source.pk)
        self.assertIn("wc_acpv_raw_without_source_pointer", str(ctx.exception))
        self.assertEqual(self._snapshot(), before)

    def test_unique_generated_source_constraint_rejects_duplicate(self):
        before = self._snapshot()
        clone = AggregatedCollectionPropertyValue.objects.get(pk=self.projection.pk)
        clone.pk = None
        with self.assertRaises(IntegrityError) as ctx:
            with transaction.atomic():
                clone.save(force_insert=True)
        self.assertIn("wc_unique_generated_acpv_source", str(ctx.exception))
        self.assertEqual(self._snapshot(), before)

    # -- 8: enabled reader surfaces honor source governance ---------------

    def test_collection_display_values_follow_source_visibility(self):
        self._set_source_state("published")
        visible = AggregatedCollectionPropertyValue
        public_pks = set(
            visible.objects.filter(
                _map_aggregated_property_value_q(AnonymousUser())
            ).values_list("pk", flat=True)
        )
        self.assertIn(self.source.pk, public_pks)
        self.assertIn(self.projection.pk, public_pks)
        self._set_source_state("private")
        private_pks = set(
            visible.objects.filter(
                _map_aggregated_property_value_q(AnonymousUser())
            ).values_list("pk", flat=True)
        )
        self.assertNotIn(self.source.pk, private_pks)
        self.assertNotIn(self.projection.pk, private_pks)

    def test_private_source_with_public_copy_cannot_leak_through_scopes(self):
        for scope in ("published", "private", "owned", "shared"):
            with self.subTest(scope=scope):
                self.assertFalse(
                    scope_queryset(self.stranger, self._acpv_qs(), scope)
                    .filter(pk=self.projection.pk)
                    .exists()
                )
        self.assertTrue(
            scope_queryset(self.stranger, self._acpv_qs(), "owned")
            .filter(pk=self.source.pk)
            .exists()
            is False
        )

    def test_staff_only_user_denied_private_source_projection(self):
        staff = User.objects.create_user("acl-agg-staff", is_staff=True)
        staff.groups.clear()
        staff.user_permissions.clear()
        self.assertFalse(decide(staff, "read", self.projection).allowed)
        self.assertFalse(decide(staff, "edit", self.projection).allowed)
        self.assertFalse(
            visible_queryset(staff, self._acpv_qs())
            .filter(pk=self.projection.pk)
            .exists()
        )

    # -- 9: rendered/detail surfaces carry the generated contract ---------

    def test_projection_detail_shows_banner_and_source_link(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse(
                "aggregatedcollectionpropertyvalue-detail",
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
                "aggregatedcollectionpropertyvalue-detail",
                kwargs={"pk": self.source.pk},
            ),
        )

    def test_raw_source_detail_has_no_generated_banner(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse(
                "aggregatedcollectionpropertyvalue-detail",
                kwargs={"pk": self.source.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Generated Value (Read-Only)")
        self.assertIsNone(response.context.get("generated_value_source"))

    def test_acpv_form_fields_exclude_generated_markers(self):
        fields = AggregatedCollectionPropertyValueModelForm.Meta.fields
        self.assertNotIn("is_derived", fields)
        self.assertNotIn("derived_from", fields)

    def test_admin_form_marks_projection_fields_readonly(self):
        acpv_admin = admin.site._registry[AggregatedCollectionPropertyValue]
        request = RequestFactory().get("/admin/")
        request.user = self.superuser
        readonly = set(acpv_admin.get_readonly_fields(request, self.source))
        self.assertIn("is_derived", readonly)
        self.assertIn("derived_from", readonly)
        form_class = acpv_admin.get_form(request, self.source)
        self.assertNotIn("is_derived", form_class.base_fields)
        self.assertNotIn("derived_from", form_class.base_fields)

    def test_admin_post_to_projection_is_denied(self):
        self.client.force_login(self.superuser)
        url = reverse(
            "admin:waste_collection_aggregatedcollectionpropertyvalue_change",
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

    def test_governed_delete_cascades_only_bound_projection(self):
        actor = User.objects.get(pk=self.owner.pk)
        actor.user_permissions.add(
            Permission.objects.get(
                codename="delete_aggregatedcollectionpropertyvalue",
                content_type=ContentType.objects.get_for_model(
                    AggregatedCollectionPropertyValue
                ),
            )
        )
        actor = User.objects.get(pk=actor.pk)
        foreign_source = self._raw(
            self.specific,
            self.specific_unit,
            "175",
            [self.collection2],
            owner=self.stranger,
            state="private",
        )
        foreign_output = create_or_update_derived_acpv(
            foreign_source, owner=self.stranger, publication_status="published"
        )[0]
        before = list(
            AggregatedCollectionPropertyValue.objects.filter(
                pk__in=[foreign_source.pk, foreign_output.pk]
            )
            .order_by("pk")
            .values()
        )
        source_revision = self.source.content_revision

        with content_mutation(actor, self.source, action="delete") as locked:
            locked.delete()

        self.assertFalse(
            AggregatedCollectionPropertyValue.objects.filter(pk=self.source.pk).exists()
        )
        self.assertFalse(
            AggregatedCollectionPropertyValue.objects.filter(
                pk=self.projection.pk
            ).exists()
        )
        after = list(
            AggregatedCollectionPropertyValue.objects.filter(
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
            ContentType.objects.get_for_model(AggregatedCollectionPropertyValue).pk,
        )
        self.assertEqual(event.content_revision, source_revision)
        self.assertEqual(event.user_id, actor.pk)

    # -- 10: reported aggregates keep their ordinary lifecycle ------------

    def test_reported_aggregate_remains_editable_and_reviewable(self):
        source = self._raw(
            self.specific,
            self.specific_unit,
            "150",
            [self.collection],
            state="private",
        )
        self.assertFalse(source.is_derived)
        self.assertIsNone(source.derived_from_id)
        self.assertTrue(decide(self.owner, "edit", source).allowed)
        self.assertTrue(decide(self.owner, "submit", source).allowed)
        self.assertFalse(decide(self.stranger, "edit", source).allowed)
        self.assertFalse(decide(AnonymousUser(), "read", source).allowed)
