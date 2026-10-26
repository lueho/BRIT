"""Dataset-version fingerprints follow core collection scopes."""

from datetime import date

from django.contrib.auth.models import AnonymousUser, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from maps.utils import compute_collection_dataset_version
from sources.waste_collection.models import (
    Collection,
    CollectionCatchment,
    CollectionSystem,
    WasteCategory,
)
from utils.object_management.models import ReviewAction


class CollectionDatasetVersionAuthorizationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("dv-owner")
        cls.other = User.objects.create_user("dv-other")
        cls.grantee = User.objects.create_user("dv-grantee")
        cls.regular = User.objects.create_user("dv-regular")
        cls.administrator = User.objects.create_user("dv-admin")
        cls.anonymous = AnonymousUser()

        administer_permission, _ = Permission.objects.get_or_create(
            codename="administer_objects",
            content_type=ContentType.objects.get_for_model(ReviewAction),
            defaults={"name": "Can administer objects"},
        )
        cls.administrator.user_permissions.add(administer_permission)

        cls.catchment = CollectionCatchment.objects.create(
            name="DV catchment", publication_status="published"
        )
        cls.system = CollectionSystem.objects.create(
            name="DV system", publication_status="published"
        )
        cls.category = WasteCategory.objects.create(
            name="DV category", publication_status="published"
        )

        cls.published = cls._collection("DV published", cls.owner, "published")
        cls.archived = cls._collection("DV archived", cls.owner, "archived")
        cls.private = cls._collection("DV private", cls.owner, "private")
        cls.foreign_private = cls._collection(
            "DV foreign private", cls.other, "private"
        )

    @classmethod
    def _collection(cls, name, owner, status):
        return Collection.objects.create(
            name=name,
            owner=owner,
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_category=cls.category,
            valid_from=date(2024, 1, 1),
            publication_status=status,
        )

    def test_published_scope_counts_only_active_published(self):
        before = compute_collection_dataset_version("published", self.anonymous)
        self.archived.publication_status = "published"
        self.archived.save(update_fields=["publication_status"])
        after = compute_collection_dataset_version("published", self.anonymous)
        self.assertNotEqual(before, after)

    def test_archived_changes_do_not_affect_published_fingerprint(self):
        before = compute_collection_dataset_version("published", self.anonymous)
        self.archived.description = "touched archived row"
        self.archived.save()
        after = compute_collection_dataset_version("published", self.anonymous)
        self.assertEqual(before, after)

    def test_unrelated_private_row_does_not_change_public_fingerprint(self):
        public_before = compute_collection_dataset_version("published", self.regular)
        workspace_before = compute_collection_dataset_version("private", self.regular)
        self.foreign_private.description = "changed by other user"
        self.foreign_private.save()

        self.assertEqual(
            public_before,
            compute_collection_dataset_version("published", self.regular),
        )
        self.assertEqual(
            workspace_before,
            compute_collection_dataset_version("private", self.regular),
        )

    def test_granted_private_row_changes_workspace_fingerprint(self):
        self.foreign_private.add_editor(self.grantee)
        before = compute_collection_dataset_version("private", self.grantee)
        granted_row = self._collection("DV granted row", self.other, "private")
        granted_row.add_editor(self.grantee)
        grantee = User.objects.get(pk=self.grantee.pk)
        self.assertNotEqual(
            before, compute_collection_dataset_version("private", grantee)
        )

    def test_owner_private_scope_tracks_own_rows(self):
        before = compute_collection_dataset_version("private", self.owner)
        self._collection("DV second own row", self.owner, "private")
        self.assertNotEqual(
            before, compute_collection_dataset_version("private", self.owner)
        )

    def test_unknown_scope_sees_no_rows(self):
        fingerprint = compute_collection_dataset_version("bogus", self.owner)
        empty_fingerprint = compute_collection_dataset_version("bogus", self.anonymous)
        self.assertEqual(fingerprint, empty_fingerprint)

    def test_anonymous_workspace_scope_is_empty(self):
        before = compute_collection_dataset_version("private", self.anonymous)
        self._collection("DV anon-untouched", self.other, "private")
        self.assertEqual(
            before, compute_collection_dataset_version("private", self.anonymous)
        )
