"""Phase-A contract tests for source-governed generated CPV projections.

Generated CollectionPropertyValue rows are read-only projections of their
explicitly linked raw source evidence. These tests construct the explicit
``derived_from`` linkage directly; they do not exercise the numerical
generator, which remains a phase-B boundary.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from utils.object_management import checks
from utils.object_management.models import ReviewAction
from utils.object_management.permissions import (
    apply_scope_filter,
    get_object_policy,
)
from utils.object_management.policy import (
    capabilities,
    decide,
    editable_queryset,
    object_access_routes,
    reviewable_queryset,
    scope_queryset,
    visible_queryset,
)
from utils.object_management.registry import (
    GENERATED_PROJECTIONS,
    KIND_GENERATED,
    KIND_REVIEWABLE,
    generated_source,
    record_policy,
    review_target,
)
from utils.object_management.services import (
    content_mutation,
    perform_transition,
    record_comment,
    record_creation,
)
from utils.properties.models import Property, Unit

from ..models import (
    Collection,
    CollectionCatchment,
    CollectionPropertyValue,
    CollectionSystem,
    WasteCategory,
)
from ..serializers import CollectionPropertyValueSerializer


def _cpv_ct():
    return ContentType.objects.get_for_model(CollectionPropertyValue)


class GeneratedProjectionFixtureMixin:
    """Shared fixtures: a raw source CPV plus explicitly linked projections."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="gp-owner")
        cls.stranger = User.objects.create_user(username="gp-stranger")
        cls.editor = User.objects.create_user(username="gp-editor")
        cls.group_editor = User.objects.create_user(username="gp-group-editor")
        cls.editor_group = Group.objects.create(name="gp-editors")
        cls.editor_group.user_set.add(cls.group_editor)
        cls.moderator = User.objects.create_user(username="gp-moderator")
        cls.administrator = User.objects.create_user(username="gp-admin")
        cls.superuser = User.objects.create_superuser(
            username="gp-root", email="root@example.com", password="pw"
        )
        cpv_ct = _cpv_ct()
        cls.moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_collectionpropertyvalue",
                content_type=cpv_ct,
            )
        )
        cls.administer_permission, _ = Permission.objects.get_or_create(
            codename="administer_objects",
            content_type=ContentType.objects.get_for_model(ReviewAction),
            defaults={"name": "Can administer objects"},
        )
        cls.administrator.user_permissions.add(cls.administer_permission)
        for codename in (
            "add_collectionpropertyvalue",
            "change_collectionpropertyvalue",
            "delete_collectionpropertyvalue",
        ):
            cls.owner.user_permissions.add(
                Permission.objects.get(codename=codename, content_type=cpv_ct)
            )

        cls.source_property = Property.objects.create(
            name="projection source property [test]",
            owner=cls.owner,
            publication_status="published",
        )
        cls.projection_property = Property.objects.create(
            name="projection target property [test]",
            owner=cls.owner,
            publication_status="published",
        )
        cls.unit = Unit.objects.create(
            name="projection unit [test]",
            owner=cls.owner,
            publication_status="published",
        )
        cls.other_unit = Unit.objects.create(
            name="projection other unit [test]",
            owner=cls.owner,
            publication_status="published",
        )
        catchment = CollectionCatchment.objects.create(
            name="Projection catchment [test]"
        )
        cls.collection_system = CollectionSystem.objects.create(
            name="Projection system [test]",
            owner=cls.owner,
            publication_status="published",
        )
        cls.waste_category = WasteCategory.objects.create(
            name="Projection category [test]",
            owner=cls.owner,
            publication_status="published",
        )
        cls.collection = Collection.objects.create(
            name="Projection collection [test]",
            catchment=catchment,
            collection_system=cls.collection_system,
            waste_category=cls.waste_category,
            valid_from=date(2024, 1, 1),
            owner=cls.owner,
            publication_status="published",
        )

    def _source(self, status="private", owner=None, year=2024):
        return CollectionPropertyValue.objects.create(
            name=f"raw source {status}",
            collection=self.collection,
            property=self.source_property,
            unit=self.unit,
            year=year,
            average=10,
            owner=owner or self.owner,
            publication_status=status,
            is_derived=False,
        )

    def _generated(
        self,
        source,
        *,
        owner=None,
        publication_status="private",
        property=None,
        unit=None,
    ):
        """Build an explicitly linked projection with divergent copied metadata."""
        if property is None:
            # Derived rows are unique on (collection, property, year); give
            # every projection its own non-convertible property.
            self._projection_property_counter = (
                getattr(self, "_projection_property_counter", 0) + 1
            )
            property = Property.objects.create(
                name=(
                    "projection target property [test] "
                    f"{self._projection_property_counter}"
                ),
                owner=self.owner,
                publication_status="published",
            )
        return CollectionPropertyValue.objects.create(
            name=f"projection of {source.pk}",
            collection=self.collection,
            property=property,
            unit=unit or self.other_unit,
            year=source.year,
            average=42,
            owner=owner or self.stranger,
            publication_status=publication_status,
            is_derived=True,
            derived_from=source,
        )


