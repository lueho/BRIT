"""Revision-bound mutation and review-transition service tests.

Covers the exact contract cases for ``content_mutation``,
``perform_transition``, ``record_creation``, ``record_comment``,
``validate_reassignment``, contributor exclusion, atomic rollback, and the
deterministic concurrency boundary.
"""

import threading
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.forms.models import modelform_factory
from django.test import TestCase, TransactionTestCase

from bibliography.models import Author, Source, SourceAuthor
from bibliography.services import create_source_with_authors
from maps.models import (
    GeoPolygon,
    GeoreferencedNutsRegion,
    GeoreferencedRegion,
    NutsRegion,
    NutsVintage,
    Region,
)
from materials.models import (
    AnalyticalMethod,
    Composition,
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialProperty,
    MaterialPropertyValue,
    Sample,
)
from sources.waste_collection.models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionPropertyValue,
)
from utils.properties.models import Property, Unit

from .. import services
from ..models import ReviewAction
from ..policy import capabilities, decide
from ..services import (
    StaleRevisionError,
    content_mutation,
    contributor_user_ids,
    last_reviewed_revision,
    perform_transition,
    record_comment,
    record_creation,
    validate_reassignment,
)


def _perm(model, codename):
    return Permission.objects.get(
        codename=codename, content_type=ContentType.objects.get_for_model(model)
    )


def _actions_for(obj, action=None):
    qs = ReviewAction.objects.filter(
        content_type=ContentType.objects.get_for_model(obj.__class__),
        object_id=obj.pk,
    )
    if action is not None:
        qs = qs.filter(action=action)
    return qs


class RevisionServiceBase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="rev-owner")
        self.owner.user_permissions.add(
            _perm(Property, "add_property"),
            _perm(Property, "change_property"),
            _perm(Property, "delete_property"),
        )
        self.editor = User.objects.create_user(username="rev-editor")
        self.editor.user_permissions.add(_perm(Property, "change_property"))
        self.moderator = User.objects.create_user(username="rev-moderator")
        self.moderator.user_permissions.add(_perm(Property, "can_moderate_property"))
        self.stranger = User.objects.create_user(username="rev-stranger")
        self.administrator = User.objects.create_user(username="rev-admin")
        self.administrator.user_permissions.add(
            Permission.objects.get(codename="administer_objects")
        )
        self.prop = Property.objects.create(
            name="Rev Test Property", owner=self.owner, publication_status="private"
        )

    def _fresh(self, user):
        return User.objects.get(pk=user.pk)


class ContentMutationTests(RevisionServiceBase):
    def test_owner_edit_bumps_revision_and_records_event(self):
        with content_mutation(self.owner, self.prop, action="edit") as prop:
            prop.name = "Renamed"
            prop.save()
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.content_revision, 2)
        self.assertEqual(self.prop.lastmodified_by, self.owner)
        event = _actions_for(self.prop, "edited").get()
        self.assertEqual(event.user, self.owner)
        self.assertEqual(event.content_revision, 2)
        self.assertIn("name", event.changed_fields)

    def test_noop_save_does_not_bump(self):
        with content_mutation(self.owner, self.prop, action="edit") as prop:
            prop.save()
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.content_revision, 1)
        self.assertFalse(_actions_for(self.prop).exists())

    def test_m2m_only_change_bumps_once(self):
        unit = Unit.objects.create(name="kg", symbol="kg", owner=self.owner)
        with content_mutation(self.owner, self.prop, action="edit") as prop:
            prop.allowed_units.add(unit)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.content_revision, 2)
        event = _actions_for(self.prop, "edited").get()
        self.assertEqual(event.content_revision, 2)

    def test_nested_mutations_bump_once(self):
        with content_mutation(self.owner, self.prop, action="edit") as prop:
            prop.name = "Outer"
            prop.save()
            with content_mutation(self.owner, self.prop, action="edit") as inner:
                inner.description = "Inner"
                inner.save()
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.content_revision, 2)
        self.assertEqual(_actions_for(self.prop, "edited").count(), 1)

    def test_comment_does_not_bump_and_binds_watermark(self):
        action = record_comment(
            self.owner, self.prop, "looks fine", expected_revision=1
        )
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.content_revision, 1)
        self.assertEqual(action.content_revision, 1)
        self.assertEqual(action.action, ReviewAction.ACTION_COMMENT)

    def test_comment_without_watermark_stays_unbound(self):
        action = record_comment(self.owner, self.prop, "no watermark")
        self.assertIsNone(action.content_revision)

    def test_comment_watermark_above_current_rejected(self):
        with self.assertRaises(ValidationError):
            record_comment(self.owner, self.prop, "x", expected_revision=99)

    def test_sharing_and_transfer_do_not_bump(self):
        self.prop.add_editor(self.editor, granted_by=self.owner)
        self.prop.transfer_ownership(self.editor, initiator=self.owner)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.owner, self.editor)
        self.assertEqual(self.prop.content_revision, 1)

    def test_editor_grant_edit_bumps(self):
        self.prop.add_editor(self.editor, granted_by=self.owner)
        with content_mutation(self.editor, self.prop, action="edit") as prop:
            prop.description = "editor change"
            prop.save()
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.content_revision, 2)
        event = _actions_for(self.prop, "edited").get()
        self.assertEqual(event.user, self.editor)

    def test_frozen_published_root_denied_even_for_admin(self):
        self.administrator.user_permissions.add(_perm(Property, "change_property"))
        self.prop.publication_status = "published"
        self.prop.save()
        decision = decide(self._fresh(self.administrator), "edit", self.prop)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "immutable_state")
        with self.assertRaises(PermissionDenied):
            with content_mutation(self.administrator, self.prop, action="edit") as prop:
                prop.name = "forbidden"
                prop.save()
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.name, "Rev Test Property")
        self.assertEqual(self.prop.content_revision, 1)

    def test_delete_records_event_and_denies_foreign_root_rows(self):
        source = Source.objects.create(
            title="S", owner=self.owner, publication_status="published"
        )
        author = Author.objects.create(
            last_names="Doe",
            first_names="J",
            owner=self.owner,
            publication_status="private",
        )
        SourceAuthor.objects.create(source=source, author=author, position=1)
        self.owner.user_permissions.add(_perm(Author, "delete_author"))
        with self.assertRaises(PermissionDenied):
            with content_mutation(self._fresh(self.owner), author, action="delete"):
                author.delete()
        author.refresh_from_db()
        self.assertTrue(SourceAuthor.objects.filter(author=author).exists())

    def test_delete_allowed_records_deleted_event(self):
        pk = self.prop.pk
        with content_mutation(self.owner, self.prop, action="delete"):
            self.prop.delete()
        self.assertFalse(Property.objects.filter(pk=pk).exists())
        event = ReviewAction.objects.filter(
            object_id=pk, action=ReviewAction.ACTION_DELETED
        ).get()
        self.assertEqual(event.user, self.owner)

    def test_failed_audit_insert_rolls_back_content_and_revision(self):
        with (
            patch.object(
                ReviewAction.objects,
                "create",
                side_effect=RuntimeError("audit boom"),
            ),
            self.assertRaises(RuntimeError),
        ):
            with content_mutation(self.owner, self.prop, action="edit") as prop:
                prop.name = "Lost"
                prop.save()
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.name, "Rev Test Property")
        self.assertEqual(self.prop.content_revision, 1)


