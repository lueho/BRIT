from decimal import Decimal

from django.contrib.auth.models import AnonymousUser, Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from utils.properties.models import Property

from ..models import ReviewAction
from ..policy import (
    PUBLIC_READ_STATES,
    decide,
    object_access_routes,
    scope_queryset,
    visible_queryset,
)


class ArchivedPublicReadTests(TestCase):
    """Archived means retained, previously published, public and frozen."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="arch-owner")
        cls.regular = User.objects.create_user(username="arch-regular")
        cls.staff = User.objects.create_user(username="arch-staff", is_staff=True)
        cls.inactive = User.objects.create_user(
            username="arch-inactive", is_active=False
        )
        cls.moderator = User.objects.create_user(username="arch-moderator")
        cls.administrator = User.objects.create_user(username="arch-admin")
        cls.anonymous = AnonymousUser()

        property_ct = ContentType.objects.get_for_model(Property)
        cls.moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_property", content_type=property_ct
            )
        )
        administer_permission, _ = Permission.objects.get_or_create(
            codename="administer_objects",
            content_type=ContentType.objects.get_for_model(ReviewAction),
            defaults={"name": "Can administer objects"},
        )
        cls.administrator.user_permissions.add(administer_permission)

        cls.objects = {}
        for status in (
            "private",
            "review",
            "published",
            "declined",
            "archived",
        ):
            cls.objects[status] = Property.objects.create(
                name=f"Archived-read {status}",
                owner=cls.owner,
                publication_status=status,
            )
        cls.bogus = Property.objects.create(
            name="Archived-read bogus",
            owner=cls.owner,
            publication_status="unknown",
        )

    def _personas(self):
        return {
            "anonymous": self.anonymous,
            "inactive": self.inactive,
            "regular": self.regular,
            "staff": self.staff,
            "moderator": self.moderator,
            "administrator": self.administrator,
        }

    def test_public_read_states_is_an_immutable_tuple(self):
        self.assertIsInstance(PUBLIC_READ_STATES, tuple)
        self.assertEqual(PUBLIC_READ_STATES, ("published", "archived"))

    def test_every_persona_reads_and_exports_archives(self):
        for persona, user in self._personas().items():
            for action in ("read", "export"):
                with self.subTest(persona=persona, action=action):
                    self.assertTrue(
                        decide(user, action, self.objects["archived"]).allowed
                    )
                    self.assertTrue(
                        decide(user, action, self.objects["published"]).allowed
                    )

    def test_visible_queryset_includes_archived_for_public_personas(self):
        archived_pk = self.objects["archived"].pk
        published_pk = self.objects["published"].pk
        for persona, user in self._personas().items():
            with self.subTest(persona=persona):
                visible = set(
                    visible_queryset(user, Property.objects.all()).values_list(
                        "pk", flat=True
                    )
                )
                self.assertIn(archived_pk, visible)
                self.assertIn(published_pk, visible)
                self.assertNotIn(self.bogus.pk, visible)

    def test_published_scope_excludes_archived_but_archived_scope_includes_it(self):
        archived_pk = self.objects["archived"].pk
        published_pk = self.objects["published"].pk
        for persona, user in self._personas().items():
            with self.subTest(persona=persona):
                published_scope = set(
                    scope_queryset(
                        user, Property.objects.all(), "published"
                    ).values_list("pk", flat=True)
                )
                self.assertIn(published_pk, published_scope)
                self.assertNotIn(archived_pk, published_scope)
                archived_scope = set(
                    scope_queryset(
                        user, Property.objects.all(), "archived"
                    ).values_list("pk", flat=True)
                )
                self.assertIn(archived_pk, archived_scope)
                self.assertNotIn(published_pk, archived_scope)

    def test_archived_records_are_frozen_for_all_actors(self):
        property_ct = ContentType.objects.get_for_model(Property)
        crud = [
            Permission.objects.get(codename=codename, content_type=property_ct)
            for codename in (
                "change_property",
                "delete_property",
                "add_property",
            )
        ]
        self.owner.user_permissions.add(*crud)
        # The administrator must hold the same CRUD capabilities so denial
        # comes from the frozen state, not a missing-permission shortcut.
        self.administrator.user_permissions.add(*crud)
        owner = User.objects.get(pk=self.owner.pk)
        administrator = User.objects.get(pk=self.administrator.pk)
        for actor in (owner, administrator):
            with self.subTest(actor=actor.username):
                for action in ("edit", "delete", "new_version"):
                    with self.subTest(action=action):
                        decision = decide(actor, action, self.objects["archived"])
                        self.assertFalse(decision.allowed)
                        self.assertEqual(decision.reason, "immutable_state")
                self.assertFalse(
                    decide(actor, "submit", self.objects["archived"]).allowed
                )

    def test_archive_action_only_allows_published(self):
        for status in ("private", "review", "declined"):
            for actor in (self.owner, self.administrator):
                with self.subTest(status=status, actor=actor.username):
                    decision = decide(actor, "archive", self.objects[status])
                    self.assertFalse(decision.allowed)
                    self.assertEqual(decision.reason, "invalid_state")

    def test_duplicate_remains_authorized_on_archives(self):
        self.regular.user_permissions.add(
            Permission.objects.get(
                codename="add_property",
                content_type=ContentType.objects.get_for_model(Property),
            )
        )
        regular = User.objects.get(pk=self.regular.pk)
        self.assertTrue(decide(regular, "duplicate", self.objects["archived"]).allowed)
        self.assertFalse(
            decide(regular, "new_version", self.objects["archived"]).allowed
        )

    def test_review_history_stays_restricted_on_archives(self):
        self.assertFalse(
            decide(
                self.anonymous, "view_review_activity", self.objects["archived"]
            ).allowed
        )
        self.assertFalse(
            decide(
                self.inactive, "view_review_activity", self.objects["archived"]
            ).allowed
        )
        self.assertFalse(
            decide(
                self.regular, "view_review_activity", self.objects["archived"]
            ).allowed
        )
        self.assertTrue(
            decide(
                self.moderator, "view_review_activity", self.objects["archived"]
            ).allowed
        )
        self.assertFalse(
            decide(self.regular, "comment_on_review", self.objects["archived"]).allowed
        )

    def test_access_routes_label_archived_public_historical_read(self):
        routes = object_access_routes(self.regular, self.objects["archived"])
        self.assertIn("archived (public historical read)", routes)
        self.assertNotIn("published (public read)", routes)
        routes = object_access_routes(self.regular, self.objects["published"])
        self.assertIn("published (public read)", routes)


class ArchivedAttachmentTests(TestCase):
    """Typed independent evidence attaches to public-archived roots under the
    declared ``published_attachment`` rule.

    MaterialPropertyValue declares ``collaborator``: owner/editor/admin of the
    parent plus the model's own add capability. ComponentMeasurement declares
    no published attachment and stays denied on public roots.
    """

    @classmethod
    def setUpTestData(cls):
        from materials.models import (
            ComponentMeasurement,
            Material,
            MaterialProperty,
            MaterialPropertyValue,
            Sample,
        )
        from utils.properties.models import Unit

        cls.MaterialPropertyValue = MaterialPropertyValue
        cls.ComponentMeasurement = ComponentMeasurement
        cls.owner = User.objects.create_user(username="arch-attach-owner")
        cls.stranger = User.objects.create_user(username="arch-attach-stranger")
        cls.editor = User.objects.create_user(username="arch-attach-editor")
        cls.group_editor = User.objects.create_user(username="arch-attach-group-editor")

        sample_ct = ContentType.objects.get_for_model(Sample)
        mpv_ct = ContentType.objects.get_for_model(MaterialPropertyValue)
        cm_ct = ContentType.objects.get_for_model(ComponentMeasurement)
        change_sample = Permission.objects.get(
            codename="change_sample", content_type=sample_ct
        )
        add_mpv = Permission.objects.get(
            codename="add_materialpropertyvalue", content_type=mpv_ct
        )
        change_mpv = Permission.objects.get(
            codename="change_materialpropertyvalue", content_type=mpv_ct
        )
        add_cm = Permission.objects.get(
            codename="add_componentmeasurement", content_type=cm_ct
        )
        cls.add_mpv = add_mpv
        cls.owner.user_permissions.add(change_sample, add_mpv, change_mpv, add_cm)
        cls.stranger.user_permissions.add(add_mpv, change_mpv, add_cm)

        material = Material.objects.create(
            name="Archived attach material", owner=cls.owner
        )
        cls.sample = Sample.objects.create(
            name="Archived attach sample",
            owner=cls.owner,
            material=material,
            publication_status="archived",
        )
        cls.published_sample = Sample.objects.create(
            name="Published attach sample",
            owner=cls.owner,
            material=material,
            publication_status="published",
        )
        cls.private_sample = Sample.objects.create(
            name="Private attach sample",
            owner=cls.owner,
            material=material,
            publication_status="private",
        )
        cls.sample.add_editor(cls.editor)
        cls.editor_group = Group.objects.create(name="arch-attach-editors")
        cls.editor_group.user_set.add(cls.group_editor)
        cls.sample.add_editor_group(cls.editor_group)

        cls.property = MaterialProperty.objects.create(name="Attach property")
        cls.unit = Unit.objects.create(name="Attach unit")
        cls.private_mpv = MaterialPropertyValue.objects.create(
            sample=cls.private_sample,
            property=cls.property,
            unit=cls.unit,
            average=Decimal("10"),
            owner=cls.owner,
            publication_status="private",
        )
        cls.published_mpv = MaterialPropertyValue.objects.create(
            sample=cls.private_sample,
            property=cls.property,
            unit=cls.unit,
            average=Decimal("20"),
            owner=cls.owner,
            publication_status="published",
        )

    def test_owner_with_add_attaches_to_public_roots(self):
        owner = User.objects.get(pk=self.owner.pk)
        for sample in (self.sample, self.published_sample):
            with self.subTest(status=sample.publication_status):
                self.assertTrue(
                    decide(
                        owner,
                        "create",
                        self.MaterialPropertyValue,
                        parent=sample,
                    ).allowed
                )

    def test_stranger_with_add_denied_without_parent_collaboration(self):
        stranger = User.objects.get(pk=self.stranger.pk)
        for sample in (self.sample, self.published_sample):
            with self.subTest(status=sample.publication_status):
                decision = decide(
                    stranger,
                    "create",
                    self.MaterialPropertyValue,
                    parent=sample,
                )
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.reason, "insufficient_parent_access")

    def test_collaborators_require_own_add_capability(self):
        for username in ("arch-attach-editor", "arch-attach-group-editor"):
            with self.subTest(username=username):
                user = User.objects.get(username=username)
                decision = decide(
                    user,
                    "create",
                    self.MaterialPropertyValue,
                    parent=self.sample,
                )
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.reason, "missing_model_permission")
                user.user_permissions.add(self.add_mpv)
                user = User.objects.get(username=username)
                self.assertTrue(
                    decide(
                        user,
                        "create",
                        self.MaterialPropertyValue,
                        parent=self.sample,
                    ).allowed
                )

    def test_undeclared_evidence_denied_on_public_roots(self):
        owner = User.objects.get(pk=self.owner.pk)
        for sample in (self.sample, self.published_sample):
            with self.subTest(status=sample.publication_status):
                decision = decide(
                    owner,
                    "create",
                    self.ComponentMeasurement,
                    parent=sample,
                )
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.reason, "insufficient_parent_access")
        # Unpublished parents still follow the parent-edit rule.
        self.assertTrue(
            decide(
                owner,
                "create",
                self.ComponentMeasurement,
                parent=self.private_sample,
            ).allowed
        )

    def test_private_parent_requires_edit_access(self):
        owner = User.objects.get(pk=self.owner.pk)
        stranger = User.objects.get(pk=self.stranger.pk)
        self.assertTrue(
            decide(
                owner,
                "create",
                self.MaterialPropertyValue,
                parent=self.private_sample,
            ).allowed
        )
        self.assertFalse(
            decide(
                stranger,
                "create",
                self.MaterialPropertyValue,
                parent=self.private_sample,
            ).allowed
        )

    def test_reassignment_to_archived_parent_follows_declared_rule(self):
        from ..policy import decide_reassign

        owner = User.objects.get(pk=self.owner.pk)
        stranger = User.objects.get(pk=self.stranger.pk)
        # Owner is a parent collaborator and holds edit capability on the row.
        self.assertTrue(decide_reassign(owner, self.private_mpv, self.sample).allowed)
        # A stranger's own private row cannot move onto a foreign archived
        # parent without collaboration on that parent.
        foreign_sample = self._foreign_private_sample(stranger)
        foreign_mpv = self.MaterialPropertyValue.objects.create(
            sample=foreign_sample,
            property=self.property,
            unit=self.unit,
            average=Decimal("30"),
            owner=stranger,
            publication_status="private",
        )
        decision = decide_reassign(stranger, foreign_mpv, self.sample)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "insufficient_parent_access")

    def test_reassignment_requires_edit_capability_and_editable_state(self):
        from ..policy import decide_reassign

        owner = User.objects.get(pk=self.owner.pk)
        owner.user_permissions.remove(
            Permission.objects.get(
                codename="change_materialpropertyvalue",
                content_type=ContentType.objects.get_for_model(
                    self.MaterialPropertyValue
                ),
            )
        )
        owner = User.objects.get(pk=self.owner.pk)
        decision = decide_reassign(owner, self.private_mpv, self.sample)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "missing_model_permission")

        owner = User.objects.get(pk=self.owner.pk)
        owner.user_permissions.add(
            Permission.objects.get(
                codename="change_materialpropertyvalue",
                content_type=ContentType.objects.get_for_model(
                    self.MaterialPropertyValue
                ),
            )
        )
        owner = User.objects.get(pk=self.owner.pk)
        decision = decide_reassign(owner, self.published_mpv, self.sample)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "immutable_state")

    def _foreign_private_sample(self, stranger):
        from materials.models import Material, Sample

        material = Material.objects.create(
            name="Foreign attach material", owner=stranger
        )
        return Sample.objects.create(
            name="Foreign attach sample",
            owner=stranger,
            material=material,
            publication_status="private",
        )


class ArchivedOwnedChildTests(TestCase):
    """Owned children (SourceAuthor on Source) inherit the archived root:
    public read through the frozen root, create/edit/delete denied by it."""

    @classmethod
    def setUpTestData(cls):
        from bibliography.models import Author, Source, SourceAuthor

        cls.SourceAuthor = SourceAuthor
        cls.owner = User.objects.create_user(username="arch-source-owner")
        cls.administrator = User.objects.create_user(username="arch-source-admin")
        cls.regular = User.objects.create_user(username="arch-source-regular")
        cls.anonymous = AnonymousUser()

        source_ct = ContentType.objects.get_for_model(Source)
        crud = [
            Permission.objects.get(codename=codename, content_type=source_ct)
            for codename in ("change_source", "delete_source", "add_source")
        ]
        cls.owner.user_permissions.add(*crud)
        cls.administrator.user_permissions.add(
            Permission.objects.get_or_create(
                codename="administer_objects",
                content_type=ContentType.objects.get_for_model(ReviewAction),
                defaults={"name": "Can administer objects"},
            )[0],
            *crud,
        )

        cls.author = Author.objects.create(
            owner=cls.owner,
            first_names="Ada",
            last_names="Lovelace",
            publication_status="published",
        )
        cls.archived_source = Source.objects.create(
            owner=cls.owner,
            title="Archived source",
            publication_status="archived",
        )
        cls.private_source = Source.objects.create(
            owner=cls.owner,
            title="Private source",
            publication_status="private",
        )
        cls.archived_row = SourceAuthor.objects.create(
            source=cls.archived_source, author=cls.author, position=1
        )
        cls.private_row = SourceAuthor.objects.create(
            source=cls.private_source, author=cls.author, position=1
        )

    def test_anonymous_reads_owned_child_of_public_archived_root(self):
        self.assertTrue(decide(self.anonymous, "read", self.archived_row).allowed)
        self.assertTrue(decide(self.anonymous, "export", self.archived_row).allowed)
        self.assertFalse(decide(self.anonymous, "read", self.private_row).allowed)

    def test_archived_root_denies_owned_child_create(self):
        owner = User.objects.get(pk=self.owner.pk)
        decision = decide(
            owner, "create", self.SourceAuthor, parent=self.archived_source
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "immutable_state")

    def test_archived_root_denies_owned_child_edit_and_delete(self):
        owner = User.objects.get(pk=self.owner.pk)
        for action in ("edit", "delete"):
            with self.subTest(action=action):
                decision = decide(owner, action, self.archived_row)
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.reason, "immutable_state")

    def test_administrator_cannot_thaw_owned_child(self):
        administrator = User.objects.get(pk=self.administrator.pk)
        decision = decide(
            administrator, "create", self.SourceAuthor, parent=self.archived_source
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "immutable_state")
        decision = decide(administrator, "edit", self.archived_row)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "immutable_state")

    def test_private_root_allows_owned_child_lifecycle(self):
        owner = User.objects.get(pk=self.owner.pk)
        self.assertTrue(
            decide(
                owner, "create", self.SourceAuthor, parent=self.private_source
            ).allowed
        )
        self.assertTrue(decide(owner, "edit", self.private_row).allowed)
        self.assertTrue(decide(owner, "delete", self.private_row).allowed)