class GeneratedProjectionDecisionTests(GeneratedProjectionFixtureMixin, TestCase):
    def test_raw_cpv_decisions_unchanged(self):
        raw = self._source("published")
        self.assertTrue(decide(AnonymousUser(), "read", raw).allowed)
        self.assertFalse(decide(self.owner, "edit", raw).allowed)
        private = self._source("private")
        self.assertEqual(
            decide(AnonymousUser(), "read", private).reason,
            "authentication_required",
        )
        self.assertEqual(record_policy(raw).kind, "reviewable")

    def test_published_source_projection_readable_anonymously(self):
        source = self._source("published")
        projection = self._generated(source, publication_status="private")
        self.assertTrue(decide(AnonymousUser(), "read", projection).allowed)
        self.assertTrue(decide(AnonymousUser(), "export", projection).allowed)

    def test_archived_source_projection_readable_anonymously(self):
        source = self._source("archived")
        projection = self._generated(source, publication_status="private")
        self.assertTrue(decide(AnonymousUser(), "read", projection).allowed)

    def test_private_source_denies_anonymous_and_stranger(self):
        source = self._source("private")
        projection = self._generated(
            source,
            owner=self.stranger,
            publication_status="published",
        )
        self.assertEqual(
            decide(AnonymousUser(), "read", projection).reason,
            "authentication_required",
        )
        # The projection's own copied owner/status never widens source access.
        self.assertEqual(
            decide(self.stranger, "read", projection).reason,
            "no_object_access",
        )

    def test_source_owner_and_editors_read_projection(self):
        source = self._source("private")
        source.add_editor(self.editor)
        source.add_editor_group(self.editor_group)
        projection = self._generated(source)
        for user in (self.owner, self.editor, self.group_editor, self.administrator):
            self.assertTrue(
                decide(user, "read", projection).allowed,
                f"{user.username} should read via the source",
            )

    def test_projection_grants_do_not_confer_private_source_access(self):
        source = self._source("private")
        projection = self._generated(source, owner=self.stranger)
        projection.add_editor(self.editor)
        projection.add_editor_group(self.editor_group)
        # Neither the copied owner nor direct/group grants on the projection
        # confers access when the source is private.
        self.assertFalse(decide(self.stranger, "read", projection).allowed)
        self.assertFalse(decide(self.editor, "read", projection).allowed)
        self.assertFalse(decide(self.group_editor, "read", projection).allowed)

    def test_source_revocation_applies_immediately(self):
        source = self._source("private")
        projection = self._generated(source)
        source.add_editor(self.stranger)
        self.assertTrue(decide(self.stranger, "read", projection).allowed)
        source.remove_editor(self.stranger)
        self.assertFalse(
            decide(User.objects.get(pk=self.stranger.pk), "read", projection).allowed
        )

    def test_review_participation_follows_source_capabilities(self):
        source = self._source("review")
        projection = self._generated(source)
        for action in ("view_review_activity", "comment_on_review"):
            self.assertTrue(decide(self.owner, action, projection).allowed)
            self.assertTrue(decide(self.moderator, action, projection).allowed)
            self.assertFalse(decide(self.stranger, action, projection).allowed)

    def test_all_standalone_mutations_denied_generated_projection(self):
        source = self._source("review")
        projection = self._generated(source)
        denied_actions = (
            "edit",
            "delete",
            "create",
            "submit",
            "withdraw",
            "approve",
            "reject",
            "archive",
            "duplicate",
            "new_version",
            "manage_editors",
            "transfer_ownership",
            "check_url",
        )
        for user in (self.owner, self.administrator, self.superuser):
            for action in denied_actions:
                decision = decide(user, action, projection)
                self.assertFalse(
                    decision.allowed,
                    f"{action} must be denied for {user.username}",
                )
                self.assertEqual(
                    decision.reason,
                    "generated_projection",
                    f"{action} must deny with generated_projection",
                )

    def test_missing_source_fails_closed_for_admin(self):
        source = self._source("private")
        projection = self._generated(source)
        projection.derived_from = None
        projection.save(update_fields=["derived_from"])
        self.assertEqual(
            decide(self.superuser, "read", projection).reason, "invalid_parent"
        )
        self.assertEqual(
            decide(self.administrator, "read", projection).reason, "invalid_parent"
        )

    def test_self_referential_and_generated_source_fail_closed(self):
        source = self._source("private")
        inner = self._generated(source)
        chained = self._generated(inner)
        self.assertEqual(
            decide(self.superuser, "read", chained).reason, "invalid_parent"
        )
        self_referential = self._generated(self._source("private"))
        CollectionPropertyValue.objects.filter(pk=self_referential.pk).update(
            derived_from=self_referential
        )
        self_referential.refresh_from_db()
        self.assertEqual(
            decide(self.superuser, "read", self_referential).reason,
            "invalid_parent",
        )

    def test_source_invalid_lifecycle_fails_closed(self):
        source = self._source("private")
        projection = self._generated(source)
        CollectionPropertyValue.objects.filter(pk=source.pk).update(
            publication_status="bogus"
        )
        source.refresh_from_db()
        projection.refresh_from_db()
        self.assertFalse(decide(self.owner, "read", projection).allowed)

    def test_class_level_create_still_means_raw_evidence(self):
        contributor = User.objects.create_user(username="gp-contributor")
        contributor.user_permissions.add(
            Permission.objects.get(
                codename="add_collectionpropertyvalue", content_type=_cpv_ct()
            )
        )
        self.assertTrue(decide(contributor, "create", CollectionPropertyValue).allowed)

    def test_raw_record_cannot_carry_source_pointer(self):
        source = self._source("private")
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                CollectionPropertyValue.objects.create(
                    name="forged pointer",
                    collection=self.collection,
                    property=self.source_property,
                    unit=self.unit,
                    year=2024,
                    average=1,
                    owner=self.owner,
                    publication_status="private",
                    is_derived=False,
                    derived_from=source,
                )

    def test_access_routes_explain_generated_source_governance(self):
        source = self._source("private")
        projection = self._generated(source)
        routes = object_access_routes(self.owner, projection)
        self.assertIn("owner", routes)
        self.assertIn(
            "generated value (read-only; governed by source evidence)", routes
        )

    def test_capabilities_reflect_source_not_copied_metadata(self):
        source = self._source("private")
        projection = self._generated(
            source, owner=self.stranger, publication_status="published"
        )
        caps = capabilities(self.stranger, projection)
        self.assertFalse(caps["read"].allowed)
        self.assertEqual(caps["edit"].reason, "generated_projection")
        owner_caps = capabilities(self.owner, projection)
        self.assertTrue(owner_caps["read"].allowed)
        self.assertFalse(owner_caps["edit"].allowed)