class OwnedAndEvidenceTests(RevisionServiceBase):
    def setUp(self):
        super().setUp()
        self.material = Material.objects.create(
            name="M", owner=self.owner, publication_status="private"
        )
        self.sample = Sample.objects.create(
            name="S",
            owner=self.owner,
            material=self.material,
            publication_status="private",
        )
        self.owner.user_permissions.add(
            _perm(Sample, "change_sample"),
            _perm(Sample, "add_sample"),
            _perm(MaterialPropertyValue, "change_materialpropertyvalue"),
            _perm(MaterialPropertyValue, "add_materialpropertyvalue"),
        )
        self.unit = Unit.objects.create(name="g", symbol="g", owner=self.owner)
        self.group = MaterialComponentGroup.objects.create(name="G")
        self.component = MaterialComponent.objects.create(name="C")
        self.mproperty = MaterialProperty.objects.create(name="MP", owner=self.owner)

    def test_owned_child_create_bumps_parent_snapshot(self):
        with content_mutation(self.owner, self.sample, action="edit"):
            Composition.objects.create(
                sample=self.sample, group=self.group, owner=self.owner
            )
        self.sample.refresh_from_db()
        self.assertEqual(self.sample.content_revision, 2)
        event = _actions_for(self.sample, "edited").get()
        self.assertTrue(any("composition" in field for field in event.changed_fields))

    def test_owned_child_delete_bumps_parent(self):
        composition = Composition.objects.create(
            sample=self.sample, group=self.group, owner=self.owner
        )
        with content_mutation(self.owner, composition, action="delete"):
            composition.delete()
        self.sample.refresh_from_db()
        self.assertEqual(self.sample.content_revision, 2)
        event = _actions_for(self.sample, "edited").get()
        self.assertTrue(any("deleted" in field for field in event.changed_fields))

    def test_independent_evidence_edit_bumps_own_revision_only(self):
        mpv = MaterialPropertyValue.objects.create(
            owner=self.owner,
            sample=self.sample,
            property=self.mproperty,
            unit=self.unit,
            average=Decimal("1"),
            publication_status="private",
        )
        with content_mutation(self.owner, mpv, action="edit") as row:
            row.average = Decimal("2")
            row.save()
        mpv.refresh_from_db()
        self.sample.refresh_from_db()
        self.assertEqual(mpv.content_revision, 2)
        self.assertEqual(self.sample.content_revision, 1)
        self.assertTrue(_actions_for(mpv, "edited").exists())
        self.assertFalse(_actions_for(self.sample).exists())

    def test_evidence_delete_bumps_own_not_parent(self):
        mpv = MaterialPropertyValue.objects.create(
            owner=self.owner,
            sample=self.sample,
            property=self.mproperty,
            unit=self.unit,
            average=Decimal("1"),
            publication_status="private",
        )
        self.owner.user_permissions.add(
            _perm(MaterialPropertyValue, "delete_materialpropertyvalue")
        )
        mpv_pk = mpv.pk
        with content_mutation(self._fresh(self.owner), mpv, action="delete"):
            mpv.delete()
        self.sample.refresh_from_db()
        self.assertEqual(self.sample.content_revision, 1)
        self.assertTrue(
            ReviewAction.objects.filter(
                object_id=mpv_pk, action=ReviewAction.ACTION_DELETED
            ).exists()
        )

    def test_reassignment_requires_valid_new_parent(self):
        mpv = MaterialPropertyValue.objects.create(
            owner=self.owner,
            sample=self.sample,
            property=self.mproperty,
            unit=self.unit,
            average=Decimal("1"),
            publication_status="private",
        )
        foreign_sample = Sample.objects.create(
            name="Other",
            owner=self.stranger,
            material=self.material,
            publication_status="private",
        )
        with self.assertRaises(PermissionDenied):
            validate_reassignment(self.owner, mpv, foreign_sample)
        with self.assertRaises(ValidationError):
            validate_reassignment(self.owner, mpv, Sample(name="unsaved"))
        with self.assertRaises(ValidationError):
            validate_reassignment(self.owner, mpv, None)

    def test_reassignment_to_own_parent_allowed(self):
        mpv = MaterialPropertyValue.objects.create(
            owner=self.owner,
            sample=self.sample,
            property=self.mproperty,
            unit=self.unit,
            average=Decimal("1"),
            publication_status="private",
        )
        other = Sample.objects.create(
            name="Other",
            owner=self.owner,
            material=self.material,
            publication_status="private",
        )
        self.assertTrue(validate_reassignment(self.owner, mpv, other))


