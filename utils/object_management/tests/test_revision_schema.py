"""Extraction-only regression tests for the additive revision/audit schema.

These tests pin the Part 2 schema slice of the unified authorization stack:
``UserCreatedObject.content_revision``, non-editable lifecycle metadata, and the
extended ``ReviewAction`` audit fields/actions. They assert ORM schema shape
only — no authorization or audit *behavior* is claimed here.
"""

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.migrations.loader import MigrationLoader
from django.test import SimpleTestCase, TestCase

from utils.properties.models import Property

from ..models import ReviewAction, UserCreatedObject


class RevisionFieldSchemaTests(TestCase):
    """Field-shape checks; no database writes required."""

    def _assert_content_revision_field(self, model):
        field = model._meta.get_field("content_revision")
        self.assertIsInstance(field, models.PositiveBigIntegerField)
        self.assertEqual(field.default, 1)
        self.assertFalse(field.editable)

    def test_base_uco_content_revision_field(self):
        self._assert_content_revision_field(UserCreatedObject)

    def test_concrete_uco_content_revision_field(self):
        self._assert_content_revision_field(Property)

    def test_lifecycle_fields_not_editable(self):
        for model in (UserCreatedObject, Property):
            for field_name in (
                "publication_status",
                "submitted_at",
                "approved_at",
                "approved_by",
            ):
                with self.subTest(model=model.__name__, field=field_name):
                    self.assertFalse(model._meta.get_field(field_name).editable)

    def test_review_action_revision_fields(self):
        revision = ReviewAction._meta.get_field("content_revision")
        self.assertIsInstance(revision, models.PositiveBigIntegerField)
        self.assertTrue(revision.null)
        self.assertTrue(revision.blank)
        self.assertFalse(revision.editable)

        changed = ReviewAction._meta.get_field("changed_fields")
        self.assertIsInstance(changed, models.JSONField)
        self.assertFalse(changed.editable)
        # default=list must yield independent empty lists per instance
        first, second = changed.default(), changed.default()
        self.assertEqual(first, [])
        first.append("x")
        self.assertEqual(second, [])

    def test_review_action_covers_all_nine_actions(self):
        expected = {
            "submitted",
            "approved",
            "rejected",
            "withdrawn",
            "archived",
            "comment",
            "created",
            "edited",
            "deleted",
        }
        choice_values = {value for value, _label in ReviewAction.ACTION_CHOICES}
        self.assertEqual(choice_values, expected)
        for name in expected:
            with self.subTest(action=name):
                self.assertEqual(getattr(ReviewAction, f"ACTION_{name.upper()}"), name)

    def test_review_action_administer_objects_permission(self):
        permissions = {codename for codename, _ in ReviewAction._meta.permissions}
        self.assertIn("administer_objects", permissions)


class RevisionFieldPersistenceTests(TestCase):
    """ORM-level persistence checks for the new schema columns."""

    def setUp(self):
        self.owner = User.objects.create_user(username="revision-owner")
        self.property = Property.objects.create(
            name="Revision Test Property",
            owner=self.owner,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )

    def test_content_revision_defaults_to_one_and_persists(self):
        self.property.refresh_from_db()
        self.assertEqual(self.property.content_revision, 1)
        self.property.content_revision = 3
        self.property.save()
        self.property.refresh_from_db()
        self.assertEqual(self.property.content_revision, 3)

    def test_review_action_revision_fields_persist(self):
        action = ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(self.property),
            object_id=self.property.pk,
            user=self.owner,
            action=ReviewAction.ACTION_COMMENT,
        )
        action.refresh_from_db()
        self.assertIsNone(action.content_revision)
        self.assertEqual(action.changed_fields, [])

        action.content_revision = 3
        action.changed_fields = ["name"]
        action.save()
        action.refresh_from_db()
        self.assertEqual(action.content_revision, 3)
        self.assertEqual(action.changed_fields, ["name"])


class RevisionMigrationGraphTests(SimpleTestCase):
    """Migration-graph shape for the schema slice on the finalized baseline.

    Each touched app must expose exactly one leaf — the additive revision
    migration re-anchored on that app's finalized squash migration — and no
    operation may target models that no longer exist on main (``maps.Attribute``
    was superseded by the Region/Categorical attribute models).
    """

    EXPECTED_LEAVES = {
        "maps": ("maps", "0023_catchment_content_revision_and_more"),
        "materials": (
            "materials",
            "0036_analyticalmethod_content_revision_and_more",
        ),
        "waste_collection": (
            "waste_collection",
            "0012_alter_collection_options",
        ),
        "object_management": ("object_management", "0009_alter_reviewaction_action"),
    }

    def test_schema_slice_apps_have_single_expected_leaf(self):
        loader = MigrationLoader(None)
        for app_label, expected_leaf in self.EXPECTED_LEAVES.items():
            with self.subTest(app=app_label):
                self.assertEqual(loader.graph.leaf_nodes(app_label), [expected_leaf])

    def test_maps_revision_migration_drops_no_removed_attribute_ops(self):
        loader = MigrationLoader(None)
        migration = loader.disk_migrations[
            ("maps", "0023_catchment_content_revision_and_more")
        ]
        touched_models = {operation.model_name for operation in migration.operations}
        self.assertNotIn("attribute", touched_models)
        self.assertNotIn(("maps", "attribute"), loader.project_state().models)