class GeneratedProjectionQuerysetTests(GeneratedProjectionFixtureMixin, TestCase):
    def test_visible_queryset_follows_source(self):
        public_source = self._source("published")
        public_projection = self._generated(public_source)
        private_source = self._source("private")
        private_projection = self._generated(
            private_source, publication_status="published", owner=self.stranger
        )
        qs = CollectionPropertyValue.objects.all()

        anonymous_visible = visible_queryset(AnonymousUser(), qs)
        self.assertIn(public_projection, anonymous_visible)
        self.assertNotIn(private_projection, anonymous_visible)

        stranger_visible = visible_queryset(self.stranger, qs)
        self.assertNotIn(private_projection, stranger_visible)

        owner_visible = visible_queryset(self.owner, qs)
        self.assertIn(private_projection, owner_visible)

    def test_scopes_follow_source_state_and_grants(self):
        published_source = self._source("published")
        published_projection = self._generated(published_source)
        private_source = self._source("private")
        private_projection = self._generated(private_source)
        review_source = self._source("review")
        review_projection = self._generated(review_source)
        qs = CollectionPropertyValue.objects.all()

        published_scope = scope_queryset(self.stranger, qs, "published")
        self.assertIn(published_projection, published_scope)
        self.assertNotIn(private_projection, published_scope)
        self.assertNotIn(review_projection, published_scope)

        owned_scope = scope_queryset(self.owner, qs, "owned")
        self.assertIn(private_projection, owned_scope)

        private_scope = scope_queryset(self.owner, qs, "private")
        self.assertIn(private_projection, private_scope)
        # The workspace scope holds every owned source, whatever its
        # lifecycle state — projections follow their source here too.
        self.assertIn(published_projection, private_scope)

        review_scope = scope_queryset(self.moderator, qs, "review")
        self.assertIn(review_projection, review_scope)

        shared_source = self._source("private")
        shared_source.add_editor(self.stranger)
        shared_projection = self._generated(shared_source)
        shared_scope = scope_queryset(self.stranger, qs, "shared")
        self.assertIn(shared_projection, shared_scope)
        self.assertNotIn(shared_projection, scope_queryset(self.owner, qs, "shared"))

        self.assertEqual(
            list(scope_queryset(self.owner, qs, "bogus-scope")),
            [],
        )

    def test_caller_filters_preserved_and_different_property_still_visible(self):
        source = self._source("published")
        projection = self._generated(source, property=self.projection_property)
        qs = CollectionPropertyValue.objects.filter(property=self.projection_property)
        visible = visible_queryset(AnonymousUser(), qs)
        self.assertIn(projection, visible)
        # The differently typed raw source is not dragged into the caller qs.
        self.assertNotIn(source, visible)

        private_source = self._source("private", year=2023)
        private_projection = self._generated(
            private_source, property=self.projection_property
        )
        self.assertNotIn(private_projection, visible_queryset(AnonymousUser(), qs))
        self.assertIn(private_projection, visible_queryset(self.owner, qs))

    def test_legacy_null_source_projection_fails_closed_in_querysets(self):
        self._source("published")
        orphan = CollectionPropertyValue.objects.create(
            name="orphan projection",
            collection=self.collection,
            property=self.projection_property,
            unit=self.other_unit,
            year=2024,
            average=42,
            owner=self.owner,
            publication_status="published",
            is_derived=True,
            derived_from=None,
        )
        qs = CollectionPropertyValue.objects.all()
        self.assertNotIn(orphan, visible_queryset(AnonymousUser(), qs))
        self.assertNotIn(orphan, visible_queryset(self.owner, qs))
        self.assertNotIn(orphan, scope_queryset(AnonymousUser(), qs, "published"))

    def test_editable_and_reviewable_querysets_exclude_generated(self):
        source = self._source("review")
        projection = self._generated(source, publication_status="review")
        qs = CollectionPropertyValue.objects.all()

        editable = editable_queryset(self.owner, qs)
        self.assertNotIn(projection, editable)

        reviewable = reviewable_queryset(self.moderator, qs)
        self.assertIn(source, reviewable)
        self.assertNotIn(projection, reviewable)