class TransitionTests(RevisionServiceBase):
    def _submit(self, obj=None, actor=None):
        obj = obj or self.prop
        return perform_transition(actor or self.owner, obj, "submit")

    def test_submit_binds_revision_and_records_event(self):
        perform_transition(self.owner, self.prop, "submit", comment="ready")
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.publication_status, "review")
        self.assertEqual(self.prop.content_revision, 1)
        event = _actions_for(self.prop, "submitted").get()
        self.assertEqual(event.content_revision, 1)
        self.assertEqual(event.comment, "ready")

    def test_approve_requires_inspected_revision(self):
        self._submit()
        with self.assertRaises(ValidationError) as ctx:
            perform_transition(self.moderator, self.prop, "approve")
        self.assertEqual(ctx.exception.code, "revision_required")
        with self.assertRaises(ValidationError):
            perform_transition(
                self.moderator, self.prop, "approve", expected_revision=True
            )
        with self.assertRaises(ValidationError):
            perform_transition(
                self.moderator, self.prop, "approve", expected_revision="abc"
            )
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.publication_status, "review")
        self.assertFalse(_actions_for(self.prop, "approved").exists())

    def test_stale_revision_rejected_without_mutation(self):
        self._submit()
        with content_mutation(self.owner, self.prop, action="edit") as prop:
            prop.description = "changed after inspection"
            prop.save()
        with self.assertRaises(StaleRevisionError) as ctx:
            perform_transition(
                self.moderator, self.prop, "approve", expected_revision=1
            )
        self.assertEqual(ctx.exception.code, "stale_revision")
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.publication_status, "review")
        self.assertEqual(self.prop.content_revision, 2)
        self.assertFalse(_actions_for(self.prop, "approved").exists())

    def test_unrelated_moderator_approves_current_revision(self):
        self._submit()
        perform_transition(self.moderator, self.prop, "approve", expected_revision=1)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.publication_status, "published")
        self.assertEqual(self.prop.approved_by, self.moderator)
        event = _actions_for(self.prop, "approved").get()
        self.assertEqual(event.content_revision, 1)
        self.assertEqual(event.user, self.moderator)

    def test_owner_cannot_approve(self):
        self._submit()
        self.owner.user_permissions.add(_perm(Property, "can_moderate_property"))
        with self.assertRaises(PermissionDenied):
            perform_transition(
                self._fresh(self.owner),
                self.prop,
                "approve",
                expected_revision=1,
            )

    def test_recorded_editor_cannot_approve(self):
        self.prop.add_editor(self.editor, granted_by=self.owner)
        with content_mutation(self.editor, self.prop, action="edit") as prop:
            prop.description = "editor contribution"
            prop.save()
        self.editor.user_permissions.add(_perm(Property, "can_moderate_property"))
        self._submit()
        with self.assertRaises(PermissionDenied):
            perform_transition(
                self._fresh(self.editor),
                self.prop,
                "approve",
                expected_revision=2,
            )
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.publication_status, "review")

    def test_earlier_editor_cannot_approve_after_later_edit(self):
        self.prop.add_editor(self.editor, granted_by=self.owner)
        with content_mutation(self.editor, self.prop, action="edit") as prop:
            prop.description = "first contribution"
            prop.save()
        with content_mutation(self.owner, self.prop, action="edit") as prop:
            prop.description = "owner follow-up"
            prop.save()
        self.editor.user_permissions.add(_perm(Property, "can_moderate_property"))
        self._submit()
        with self.assertRaises(PermissionDenied):
            perform_transition(
                self._fresh(self.editor),
                self.prop,
                "approve",
                expected_revision=3,
            )

    def test_grant_holder_without_contribution_can_approve(self):
        self.prop.add_editor(self.moderator, granted_by=self.owner)
        self._submit()
        perform_transition(self.moderator, self.prop, "approve", expected_revision=1)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.publication_status, "published")

    def test_former_creator_cannot_approve_after_transfer(self):
        record_creation(self.stranger, self.prop)
        self.prop.owner = self.owner
        self.prop.save()
        self.stranger.user_permissions.add(_perm(Property, "can_moderate_property"))
        self._submit()
        with self.assertRaises(PermissionDenied):
            perform_transition(
                self._fresh(self.stranger),
                self.prop,
                "approve",
                expected_revision=1,
            )

    def test_reject_and_withdraw_record_transitions(self):
        self._submit()
        perform_transition(self.moderator, self.prop, "reject", comment="needs work")
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.publication_status, "declined")
        self.assertTrue(_actions_for(self.prop, "rejected").exists())
        self._submit()
        perform_transition(self.owner, self.prop, "withdraw")
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.publication_status, "private")
        self.assertTrue(_actions_for(self.prop, "withdrawn").exists())

    def test_full_cycle_history_retained(self):
        self._submit()
        perform_transition(self.moderator, self.prop, "reject")
        self._submit()
        perform_transition(self.moderator, self.prop, "approve", expected_revision=1)
        actions = list(_actions_for(self.prop).values_list("action", flat=True))
        self.assertEqual(actions.count("submitted"), 2)
        self.assertIn("rejected", actions)
        self.assertIn("approved", actions)

    def test_failed_audit_rolls_back_transition(self):
        self._submit()
        with (
            patch.object(
                ReviewAction.objects,
                "create",
                side_effect=RuntimeError("audit boom"),
            ),
            self.assertRaises(RuntimeError),
        ):
            perform_transition(
                self.moderator, self.prop, "approve", expected_revision=1
            )
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.publication_status, "review")
        self.assertIsNone(self.prop.approved_by)


class CompoundCreationTests(RevisionServiceBase):
    def setUp(self):
        super().setUp()
        self.owner.user_permissions.add(
            _perm(Source, "add_source"), _perm(Author, "add_author")
        )

    def test_source_and_new_authors_get_separate_events(self):
        source = create_source_with_authors(
            self.owner,
            {"title": "Compound"},
            [
                {"last_names": "Doe", "first_names": "J"},
                {"organization_name": "Org", "author_type": "organization"},
            ],
        )
        source.refresh_from_db()
        self.assertEqual(source.content_revision, 1)
        event = _actions_for(source, "created").get()
        self.assertEqual(event.user, self.owner)
        self.assertEqual(event.changed_fields, ["created"])
        authors = [sa.author for sa in source.ordered_authors()]
        self.assertEqual(len(authors), 2)
        for author in authors:
            self.assertTrue(_actions_for(author, "created").exists())

    def test_invalid_author_rolls_back_everything(self):
        with self.assertRaises(ValidationError):
            create_source_with_authors(
                self.owner,
                {"title": "Rollback"},
                [
                    {"last_names": "Doe", "first_names": "J"},
                    {"author_type": "robot", "last_names": "X"},
                ],
            )
        self.assertFalse(Source.objects.filter(title="Rollback").exists())
        self.assertFalse(Author.objects.filter(last_names="Doe").exists())
        self.assertEqual(ReviewAction.objects.count(), 0)


class FacetContributorTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="facet-owner")
        self.editor = User.objects.create_user(username="facet-editor")
        self.moderator = User.objects.create_user(username="facet-moderator")
        vintage = NutsVintage.objects.first() or NutsVintage.objects.create(
            year=2021, is_current=True
        )
        self.region = NutsRegion.objects.create(
            name="Deutschland",
            nuts_id="DE",
            levl_code=0,
            cntr_code="DE",
            version=vintage,
            owner=self.owner,
            publication_status="review",
        )
        self.moderator.user_permissions.add(
            _perm(NutsRegion, "can_moderate_nutsregion")
        )

    def test_region_facet_edit_counts_toward_nutsregion_contributors(self):
        ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(Region),
            object_id=self.region.pk,
            user=self.editor,
            action=ReviewAction.ACTION_EDITED,
            content_revision=1,
        )
        self.assertIn(self.editor.pk, contributor_user_ids(self.region))
        self.editor.user_permissions.add(_perm(NutsRegion, "can_moderate_nutsregion"))
        fresh_editor = User.objects.get(pk=self.editor.pk)
        decision = decide(fresh_editor, "approve", self.region)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "four_eyes_required")
        with self.assertRaises(PermissionDenied):
            perform_transition(
                fresh_editor,
                self.region,
                "approve",
                expected_revision=self.region.content_revision,
            )
        self.region.refresh_from_db()
        self.assertEqual(self.region.publication_status, "review")
        perform_transition(
            self.moderator,
            self.region,
            "approve",
            expected_revision=self.region.content_revision,
        )
        self.region.refresh_from_db()
        self.assertEqual(self.region.publication_status, "published")


class QueueRevisionTests(RevisionServiceBase):
    def test_last_reviewed_revision_from_bound_actions_only(self):
        self.assertIsNone(last_reviewed_revision(self.moderator, self.prop))
        record_comment(self.owner, self.prop, "unbound")
        self.assertIsNone(last_reviewed_revision(self.owner, self.prop))
        record_comment(self.owner, self.prop, "bound", expected_revision=1)
        self.assertEqual(last_reviewed_revision(self.owner, self.prop), 1)

    def test_lifecycle_events_are_not_review_proof(self):
        record_creation(self.owner, self.prop)
        with content_mutation(self.owner, self.prop, action="edit") as prop:
            prop.description = "edited"
            prop.save()
        perform_transition(self.owner, self.prop, "submit")
        perform_transition(self.owner, self.prop, "withdraw")
        perform_transition(self.owner, self.prop, "submit")
        perform_transition(self.moderator, self.prop, "reject")
        self.assertIsNone(last_reviewed_revision(self.owner, self.prop))
        self.assertIsNone(last_reviewed_revision(self.moderator, self.prop))
        record_comment(self.moderator, self.prop, "inspected", expected_revision=1)
        self.assertEqual(last_reviewed_revision(self.moderator, self.prop), 1)

    def test_bound_approval_establishes_watermark(self):
        perform_transition(self.owner, self.prop, "submit")
        perform_transition(self.moderator, self.prop, "approve", expected_revision=1)
        self.assertEqual(last_reviewed_revision(self.moderator, self.prop), 1)


class CoreApproveContributorTests(RevisionServiceBase):
    """Contributor exclusion lives in the single core approve decision."""

    def setUp(self):
        super().setUp()
        self.prop.add_editor(self.editor, granted_by=self.owner)
        with content_mutation(self.editor, self.prop, action="edit") as prop:
            prop.description = "contributed content"
            prop.save()
        self.editor.user_permissions.add(_perm(Property, "can_moderate_property"))
        perform_transition(self.owner, self.prop, "submit")
        self.prop.refresh_from_db()

    def test_decide_approve_denies_contributor_in_core(self):
        fresh_editor = self._fresh(self.editor)
        decision = decide(fresh_editor, "approve", self.prop)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "four_eyes_required")

    def test_capabilities_hide_approve_for_contributor(self):
        caps = capabilities(self._fresh(self.editor), self.prop)
        self.assertFalse(caps["approve"].allowed)
        self.assertTrue(caps["reject"].allowed)

    def test_unrelated_moderator_still_approves_same_revision(self):
        self.assertTrue(
            decide(self._fresh(self.moderator), "approve", self.prop).allowed
        )
        perform_transition(self.moderator, self.prop, "approve", expected_revision=2)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.publication_status, "published")