class GeneratedProjectionMutationTests(GeneratedProjectionFixtureMixin, TestCase):
    def test_content_mutation_rejects_generated_target(self):
        source = self._source("private")
        projection = self._generated(source)
        with self.assertRaises(PermissionDenied) as ctx:
            with content_mutation(self.administrator, projection, action="edit"):
                pass  # pragma: no cover - the boundary must raise first
        self.assertIn("generated_projection", str(ctx.exception))

        projection.refresh_from_db()
        self.assertEqual(projection.average, 42)
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=_cpv_ct(), object_id=projection.pk
            ).exists()
        )

    def test_perform_transition_rejects_generated_target(self):
        source = self._source("private")
        projection = self._generated(source)
        for action in ("submit", "withdraw", "approve", "reject", "archive"):
            with self.assertRaises(PermissionDenied):
                perform_transition(self.administrator, projection, action)
        projection.refresh_from_db()
        self.assertEqual(projection.publication_status, "private")

    def test_record_creation_skips_generated(self):
        source = self._source("private")
        projection = self._generated(source)
        record_creation(self.owner, projection)
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=_cpv_ct(),
                object_id=projection.pk,
                action=ReviewAction.ACTION_CREATED,
            ).exists()
        )
        raw = self._source("private")
        record_creation(self.owner, raw)
        self.assertTrue(
            ReviewAction.objects.filter(
                content_type=_cpv_ct(),
                object_id=raw.pk,
                action=ReviewAction.ACTION_CREATED,
            ).exists()
        )

    def test_record_comment_binds_source_thread_and_revision(self):
        source = self._source("review")
        source.content_revision = 3
        source.save(update_fields=["content_revision"])
        projection = self._generated(source)
        event = record_comment(
            self.moderator, projection, "looks right", expected_revision=3
        )
        self.assertEqual(event.object_id, source.pk)
        self.assertEqual(event.content_revision, 3)
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=_cpv_ct(), object_id=projection.pk
            ).exists()
        )

    def test_source_delete_cascades_to_linked_generated_only(self):
        source = self._source("private")
        projection = self._generated(source)
        other_source = self._source("private")
        foreign_projection = self._generated(other_source)
        manual = self._source("private")

        with content_mutation(self.owner, source, action="delete") as locked:
            locked.delete()

        self.assertFalse(CollectionPropertyValue.objects.filter(pk=source.pk).exists())
        self.assertFalse(
            CollectionPropertyValue.objects.filter(pk=projection.pk).exists()
        )
        self.assertTrue(
            CollectionPropertyValue.objects.filter(pk=other_source.pk).exists()
        )
        self.assertTrue(
            CollectionPropertyValue.objects.filter(pk=foreign_projection.pk).exists()
        )
        self.assertTrue(CollectionPropertyValue.objects.filter(pk=manual.pk).exists())

    def test_audit_failure_rolls_back_source_and_generated_delete(self):
        source = self._source("private")
        projection = self._generated(source)
        with (
            patch(
                "utils.object_management.services._record_event",
                side_effect=RuntimeError("audit transport failed"),
            ),
            self.assertRaises(RuntimeError),
        ):
            with content_mutation(self.owner, source, action="delete") as locked:
                locked.delete()
        self.assertTrue(CollectionPropertyValue.objects.filter(pk=source.pk).exists())
        self.assertTrue(
            CollectionPropertyValue.objects.filter(pk=projection.pk).exists()
        )

    def test_http_update_and_delete_deny_generated(self):
        source = self._source("private")
        projection = self._generated(source)
        client = Client()
        client.force_login(self.owner)

        response = client.post(
            reverse("collectionpropertyvalue-update", args=[projection.pk]),
            data={"average": 99},
        )
        self.assertEqual(response.status_code, 403)
        response = client.post(
            reverse("collectionpropertyvalue-delete-modal", args=[projection.pk])
        )
        self.assertEqual(response.status_code, 403)
        projection.refresh_from_db()
        self.assertEqual(projection.average, 42)

    def test_http_lifecycle_actions_deny_generated(self):
        source = self._source("review")
        projection = self._generated(source, publication_status="review")
        ct = _cpv_ct()
        client = Client()
        client.force_login(self.superuser)
        for url_name in (
            "object_management:submit_for_review",
            "object_management:withdraw_from_review",
            "object_management:approve_item",
            "object_management:reject_item",
        ):
            response = client.post(
                reverse(
                    url_name,
                    kwargs={
                        "content_type_id": ct.pk,
                        "object_id": projection.pk,
                    },
                )
            )
            self.assertEqual(
                response.status_code, 403, f"{url_name} must deny the projection"
            )
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=ct, object_id=projection.pk
            ).exists()
        )

    def test_http_admin_change_denies_generated(self):
        source = self._source("private")
        projection = self._generated(source)
        client = Client()
        client.force_login(self.superuser)
        response = client.post(
            reverse(
                "admin:waste_collection_collectionpropertyvalue_change",
                args=[projection.pk],
            ),
            data={
                "name": "forged",
                "collection": self.collection.pk,
                "property": self.projection_property.pk,
                "unit": self.other_unit.pk,
                "year": 2024,
                "average": 99,
                "is_derived": "on",
            },
        )
        self.assertEqual(response.status_code, 403)
        projection.refresh_from_db()
        self.assertEqual(projection.average, 42)

    def test_api_list_and_detail_read_parity(self):
        public_source = self._source("published")
        public_projection = self._generated(public_source)
        private_source = self._source("private")
        private_projection = self._generated(
            private_source, publication_status="published", owner=self.stranger
        )

        response = Client().get(reverse("api-waste-collection-property-value-list"))
        self.assertEqual(response.status_code, 200)
        ids = {row["id"] for row in response.data["results"]}
        self.assertIn(public_projection.pk, ids)
        self.assertNotIn(private_projection.pk, ids)

        owner_client = Client()
        owner_client.force_login(self.owner)
        response = owner_client.get(
            reverse("api-waste-collection-property-value-list"),
            {"scope": "private"},
        )
        self.assertEqual(response.status_code, 200)
        ids = {row["id"] for row in response.data["results"]}
        self.assertIn(private_projection.pk, ids)

        # HTML detail delegates read to the source lifecycle as well.
        public_detail = reverse(
            "collectionpropertyvalue-detail", args=[public_projection.pk]
        )
        self.assertEqual(Client().get(public_detail).status_code, 200)
        private_detail = reverse(
            "collectionpropertyvalue-detail", args=[private_projection.pk]
        )
        self.assertEqual(owner_client.get(private_detail).status_code, 200)
        self.assertNotEqual(Client().get(private_detail).status_code, 200)

    def test_review_queue_excludes_generated(self):
        source = self._source("review")
        self._generated(source, publication_status="review")
        queue = reviewable_queryset(
            self.moderator, CollectionPropertyValue.objects.all()
        )
        self.assertIn(source, queue)
        self.assertFalse(queue.filter(is_derived=True).exists())