class ConcurrencyTests(TransactionTestCase):
    """Deterministic two-connection stale-approval boundary (case 6)."""

    def setUp(self):
        self.owner = User.objects.create_user(username="cc-owner")
        self.owner.user_permissions.add(
            _perm(Property, "add_property"),
            _perm(Property, "change_property"),
        )
        self.moderator = User.objects.create_user(username="cc-moderator")
        self.moderator.user_permissions.add(_perm(Property, "can_moderate_property"))
        self.prop = Property.objects.create(
            name="Concurrent", owner=self.owner, publication_status="review"
        )

    def test_concurrent_edit_makes_approval_stale(self):
        """An edit committing between inspection and approval must win.

        Thread A holds the root lock inside ``content_mutation`` and waits on
        a barrier; thread B signals when it actually attempts the same row
        lock inside ``perform_transition`` — only then is the barrier
        released, so the approval deterministically runs after the commit
        and must fail stale.
        """
        edit_locked = threading.Event()
        approve_attempted = threading.Event()
        proceed = threading.Event()
        results = {}
        errors = {}

        real_lock = services._lock_instance

        def signaling_lock(obj):
            approve_attempted.set()
            return real_lock(obj)

        def editor():
            with content_mutation(self.owner, self.prop, action="edit") as prop:
                prop.description = "concurrent edit"
                prop.save()
                edit_locked.set()
                proceed.wait(timeout=10)

        def approver():
            with patch.object(services, "_lock_instance", side_effect=signaling_lock):
                perform_transition(
                    self.moderator, self.prop, "approve", expected_revision=1
                )

        def run(fn, key):
            try:
                fn()
            except StaleRevisionError as exc:
                results[key] = exc
            except Exception as exc:  # pragma: no cover
                errors[key] = exc
            finally:
                connection.close()

        t_edit = threading.Thread(target=lambda: run(editor, "editor"))
        t_edit.start()
        self.assertTrue(edit_locked.wait(timeout=10))

        t_approve = threading.Thread(target=lambda: run(approver, "approver"))
        t_approve.start()
        self.assertTrue(approve_attempted.wait(timeout=10))
        proceed.set()
        t_edit.join(timeout=10)
        t_approve.join(timeout=10)

        self.assertFalse(t_edit.is_alive() or t_approve.is_alive())
        self.assertFalse(errors, errors)
        self.assertIsInstance(results.get("approver"), StaleRevisionError)

        fresh = Property.objects.get(pk=self.prop.pk)
        self.assertEqual(fresh.publication_status, "review")
        self.assertEqual(fresh.content_revision, 2)


class OwnedChildApprovalRaceTests(TransactionTestCase):
    """Owned-child writes bump the root revision; a concurrent approval on
    the inspected revision must fail stale after the locks serialize."""

    def setUp(self):
        self.owner = User.objects.create_user(username="occ-owner")
        self.owner.user_permissions.add(_perm(Source, "change_source"))
        self.moderator = User.objects.create_user(username="occ-moderator")
        self.moderator.user_permissions.add(_perm(Source, "can_moderate_source"))
        self.author = Author.objects.create(
            last_names="Doe", owner=self.owner, publication_status="private"
        )
        self.source = Source.objects.create(
            title="Raced", owner=self.owner, publication_status="review"
        )
        self.link = SourceAuthor.objects.create(
            source=self.source, author=self.author, position=1
        )

    def test_owned_child_edit_makes_parent_approval_stale(self):
        edit_locked = threading.Event()
        approve_attempted = threading.Event()
        proceed = threading.Event()
        results = {}
        errors = {}

        real_lock = services._lock_instance

        def signaling_lock(obj):
            approve_attempted.set()
            return real_lock(obj)

        def editor():
            with content_mutation(self.owner, self.link, action="edit") as row:
                row.position = 2
                row.save()
                edit_locked.set()
                proceed.wait(timeout=10)

        def approver():
            with patch.object(services, "_lock_instance", side_effect=signaling_lock):
                perform_transition(
                    self.moderator, self.source, "approve", expected_revision=1
                )

        def run(fn, key):
            try:
                fn()
            except StaleRevisionError as exc:
                results[key] = exc
            except Exception as exc:  # pragma: no cover
                errors[key] = exc
            finally:
                connection.close()

        t_edit = threading.Thread(target=lambda: run(editor, "editor"))
        t_edit.start()
        self.assertTrue(edit_locked.wait(timeout=10))

        t_approve = threading.Thread(target=lambda: run(approver, "approver"))
        t_approve.start()
        self.assertTrue(approve_attempted.wait(timeout=10))
        proceed.set()
        t_edit.join(timeout=10)
        t_approve.join(timeout=10)

        self.assertFalse(t_edit.is_alive() or t_approve.is_alive())
        self.assertFalse(errors, errors)
        self.assertIsInstance(results.get("approver"), StaleRevisionError)

        self.source.refresh_from_db()
        self.link.refresh_from_db()
        self.assertEqual(self.source.publication_status, "review")
        self.assertEqual(self.source.content_revision, 2)
        self.assertEqual(self.link.position, 2)


class OwnedParentResolutionTests(TestCase):
    """Owned children must re-resolve their stored parent under the root lock."""

    def setUp(self):
        self.owner = User.objects.create_user(username="link-owner")
        self.owner.user_permissions.add(_perm(Source, "change_source"))
        self.stranger = User.objects.create_user(username="link-stranger")
        self.source = Source.objects.create(
            title="Src", owner=self.owner, publication_status="private"
        )
        self.author = Author.objects.create(
            last_names="Doe", owner=self.owner, publication_status="private"
        )
        self.link = SourceAuthor.objects.create(
            source=self.source, author=self.author, position=1
        )

    def test_parent_published_between_resolve_and_lock_denies(self):
        real_lock = services._lock_instance

        def publish_then_lock(obj):
            Source.objects.filter(pk=obj.pk).update(publication_status="published")
            return real_lock(obj)

        with patch.object(services, "_lock_instance", side_effect=publish_then_lock):
            with self.assertRaises(PermissionDenied):
                with content_mutation(self.owner, self.link, action="edit") as row:
                    row.position = 9
                    row.save()
        self.link.refresh_from_db()
        self.source.refresh_from_db()
        self.assertEqual(self.link.position, 1)
        self.assertEqual(self.source.content_revision, 1)

    def test_parent_moved_between_resolve_and_lock_denies(self):
        other = Source.objects.create(
            title="Other", owner=self.stranger, publication_status="private"
        )
        real_lock = services._lock_instance

        def move_then_lock(obj):
            SourceAuthor.objects.filter(pk=self.link.pk).update(source=other)
            return real_lock(obj)

        with patch.object(services, "_lock_instance", side_effect=move_then_lock):
            with self.assertRaises(PermissionDenied):
                with content_mutation(self.owner, self.link, action="edit") as row:
                    row.position = 9
                    row.save()
        self.link.refresh_from_db()
        self.assertEqual(self.link.source_id, self.source.pk)
        self.assertEqual(self.link.position, 1)


class LockedTargetInvariantTests(RevisionServiceBase):
    """Callbacks writing stale or protected state must never commit."""

    def test_stale_instance_save_restores_no_metadata(self):
        stale = Property.objects.get(pk=self.prop.pk)
        Property.objects.filter(pk=self.prop.pk).update(
            owner_id=self.editor.pk, publication_status="review"
        )
        with self.assertRaises(PermissionDenied):
            with content_mutation(self.editor, self.prop, action="edit"):
                stale.name = "clobber"
                stale.save()
        fresh = Property.objects.get(pk=self.prop.pk)
        self.assertEqual(fresh.owner_id, self.editor.pk)
        self.assertEqual(fresh.publication_status, "review")
        self.assertEqual(fresh.name, "Rev Test Property")
        self.assertEqual(fresh.content_revision, 1)

    def test_callback_protected_metadata_write_rolls_back(self):
        with self.assertRaises(PermissionDenied):
            with content_mutation(self.owner, self.prop, action="edit") as prop:
                prop.publication_status = "published"
                prop.save()
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.publication_status, "private")
        self.assertEqual(self.prop.content_revision, 1)

    def test_locked_delete_uses_yielded_object_and_keeps_object_id(self):
        pk = self.prop.pk
        with content_mutation(self.owner, self.prop, action="delete") as prop:
            prop.delete()
        self.assertFalse(Property.objects.filter(pk=pk).exists())
        event = ReviewAction.objects.get(
            content_type=ContentType.objects.get_for_model(Property),
            object_id=pk,
            action=ReviewAction.ACTION_DELETED,
        )
        self.assertEqual(event.user, self.owner)

    def test_deleted_actor_is_denied(self):
        ghost = User.objects.create_superuser(username="ghost", email="", password=None)
        User.objects.filter(pk=ghost.pk).delete()
        with self.assertRaises(PermissionDenied):
            with content_mutation(ghost, self.prop, action="edit") as prop:
                prop.name = "x"
                prop.save()
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.name, "Rev Test Property")
        self.assertEqual(self.prop.content_revision, 1)

    def test_narrow_form_preserves_concurrent_field_change(self):
        from django.http import HttpResponse

        from utils.object_management.views import _perform_bound_update

        narrow_form_class = modelform_factory(Property, fields=["name"])
        stale = Property.objects.get(pk=self.prop.pk)
        form = narrow_form_class({"name": "Posted"}, instance=stale)
        self.assertTrue(form.is_valid())
        Property.objects.filter(pk=self.prop.pk).update(description="concurrent edit")

        def fake_super(bound_form):
            view.object = bound_form.save()
            return HttpResponse()

        view = SimpleNamespace(
            object=stale,
            request=SimpleNamespace(user=self.owner),
            _call_super_form_valid=fake_super,
        )
        response = _perform_bound_update(view, form)
        self.assertIsNotNone(response)
        fresh = Property.objects.get(pk=self.prop.pk)
        self.assertEqual(fresh.description, "concurrent edit")
        self.assertEqual(fresh.name, "Posted")
        self.assertEqual(fresh.content_revision, 2)


class ReassignmentLockTests(RevisionServiceBase):
    """``proposed_parent`` coordinates locks, re-decision, and dual audit."""

    def setUp(self):
        super().setUp()
        self.material = Material.objects.create(
            name="M", owner=self.owner, publication_status="private"
        )
        self.owner.user_permissions.add(
            _perm(Sample, "change_sample"),
            _perm(MaterialPropertyValue, "change_materialpropertyvalue"),
        )
        self.sample_a = Sample.objects.create(
            name="A",
            owner=self.owner,
            material=self.material,
            publication_status="private",
        )
        self.sample_b = Sample.objects.create(
            name="B",
            owner=self.owner,
            material=self.material,
            publication_status="private",
        )
        self.composition = Composition.objects.create(
            sample=self.sample_a,
            group=MaterialComponentGroup.objects.create(name="RG"),
            owner=self.owner,
        )
        self.unit = Unit.objects.create(name="g", symbol="g", owner=self.owner)
        self.mproperty = MaterialProperty.objects.create(name="MP", owner=self.owner)

    def _mpv(self, sample):
        return MaterialPropertyValue.objects.create(
            owner=self.owner,
            sample=sample,
            property=self.mproperty,
            unit=self.unit,
            average=Decimal("1"),
            publication_status="private",
        )

    def test_owned_move_audits_both_roots(self):
        with content_mutation(
            self.owner,
            self.composition,
            action="edit",
            proposed_parent=self.sample_b,
        ) as row:
            row.sample = self.sample_b
            row.save()
        self.sample_a.refresh_from_db()
        self.sample_b.refresh_from_db()
        self.composition.refresh_from_db()
        self.assertEqual(self.composition.sample_id, self.sample_b.pk)
        self.assertEqual(self.sample_a.content_revision, 2)
        self.assertEqual(self.sample_b.content_revision, 2)
        self.assertEqual(_actions_for(self.sample_a, "edited").count(), 1)
        self.assertEqual(_actions_for(self.sample_b, "edited").count(), 1)

    def test_owned_move_denied_without_edit_on_new_root(self):
        foreign = Sample.objects.create(
            name="F",
            owner=self.stranger,
            material=self.material,
            publication_status="private",
        )
        with self.assertRaises(PermissionDenied):
            with content_mutation(
                self.owner,
                self.composition,
                action="edit",
                proposed_parent=foreign,
            ) as row:
                row.sample = foreign
                row.save()
        self.composition.refresh_from_db()
        self.sample_a.refresh_from_db()
        foreign.refresh_from_db()
        self.assertEqual(self.composition.sample_id, self.sample_a.pk)
        self.assertEqual(self.sample_a.content_revision, 1)
        self.assertEqual(foreign.content_revision, 1)

    def test_evidence_move_is_own_root_write_without_add_perm(self):
        mpv = self._mpv(self.sample_a)
        self.owner.user_permissions.remove(
            _perm(MaterialPropertyValue, "add_materialpropertyvalue")
        )
        with content_mutation(
            self.owner, mpv, action="edit", proposed_parent=self.sample_b
        ) as row:
            row.sample = self.sample_b
            row.save()
        mpv.refresh_from_db()
        self.sample_a.refresh_from_db()
        self.sample_b.refresh_from_db()
        self.assertEqual(mpv.sample_id, self.sample_b.pk)
        self.assertEqual(mpv.content_revision, 2)
        self.assertEqual(_actions_for(mpv, "edited").get().changed_fields, ["sample"])
        self.assertEqual(self.sample_a.content_revision, 1)
        self.assertEqual(self.sample_b.content_revision, 1)

    def test_evidence_move_denied_when_new_parent_inaccessible(self):
        mpv = self._mpv(self.sample_a)
        foreign = Sample.objects.create(
            name="F2",
            owner=self.stranger,
            material=self.material,
            publication_status="private",
        )
        with self.assertRaises(PermissionDenied):
            with content_mutation(
                self.owner, mpv, action="edit", proposed_parent=foreign
            ) as row:
                row.sample = foreign
                row.save()
        mpv.refresh_from_db()
        self.assertEqual(mpv.sample_id, self.sample_a.pk)
        self.assertEqual(mpv.content_revision, 1)

    def test_new_parent_access_revoked_between_preflight_and_lock_denies(self):
        mpv = self._mpv(self.sample_a)
        foreign = Sample.objects.create(
            name="F3",
            owner=self.stranger,
            material=self.material,
            publication_status="private",
        )
        foreign.add_editor(self.owner, granted_by=self.stranger)
        self.assertTrue(
            validate_reassignment(User.objects.get(pk=self.owner.pk), mpv, foreign)
        )
        real_lock = services._lock_instance

        def revoke_then_lock(obj):
            if isinstance(obj, Sample) and obj.pk == foreign.pk:
                foreign.remove_editor(self.owner)
            return real_lock(obj)

        mutation_actor = User.objects.get(pk=self.owner.pk)
        with patch.object(services, "_lock_instance", side_effect=revoke_then_lock):
            with self.assertRaises(PermissionDenied):
                with content_mutation(
                    mutation_actor,
                    mpv,
                    action="edit",
                    proposed_parent=foreign,
                ) as row:
                    row.sample = foreign
                    row.save()
        mpv.refresh_from_db()
        self.assertEqual(mpv.sample_id, self.sample_a.pk)