class GeneratedProjectionPayloadTests(GeneratedProjectionFixtureMixin, TestCase):
    def _create_payload(self, **extra):
        payload = {
            "collection": self.collection.pk,
            "property_id": self.source_property.pk,
            "unit_name": self.unit.name,
            "year": 2024,
            "average": 12,
            "submit_for_review": False,
        }
        payload.update(extra)
        return payload

    def test_public_create_cannot_forge_generated_marker_or_source(self):
        raw = self._source("published")
        client = Client()
        client.force_login(self.owner)
        response = client.post(
            reverse("api-waste-collection-property-value-create"),
            data=self._create_payload(
                is_derived=True,
                derived_from=raw.pk,
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        created = CollectionPropertyValue.objects.get(pk=response.data["id"])
        self.assertFalse(created.is_derived)
        self.assertIsNone(created.derived_from_id)

    def test_public_update_cannot_toggle_marker_or_source(self):
        raw = self._source("private")
        client = Client()
        client.force_login(self.owner)
        client.post(
            reverse("collectionpropertyvalue-update", args=[raw.pk]),
            data={
                "name": raw.name,
                "collection": self.collection.pk,
                "property": self.source_property.pk,
                "unit": self.unit.pk,
                "year": 2024,
                "average": 15,
                "is_derived": "on",
                "derived_from": raw.pk,
                "wasteflyer_set-TOTAL_FORMS": "0",
                "wasteflyer_set-INITIAL_FORMS": "0",
                "wasteflyer_set-MIN_NUM_FORMS": "0",
                "wasteflyer_set-MAX_NUM_FORMS": "1000",
            },
        )
        raw.refresh_from_db()
        self.assertFalse(raw.is_derived)
        self.assertIsNone(raw.derived_from_id)

    def test_serializer_exposes_source_link_and_source_lifecycle(self):
        source = self._source("published")
        projection = self._generated(source, publication_status="private")
        data = CollectionPropertyValueSerializer(projection).data
        self.assertEqual(data["derived_from"], source.pk)
        # Lifecycle display reflects the source, not the stale copied field.
        self.assertEqual(data["publication_status"], "published")

        # Lifecycle change without save(): the source is intentionally
        # non-convertible so the generator leaves the explicit fixture alone.
        CollectionPropertyValue.objects.filter(pk=source.pk).update(
            publication_status="private"
        )
        projection.refresh_from_db()
        data = CollectionPropertyValueSerializer(projection).data
        self.assertEqual(data["publication_status"], "private")


class GeneratedProjectionRegistryTests(GeneratedProjectionFixtureMixin, TestCase):
    def test_record_policy_classification(self):
        source = self._source("private")
        projection = self._generated(source)
        self.assertEqual(record_policy(projection).kind, KIND_GENERATED)
        self.assertEqual(record_policy(source).kind, "reviewable")
        self.assertEqual(record_policy(projection).parent_path, "derived_from")

    def test_system_checks_validate_generated_profile(self):
        stdout = __import__("io").StringIO()
        call_command("check", stdout=stdout, stderr=stdout)
        self.assertNotIn("object_management.E", stdout.getvalue())


class GeneratedProjectionAtlasTests(GeneratedProjectionFixtureMixin, TestCase):
    def test_atlas_public_membership_follows_source_lifecycle(self):
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        from ..waste_atlas.viewsets import _property_value_q

        source = self._source("private")
        projection = self._generated(source)
        qs = CollectionPropertyValue.objects.filter(_property_value_q())

        self.assertNotIn(projection, qs)

        workspace_request = Request(APIRequestFactory().get("/", {"scope": "mine"}))
        workspace_request.user = self.owner
        self.assertIn(
            projection,
            CollectionPropertyValue.objects.filter(
                _property_value_q(workspace_request)
            ),
        )

        CollectionPropertyValue.objects.filter(pk=source.pk).update(
            publication_status="published"
        )
        self.assertIn(
            projection,
            CollectionPropertyValue.objects.filter(_property_value_q()),
        )

        CollectionPropertyValue.objects.filter(pk=source.pk).update(
            publication_status="archived"
        )
        self.assertIn(
            projection,
            CollectionPropertyValue.objects.filter(_property_value_q()),
        )


class GeneratedProjectionLiveAdapterTests(GeneratedProjectionFixtureMixin, TestCase):
    """Live HTTP/adapters — queue, review detail, context, template, policy."""

    def _dashboard_items(self, user):
        from utils.object_management.views import ReviewDashboardView

        request = RequestFactory().get("/review/")
        request.user = user
        view = ReviewDashboardView()
        view.request = request
        view.paginate_by = 50
        view._available_models_cache = None
        return view.collect_review_items()

    def test_dashboard_collect_review_items_excludes_generated(self):
        source = self._source("review")
        projection = self._generated(source, publication_status="review")
        items = self._dashboard_items(self.moderator)
        self.assertIn(source, items)
        self.assertNotIn(projection, items)

    def test_model_discovery_skips_profiled_model_with_only_generated(self):
        # Copied stale review state on the projection alone must not make
        # the model discoverable for moderation.
        source = self._source("private")
        self._generated(source, publication_status="review")
        request = RequestFactory().get("/review/")
        request.user = self.moderator
        from utils.object_management.views import ReviewDashboardView

        view = ReviewDashboardView()
        view.request = request
        view._available_models_cache = None
        self.assertNotIn(CollectionPropertyValue, view.get_available_models())

    def test_review_queue_api_excludes_generated(self):
        source = self._source("review")
        projection = self._generated(source, publication_status="review")
        client = Client()
        client.force_login(self.moderator)
        response = client.get(reverse("object_management:api_review_queue"))
        self.assertEqual(response.status_code, 200)
        ids = {row["object_id"] for row in response.data["results"]}
        self.assertIn(source.pk, ids)
        self.assertNotIn(projection.pk, ids)

    def test_inactive_moderator_gets_no_queue_items(self):
        self._source("review")
        self.moderator.is_active = False
        self.moderator.save()
        items = self._dashboard_items(User.objects.get(pk=self.moderator.pk))
        self.assertFalse(
            any(isinstance(item, CollectionPropertyValue) for item in items)
        )

    def test_review_item_detail_redirects_generated_to_source(self):
        source = self._source("review")
        projection = self._generated(source, publication_status="review")
        ct = _cpv_ct()
        client = Client()
        client.force_login(self.owner)
        response = client.get(
            reverse(
                "object_management:review_item_detail",
                kwargs={"content_type_id": ct.pk, "object_id": projection.pk},
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse(
                "object_management:review_item_detail",
                kwargs={"content_type_id": ct.pk, "object_id": source.pk},
            ),
        )

    def test_review_item_detail_raw_source_unchanged(self):
        source = self._source("review")
        ct = _cpv_ct()
        client = Client()
        client.force_login(self.owner)
        response = client.get(
            reverse(
                "object_management:review_item_detail",
                kwargs={"content_type_id": ct.pk, "object_id": source.pk},
            )
        )
        self.assertEqual(response.status_code, 200)

    def test_review_item_detail_stranger_denied(self):
        source = self._source("review")
        projection = self._generated(source, publication_status="review")
        ct = _cpv_ct()
        client = Client()
        client.force_login(self.stranger)
        response = client.get(
            reverse(
                "object_management:review_item_detail",
                kwargs={"content_type_id": ct.pk, "object_id": projection.pk},
            )
        )
        self.assertEqual(response.status_code, 403)

    def test_review_context_api_uses_source_and_marks_projection(self):
        source = self._source("review")
        source.content_revision = 3
        source.save(update_fields=["content_revision"])
        projection = self._generated(source, publication_status="private")
        projection.content_revision = 1
        projection.save(update_fields=["content_revision"])
        record_comment(self.moderator, source, "source note", expected_revision=3)

        ct = _cpv_ct()
        client = Client()
        client.force_login(self.moderator)
        response = client.get(
            reverse(
                "object_management:api_review_context",
                kwargs={"content_type_id": ct.pk, "object_id": projection.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        context = response.data["context"]
        obj = context["object"]
        self.assertEqual(obj["object_id"], source.pk)
        self.assertEqual(obj["content_revision"], 3)
        self.assertEqual(obj["owner_id"], self.owner.pk)
        self.assertEqual(obj["publication_status"], "review")
        self.assertEqual(
            context["projection"],
            {
                "object_id": projection.pk,
                "derived_from": source.pk,
                "read_only": True,
            },
        )
        history_comments = [
            entry["comment"] for entry in context.get("review_history", [])
        ]
        self.assertIn("source note", history_comments)
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=ct, object_id=projection.pk
            ).exists()
        )

    def test_comment_api_on_projection_binds_source_thread(self):
        source = self._source("review")
        source.content_revision = 3
        source.save(update_fields=["content_revision"])
        projection = self._generated(source)
        ct = _cpv_ct()
        client = Client()
        client.force_login(self.moderator)
        response = client.post(
            reverse(
                "object_management:api_add_review_comment",
                kwargs={"content_type_id": ct.pk, "object_id": projection.pk},
            ),
            data={"comment": "via projection", "expected_revision": 3},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            ReviewAction.objects.get(pk=response.data["id"]).object_id, source.pk
        )
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=ct, object_id=projection.pk
            ).exists()
        )

    def test_object_policy_display_follows_source_capabilities_on_projection(
        self,
    ):
        source = self._source("review")
        source.add_editor(self.editor)
        projection = self._generated(
            source, publication_status="published", owner=self.stranger
        )

        owner_policy = get_object_policy(self.owner, projection)
        # Display reflects the source lifecycle/ownership, not copied data.
        self.assertTrue(owner_policy["is_owner"])
        self.assertTrue(owner_policy["is_in_review"])
        self.assertFalse(owner_policy["is_published"])
        self.assertFalse(owner_policy["can_edit"])
        self.assertEqual(owner_policy["reason_codes"]["edit"], "generated_projection")
        self.assertTrue(owner_policy["can_view_review_activity"])

        editor_policy = get_object_policy(self.editor, projection)
        self.assertTrue(editor_policy["is_editor"])

        stranger_policy = get_object_policy(self.stranger, projection)
        self.assertFalse(stranger_policy["is_owner"])

    def test_object_policy_export_list_type_maps_source_lifecycle(self):
        archived_source = self._source("archived")
        archived_projection = self._generated(
            archived_source, publication_status="private"
        )
        policy = get_object_policy(self.stranger, archived_projection)
        self.assertTrue(policy["is_archived"])
        self.assertTrue(policy["can_export"])
        self.assertEqual(policy["export_list_type"], "archived")

        published_source = self._source("published")
        published_projection = self._generated(
            published_source, publication_status="private"
        )
        self.assertEqual(
            get_object_policy(self.stranger, published_projection)["export_list_type"],
            "published",
        )

    def test_detail_review_panel_uses_activity_capability_and_source_logs(
        self,
    ):
        source = self._source("review")
        source.content_revision = 2
        source.save(update_fields=["content_revision"])
        record_comment(self.moderator, source, "source thread note")
        projection = self._generated(source)
        url = reverse("collectionpropertyvalue-detail", args=[projection.pk])

        owner_client = Client()
        owner_client.force_login(self.owner)
        response = owner_client.get(url, {"review": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["show_review_panel"])
        self.assertContains(response, "source thread note")

    def test_detail_panel_hidden_from_public_reader(self):
        source = self._source("published")
        record_comment(self.moderator, source, "internal note")
        projection = self._generated(source)
        url = reverse("collectionpropertyvalue-detail", args=[projection.pk])
        response = Client().get(url, {"review": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["show_review_panel"])
        self.assertNotContains(response, "internal note")

    def test_detail_template_shows_generated_source_governance(self):
        source = self._source("private")
        projection = self._generated(
            source, publication_status="published", owner=self.stranger
        )
        client = Client()
        client.force_login(self.owner)
        response = client.get(
            reverse("collectionpropertyvalue-detail", args=[projection.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, source.get_absolute_url())
        self.assertContains(response, "read-only")
        # Governance badge/owner/state describe the private source, not the
        # copied published projection metadata.
        self.assertContains(response, "Private: available to the owner and current")


class GeneratedProjectionExportSeamTests(GeneratedProjectionFixtureMixin, TestCase):
    def test_scope_filter_uses_source_lifecycle_not_copied_status(self):
        published_source = self._source("published")
        published_projection = self._generated(
            published_source, publication_status="private"
        )
        private_source = self._source("private")
        hidden_projection = self._generated(
            private_source, publication_status="published", owner=self.stranger
        )
        qs = CollectionPropertyValue.objects.all()

        published = apply_scope_filter(qs, "published", user=self.stranger)
        self.assertIn(published_source, published)
        self.assertIn(published_projection, published)
        self.assertNotIn(hidden_projection, published)

    def test_archived_scope_shows_archived_source_to_unrelated_reader(self):
        archived_source = self._source("archived")
        archived_projection = self._generated(
            archived_source, publication_status="private"
        )
        qs = CollectionPropertyValue.objects.all()
        archived = apply_scope_filter(qs, "archived", user=self.stranger)
        self.assertIn(archived_source, archived)
        self.assertIn(archived_projection, archived)

    def test_export_seed_params_skip_raw_status_for_profiled_model(self):
        from utils.file_export.export_registry import (
            EXPORT_REGISTRY,
            ExportSpec,
        )
        from utils.file_export.views import (
            GenericUserCreatedObjectExportView,
        )

        class _View(GenericUserCreatedObjectExportView):
            model_label = "waste_collection.collectionpropertyvalue"

        spec = ExportSpec(
            model=CollectionPropertyValue,
            filterset=None,
            serializer=None,
            renderers={},
        )
        request = RequestFactory().get("/export/", {"list_type": "published"})
        request.user = self.owner
        with patch.dict(
            EXPORT_REGISTRY,
            {"waste_collection.collectionpropertyvalue": spec},
        ):
            params = _View().get_filter_params(request, dict(request.GET))
        # The export task resolves lifecycle through the source-aware core
        # scope; a raw copied publication_status field filter is not seeded.
        self.assertNotIn("publication_status", params)

    def test_export_seed_params_keep_status_for_raw_model(self):
        from utils.file_export.views import (
            GenericUserCreatedObjectExportView,
        )

        class _View(GenericUserCreatedObjectExportView):
            model_label = "waste_collection.Collection"

        request = RequestFactory().get("/export/", {"list_type": "published"})
        request.user = self.owner
        params = _View().get_filter_params(request, dict(request.GET))
        self.assertEqual(params.get("publication_status"), ["published"])


class GeneratedProjectionRegistryProfileTests(
    GeneratedProjectionFixtureMixin, TestCase
):
    def test_marker_must_be_strict_boolean_true(self):
        loose = CollectionPropertyValue(is_derived="yes")
        self.assertEqual(record_policy(loose).kind, KIND_REVIEWABLE)
        real = CollectionPropertyValue(is_derived=True)
        self.assertEqual(record_policy(real).kind, KIND_GENERATED)

    def test_review_target_resolves_validated_source(self):
        source = self._source("private")
        projection = self._generated(source)
        self.assertEqual(review_target(projection), source)
        self.assertIs(review_target(source), source)
        inner = self._generated(self._source("private"))
        chained = self._generated(inner)
        self.assertIsNone(review_target(chained))

    def test_check_flags_missing_profile_model(self):
        with patch.dict(
            GENERATED_PROJECTIONS,
            {"waste_collection.missing_model": ("is_derived", "derived_from")},
            clear=True,
        ):
            errors = checks.registry_classification_check(None)
        self.assertTrue(
            any(e.id == "object_management.E011" for e in errors),
            msg=f"Expected E011, got {errors}",
        )

    def test_check_flags_non_boolean_marker(self):
        with patch.dict(
            GENERATED_PROJECTIONS,
            {
                "waste_collection.collectionpropertyvalue": (
                    "year",
                    "derived_from",
                )
            },
            clear=True,
        ):
            errors = checks.registry_classification_check(None)
        self.assertTrue(
            any(e.id == "object_management.E013" for e in errors),
            msg=f"Expected E013, got {errors}",
        )

    def test_check_flags_unresolvable_source_path(self):
        with patch.dict(
            GENERATED_PROJECTIONS,
            {
                "waste_collection.collectionpropertyvalue": (
                    "is_derived",
                    "no_such_field",
                )
            },
            clear=True,
        ):
            errors = checks.registry_classification_check(None)
        self.assertTrue(
            any(e.id == "object_management.E014" for e in errors),
            msg=f"Expected E014, got {errors}",
        )

    def test_check_flags_non_reviewable_source(self):
        with patch.dict(
            GENERATED_PROJECTIONS,
            {
                "waste_collection.collectionpropertyvalue": (
                    "is_derived",
                    "owner",
                )
            },
            clear=True,
        ):
            errors = checks.registry_classification_check(None)
        self.assertTrue(
            any(e.id == "object_management.E015" for e in errors),
            msg=f"Expected E015, got {errors}",
        )

    def test_invalid_source_parity_between_decide_and_querysets(self):
        source = self._source("published")
        inner = self._generated(source)
        chained = self._generated(inner)
        qs = CollectionPropertyValue.objects.all()
        for user in (
            self.owner,
            self.administrator,
            self.superuser,
            AnonymousUser(),
        ):
            self.assertEqual(decide(user, "read", chained).reason, "invalid_parent")
            self.assertNotIn(chained, visible_queryset(user, qs))
            self.assertNotIn(chained, scope_queryset(user, qs, "published"))
        self.assertIsNone(generated_source(chained))


class GeneratedProjectionInvalidProvenanceTests(
    GeneratedProjectionFixtureMixin, TestCase
):
    """Invalid provenance fails closed in review/policy surfaces."""

    def _invalid_projection(self, *, owner=None, publication_status="published"):
        """A generated row whose declared source is itself generated."""
        source = self._source("published")
        inner = self._generated(source)
        return self._generated(
            inner, owner=owner or self.owner, publication_status=publication_status
        )

    def test_build_review_context_denies_invalid_provenance(self):
        from utils.object_management.review_context import build_review_context

        projection = self._invalid_projection()
        with self.assertRaises(PermissionDenied):
            build_review_context(projection)

    def test_review_context_api_invalid_provenance_forbidden(self):
        projection = self._invalid_projection()
        ct = _cpv_ct()
        client = Client()
        client.force_login(self.owner)
        response = client.get(
            reverse(
                "object_management:api_review_context",
                kwargs={"content_type_id": ct.pk, "object_id": projection.pk},
            )
        )
        self.assertEqual(response.status_code, 403)

    def test_object_policy_invalid_generated_advertises_no_copied_state(self):
        # Copied owner/status are stale compatibility metadata; an invalid
        # provenance must not surface them as governance.
        projection = self._invalid_projection(
            owner=self.owner, publication_status="published"
        )
        policy = get_object_policy(self.owner, projection)
        self.assertFalse(policy["is_owner"])
        self.assertFalse(policy["is_published"])
        self.assertFalse(policy["is_private"])
        self.assertFalse(policy["is_in_review"])
        self.assertFalse(policy["can_view_review_activity"])
        self.assertIsNone(policy["export_list_type"])

    def test_access_routes_invalid_generated_make_no_copied_claims(self):
        projection = self._invalid_projection(
            owner=self.owner, publication_status="published"
        )
        routes = object_access_routes(self.owner, projection)
        self.assertNotIn("owner", routes)
        self.assertNotIn("published (public read)", routes)
        self.assertNotIn("archived (public historical read)", routes)


class _StaleStatusFilterSet:
    """Filterset stand-in applying the raw copied publication_status field.

    Reproduces the pre-fix failure mode: if the worker leaves the explicit
    state key in the query dict, this filterset compares the projection's
    stale copied status instead of the source lifecycle.
    """

    def __init__(self, data, queryset=None):
        qs = queryset
        states = data.getlist("publication_status")
        if states:
            qs = qs.filter(publication_status__in=states)
        self.qs = qs


class _PkExportSerializer:
    def __init__(self, instances, many=False, context=None):
        self.data = [{"pk": obj.pk} for obj in instances]


class GeneratedExplicitExportTests(GeneratedProjectionFixtureMixin, TestCase):
    """Worker-level exports honour explicit lifecycle-state filters."""

    def _export_spec(self):
        from unittest.mock import MagicMock

        from utils.file_export.export_registry import ExportSpec

        return ExportSpec(
            model=CollectionPropertyValue,
            filterset=_StaleStatusFilterSet,
            serializer=_PkExportSerializer,
            renderers={"csv": MagicMock()},
        )

    def _run_worker(self, query_params, *, list_type="private", user=None):
        from unittest.mock import MagicMock

        from utils.file_export import generic_tasks
        from utils.file_export.export_registry import EXPORT_REGISTRY

        user = user or self.owner
        run_fn = generic_tasks.export_user_created_object_to_file.run.__func__
        mock_self = MagicMock()
        mock_self.request.id = "req-1"
        mock_storage = MagicMock()
        mock_storage.size.return_value = 123
        with (
            patch.dict(
                EXPORT_REGISTRY,
                {"waste_collection.collectionpropertyvalue": self._export_spec()},
            ),
            patch(
                "utils.file_export.storages.write_file_for_download",
                return_value="https://example.com/export.csv",
            ) as mock_write,
            patch(
                "utils.file_export.storages.get_file_export_storage",
                return_value=mock_storage,
            ),
        ):
            run_fn(
                mock_self,
                "waste_collection.collectionpropertyvalue",
                "csv",
                query_params,
                {"user_id": user.pk, "list_type": list_type},
            )
        data = mock_write.call_args[0][1]
        return {row["pk"] for row in data}

    def test_view_preserves_explicit_status_for_profiled_model(self):
        from utils.file_export.export_registry import EXPORT_REGISTRY
        from utils.file_export.views import GenericUserCreatedObjectExportView

        class _View(GenericUserCreatedObjectExportView):
            model_label = "waste_collection.collectionpropertyvalue"

        request = RequestFactory().get(
            "/export/",
            {"list_type": "private", "publication_status": ["declined", "review"]},
        )
        request.user = self.owner
        with patch.dict(
            EXPORT_REGISTRY,
            {"waste_collection.collectionpropertyvalue": self._export_spec()},
        ):
            params = _View().get_filter_params(request, dict(request.GET))
        self.assertEqual(params.get("publication_status"), ["declined", "review"])

    def test_view_drops_seeded_status_for_profiled_model(self):
        from utils.file_export.export_registry import EXPORT_REGISTRY
        from utils.file_export.views import GenericUserCreatedObjectExportView

        class _View(GenericUserCreatedObjectExportView):
            model_label = "waste_collection.collectionpropertyvalue"

        request = RequestFactory().get("/export/", {"list_type": "published"})
        request.user = self.owner
        with patch.dict(
            EXPORT_REGISTRY,
            {"waste_collection.collectionpropertyvalue": self._export_spec()},
        ):
            params = _View().get_filter_params(request, dict(request.GET))
        self.assertNotIn("publication_status", params)

    def test_worker_explicit_declined_exports_only_declined_state(self):
        declined_source = self._source("declined")
        declined_projection = self._generated(
            declined_source, publication_status="published"
        )
        self._source("published")
        self._generated(self._source("review"))

        pks = self._run_worker({"publication_status": ["declined"]})
        self.assertEqual(pks, {declined_source.pk, declined_projection.pk})

    def test_worker_explicit_published_uses_source_lifecycle(self):
        published_source = self._source("published")
        projection_private_copy = self._generated(
            published_source, publication_status="private"
        )
        private_source = self._source("private")
        self._generated(
            private_source,
            publication_status="published",
            owner=self.stranger,
        )

        pks = self._run_worker({"publication_status": ["published"]})
        self.assertEqual(pks, {published_source.pk, projection_private_copy.pk})

    def test_worker_invalid_state_exports_nothing(self):
        self._source("published")
        self._generated(self._source("private"))
        pks = self._run_worker({"publication_status": ["bogus"]})
        self.assertEqual(pks, set())

    def test_worker_without_explicit_state_uses_scope_only(self):
        published_source = self._source("published")
        projection = self._generated(published_source, publication_status="private")
        private_source = self._source("private")
        pks = self._run_worker({}, list_type="published")
        self.assertEqual(pks, {published_source.pk, projection.pk})
        self.assertNotIn(private_source.pk, pks)

    def test_row_count_estimate_matches_worker_for_profiled_model(self):
        from utils.file_export.export_registry import EXPORT_REGISTRY
        from utils.file_export.views import GenericUserCreatedObjectExportView

        class _View(GenericUserCreatedObjectExportView):
            model_label = "waste_collection.collectionpropertyvalue"

        self._generated(self._source("published"), publication_status="private")
        self._generated(
            self._source("private"),
            publication_status="published",
            owner=self.stranger,
        )
        view = _View()
        request = RequestFactory().get("/export/")
        request.user = self.owner
        view.request = request
        with patch.dict(
            EXPORT_REGISTRY,
            {"waste_collection.collectionpropertyvalue": self._export_spec()},
        ):
            estimate = view.get_export_row_count_estimate(
                {"publication_status": ["published"]},
                {"list_type": "private"},
            )
            worker_pks = self._run_worker({"publication_status": ["published"]})
        self.assertEqual(estimate, len(worker_pks))


class GeneratedPreferredMeasurementTests(GeneratedProjectionFixtureMixin, TestCase):
    """Purpose-scoped read preference: visible manual beats generated."""

    def test_visible_manual_suppresses_generated_in_preferred_queryset(self):
        from sources.waste_collection.derived_values import (
            preferred_measurement_queryset,
        )

        source = self._source("published")
        projection = self._generated(
            source, property=self.projection_property, unit=self.unit
        )
        manual = CollectionPropertyValue.objects.create(
            name="manual counterpart",
            collection=self.collection,
            property=self.projection_property,
            unit=self.unit,
            year=source.year,
            average=25,
            owner=self.owner,
            publication_status="published",
            is_derived=False,
        )
        preferred = preferred_measurement_queryset(
            CollectionPropertyValue.objects.filter(collection=self.collection)
        )
        self.assertIn(manual, preferred)
        self.assertIn(source, preferred)
        self.assertNotIn(projection, preferred)

    def test_inaccessible_manual_does_not_suppress_public_generated(self):
        from sources.waste_collection.derived_values import (
            preferred_measurement_queryset,
        )

        source = self._source("published")
        projection = self._generated(
            source, property=self.projection_property, unit=self.unit
        )
        # Private manual evidence owned by someone else at the same key.
        hidden_manual = CollectionPropertyValue.objects.create(
            name="hidden manual",
            collection=self.collection,
            property=self.projection_property,
            unit=self.unit,
            year=source.year,
            average=999,
            owner=self.stranger,
            publication_status="private",
            is_derived=False,
        )

        public_visible = visible_queryset(
            AnonymousUser(), CollectionPropertyValue.objects.all()
        )
        preferred_public = preferred_measurement_queryset(public_visible)
        self.assertIn(projection, preferred_public)
        self.assertNotIn(hidden_manual, preferred_public)

        # The manual's owner may select it in their workspace; the generated
        # alternative is suppressed within that purpose-scoped queryset.
        stranger_visible = visible_queryset(
            self.stranger, CollectionPropertyValue.objects.all()
        )
        preferred_stranger = preferred_measurement_queryset(stranger_visible)
        self.assertIn(hidden_manual, preferred_stranger)
        self.assertNotIn(projection, preferred_stranger)