class DeleteBoundaryTests(TestCase):
    """Same-pk cross-model cascades, auto-through rows, and SET_NULL field
    updates on foreign roots must all deny the delete."""

    def setUp(self):
        self.owner = User.objects.create_user(username="del-owner")

    def test_same_pk_cross_model_cascade_denied(self):
        author = Author.objects.create(
            pk=543_210,
            last_names="Doe",
            owner=self.owner,
            publication_status="private",
        )
        source = Source.objects.create(
            pk=543_210,
            title="S",
            owner=self.owner,
            publication_status="published",
        )
        link = SourceAuthor.objects.create(source=source, author=author, position=1)
        self.owner.user_permissions.add(_perm(Author, "delete_author"))
        with self.assertRaises(PermissionDenied):
            with content_mutation(self.owner, author, action="delete") as row:
                row.delete()
        self.assertTrue(Author.objects.filter(pk=author.pk).exists())
        self.assertTrue(SourceAuthor.objects.filter(pk=link.pk).exists())
        source.refresh_from_db()
        self.assertEqual(source.publication_status, "published")

    def test_auto_created_through_row_on_foreign_root_denied(self):
        method = AnalyticalMethod.objects.create(
            name="AM", owner=self.owner, publication_status="published"
        )
        source = Source.objects.create(
            title="S2", owner=self.owner, publication_status="private"
        )
        method.sources.add(source)
        self.owner.user_permissions.add(_perm(Source, "delete_source"))
        with self.assertRaises(PermissionDenied):
            with content_mutation(self.owner, source, action="delete") as row:
                row.delete()
        self.assertTrue(Source.objects.filter(pk=source.pk).exists())
        self.assertTrue(method.sources.filter(pk=source.pk).exists())

    def test_own_outgoing_m2m_rows_do_not_deny(self):
        self.owner.user_permissions.add(_perm(Sample, "delete_sample"))
        material = Material.objects.create(
            name="M", owner=self.owner, publication_status="private"
        )
        sample = Sample.objects.create(
            name="S",
            owner=self.owner,
            material=material,
            publication_status="private",
        )
        source = Source.objects.create(
            title="Linked", owner=self.owner, publication_status="published"
        )
        sample.sources.add(source)
        pk = sample.pk
        with content_mutation(self.owner, sample, action="delete") as row:
            row.delete()
        self.assertFalse(Sample.objects.filter(pk=pk).exists())
        self.assertTrue(Source.objects.filter(pk=source.pk).exists())

    def test_set_null_field_update_on_foreign_root_denied(self):
        region = Region.objects.create(
            name="R", owner=self.owner, publication_status="private"
        )
        material = Material.objects.create(
            name="M", owner=self.owner, publication_status="private"
        )
        sample = Sample.objects.create(
            name="S",
            owner=self.owner,
            material=material,
            region=region,
            publication_status="published",
        )
        self.owner.user_permissions.add(_perm(Region, "delete_region"))
        with self.assertRaises(PermissionDenied):
            with content_mutation(self.owner, region, action="delete") as row:
                row.delete()
        self.assertTrue(Region.objects.filter(pk=region.pk).exists())
        sample.refresh_from_db()
        self.assertEqual(sample.region_id, region.pk)


class ArchiveAuditTests(RevisionServiceBase):
    def setUp(self):
        super().setUp()
        self.prop.publication_status = "published"
        self.prop.save()
        self.moderator.user_permissions.add(_perm(Property, "can_moderate_property"))

    def test_archive_records_bound_audit_event(self):
        perform_transition(self.moderator, self.prop, "archive")
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.publication_status, "archived")
        event = _actions_for(self.prop, "archived").get()
        self.assertEqual(event.user, self.moderator)
        self.assertEqual(event.content_revision, 1)

    def test_archive_audit_failure_rolls_back_status(self):
        with patch.object(
            ReviewAction.objects, "create", side_effect=RuntimeError("audit")
        ):
            with self.assertRaises(RuntimeError):
                perform_transition(self.moderator, self.prop, "archive")
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.publication_status, "published")
        self.assertFalse(_actions_for(self.prop, "archived").exists())


class CreationDedupeTests(RevisionServiceBase):
    def test_repeated_record_creation_yields_single_event(self):
        record_creation(self.owner, self.prop)
        record_creation(self.owner, self.prop)
        record_creation(self.owner, self.prop)
        self.assertEqual(_actions_for(self.prop, "created").count(), 1)


class CollectionCascadeTests(TestCase):
    """Parent review actions must not implicitly mutate independent
    CPV/ACPV children, including children already in review."""

    def setUp(self):
        self.owner = User.objects.create_user(username="coll-owner")
        self.child_owner = User.objects.create_user(username="cpv-owner")
        self.moderator = User.objects.create_user(username="coll-moderator")
        self.moderator.user_permissions.add(
            _perm(Collection, "can_moderate_collection")
        )
        prop = Property.objects.create(
            name="Rate", owner=self.owner, publication_status="private"
        )
        self.collection = Collection.objects.create(
            owner=self.owner, publication_status="private"
        )
        self.cpv = CollectionPropertyValue.objects.create(
            collection=self.collection,
            property=prop,
            year=2022,
            average=50,
            owner=self.child_owner,
            publication_status="review",
        )
        self.acpv = AggregatedCollectionPropertyValue.objects.create(
            property=prop,
            year=2022,
            average=50,
            owner=self.child_owner,
            publication_status="review",
        )
        self.acpv.collections.add(self.collection)

    def test_moderator_reject_does_not_touch_review_children(self):
        perform_transition(self.owner, self.collection, "submit")
        perform_transition(self.moderator, self.collection, "reject")
        self.collection.refresh_from_db()
        self.cpv.refresh_from_db()
        self.acpv.refresh_from_db()
        self.assertEqual(self.collection.publication_status, "declined")
        self.assertEqual(self.cpv.publication_status, "review")
        self.assertEqual(self.acpv.publication_status, "review")
        self.assertFalse(_actions_for(self.cpv).exists())
        self.assertFalse(_actions_for(self.acpv).exists())

    def test_moderator_approve_does_not_touch_review_children(self):
        perform_transition(self.owner, self.collection, "submit")
        perform_transition(
            self.moderator,
            self.collection,
            "approve",
            expected_revision=self.collection.content_revision,
        )
        self.collection.refresh_from_db()
        self.cpv.refresh_from_db()
        self.acpv.refresh_from_db()
        self.assertEqual(self.collection.publication_status, "published")
        self.assertEqual(self.cpv.publication_status, "review")
        self.assertEqual(self.acpv.publication_status, "review")
        self.assertFalse(_actions_for(self.cpv).exists())
        self.assertFalse(_actions_for(self.acpv).exists())


class OwnedMtiFacetTests(TestCase):
    """Owned MTI facets share the root's counter identity but must yield
    and authorize the actual facet instance."""

    def setUp(self):
        self.owner = User.objects.create_user(username="mti-owner")
        self.owner.user_permissions.add(_perm(Region, "change_region"))

    def _geo_region(self, status="private"):
        """Facet and root forced onto the same pk to exercise the shared
        counter-identity path deterministically."""
        region = Region.objects.create(owner=self.owner, publication_status=status)
        poly = GeoPolygon.objects.create(fid=region.pk)
        return GeoreferencedRegion.objects.create(
            geopolygon_ptr_id=poly.pk,
            region_ptr_id=region.pk,
            name="GeoR",
            owner=self.owner,
            publication_status=status,
        )

    def test_georeferencedregion_edit_yields_child_and_bumps_root_once(self):
        geo = self._geo_region()
        seen = {}
        with content_mutation(self.owner, geo, action="edit") as row:
            seen["type"] = type(row)
            row.name = "GeoR renamed"
            row.save()
        self.assertIs(seen["type"], GeoreferencedRegion)
        region = geo.region_ptr
        region.refresh_from_db()
        self.assertEqual(region.name, "GeoR renamed")
        self.assertEqual(region.content_revision, 2)
        self.assertEqual(_actions_for(region, "edited").count(), 1)

    def test_published_root_denies_owned_facet_edit(self):
        geo = self._geo_region()
        Region.objects.filter(pk=geo.region_ptr_id).update(
            publication_status="published"
        )
        with self.assertRaises(PermissionDenied):
            with content_mutation(self.owner, geo, action="edit") as row:
                row.name = "forbidden"
                row.save()
        geo.refresh_from_db()
        self.assertEqual(geo.name, "GeoR")

    def test_georeferencednutsregion_edit_yields_child(self):
        self.owner.user_permissions.add(_perm(NutsRegion, "change_nutsregion"))
        vintage = NutsVintage.objects.first() or NutsVintage.objects.create(
            year=2021, is_current=True
        )
        nuts = NutsRegion.objects.create(
            name="N",
            nuts_id="DE9",
            levl_code=1,
            cntr_code="DE",
            version=vintage,
            owner=self.owner,
            publication_status="private",
        )
        poly = GeoPolygon.objects.create(fid=nuts.pk)
        geo = GeoreferencedNutsRegion.objects.create(
            geopolygon_ptr_id=poly.pk,
            nutsregion_ptr_id=nuts.pk,
            name="N",
            owner=self.owner,
            publication_status="private",
        )
        seen = {}
        with content_mutation(self.owner, geo, action="edit") as row:
            seen["type"] = type(row)
            row.name = "N renamed"
            row.save()
        self.assertIs(seen["type"], GeoreferencedNutsRegion)
        nuts.refresh_from_db()
        self.assertEqual(nuts.name, "N renamed")
        self.assertEqual(nuts.content_revision, 2)
