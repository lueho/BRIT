from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import AnonymousUser, Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from bibliography.models import Author, Source, SourceAuthor
from distributions.models import TemporalDistribution, Timestep
from maps.models import (
    Catchment,
    GeoreferencedCatchment,
    GeoreferencedNutsRegion,
    GeoreferencedRegion,
    NutsVintage,
)
from materials.models import MaterialComponent
from sources.greenhouses.models import (
    Greenhouse,
    GreenhouseGrowthCycle,
    GrowthShare,
    GrowthTimeStepSet,
    NantesGreenhouses,
)
from sources.waste_collection.models import CollectionCatchment

from .. import checks
from ..models import ObjectEditorGrant, UserCreatedObject
from ..policy import (
    decide,
    decide_reassign,
    object_access_routes,
    scope_queryset,
    visible_queryset,
)
from ..registry import (
    KIND_OWNED,
    KIND_REVIEWABLE,
    MODEL_POLICIES,
    model_policy,
    root_model,
)
from ..signals import ensure_moderation_permissions


def model_permission(model, codename):
    return Permission.objects.get(
        content_type=ContentType.objects.get_for_model(model, for_concrete_model=False),
        codename=codename,
    )


class RegistryClassificationTests(TestCase):
    def test_every_installed_user_created_model_is_classified(self):
        registry_labels = set(MODEL_POLICIES)
        installed = {
            m._meta.label_lower
            for m in apps.get_models()
            if issubclass(m, UserCreatedObject) and not m._meta.abstract
        }
        self.assertEqual(
            installed - registry_labels,
            set(),
            msg="Installed UCO models missing from the registry",
        )
        for label in installed:
            policy = model_policy(apps.get_model(label))
            self.assertIsNotNone(policy, msg=label)
            self.assertIn(policy.kind, {"reviewable", "owned"})

    def test_registry_check_passes_unmodified(self):
        self.assertEqual(list(checks.registry_classification_check(None)), [])

    def test_non_uco_owned_children_are_accepted(self):
        """Plain ``models.Model`` owned children (no UserCreatedObject base)
        are valid registry entries whose roots stay governed."""
        from inventories.models import ScenarioInventoryConfiguration
        from maps.models import (
            GeoDatasetColumnPolicy,
            GeoDatasetRuntimeConfiguration,
        )

        for model, path in (
            (GeoDatasetRuntimeConfiguration, "dataset"),
            (GeoDatasetColumnPolicy, "dataset"),
            (ScenarioInventoryConfiguration, "scenario"),
        ):
            policy = model_policy(model)
            with self.subTest(model=model._meta.label_lower):
                self.assertFalse(issubclass(model, UserCreatedObject))
                self.assertIsNotNone(policy)
                self.assertEqual(policy.kind, KIND_OWNED)
                self.assertEqual(policy.parent_path, path)
                root = root_model(model, path)
                self.assertEqual(model_policy(root).kind, KIND_REVIEWABLE)

    def test_removing_a_model_from_registry_fails_check(self):
        patched = dict(MODEL_POLICIES)
        patched.pop("bibliography.source")
        with patch.dict(
            "utils.object_management.registry.MODEL_POLICIES", patched, clear=True
        ):
            errors = checks.registry_classification_check(None)
        self.assertTrue(
            any("bibliography.source" in e.msg for e in errors),
            msg=f"Expected registry check error for removed model, got {errors}",
        )

    def test_unregistered_user_created_subclass_is_denied(self):
        class UnregisteredObject(UserCreatedObject):
            class Meta:
                app_label = "object_management"
                managed = False

        try:
            user = User.objects.create_user(username="unregistered-actor")
            decision = decide(user, "create", UnregisteredObject)
            self.assertFalse(decision.allowed)
            self.assertEqual(decision.reason, "unsupported_model")
            self.assertEqual(
                list(
                    visible_queryset(AnonymousUser(), UnregisteredObject.objects.all())
                ),
                [],
            )
        finally:
            # Remove the ad-hoc model and expire cached reverse relations so
            # its inherited owner field cannot leak into delete collectors
            # of later tests.
            apps.all_models["object_management"].pop("unregisteredobject", None)
            apps.clear_cache()


class OwnedChildPolicyTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owned-owner")
        self.editor = User.objects.create_user(username="owned-editor")
        self.group_editor = User.objects.create_user(username="owned-group-editor")
        self.stranger = User.objects.create_user(username="owned-stranger")
        self.anonymous = AnonymousUser()
        self.source = Source.objects.create(title="Root source", owner=self.owner)
        self.author = Author.objects.create(owner=self.owner, last_names="Doe")
        self.child = SourceAuthor.objects.create(
            source=self.source, author=self.author, position=1
        )
        self.editor_group = Group.objects.create(name="owned-child-editors")
        self.group_editor.groups.add(self.editor_group)

    def test_class_create_requires_parent(self):
        decision = decide(self.owner, "create", SourceAuthor)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "parent_required")

    def test_class_create_delegates_to_parent_edit(self):
        decision = decide(self.stranger, "create", SourceAuthor, parent=self.source)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "missing_model_permission")
        self.stranger.user_permissions.add(model_permission(Source, "change_source"))
        stranger = User.objects.get(pk=self.stranger.pk)
        decision = decide(stranger, "create", SourceAuthor, parent=self.source)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "no_object_access")
        self.owner.user_permissions.add(model_permission(Source, "change_source"))
        owner = User.objects.get(pk=self.owner.pk)
        self.assertAllowed(decide(owner, "create", SourceAuthor, parent=self.source))

    def assertAllowed(self, decision):
        self.assertTrue(decision.allowed, msg=decision.reason)
        self.assertEqual(decision.reason, "allowed")

    def test_unsaved_parent_is_denied(self):
        unsaved = Source(title="Unsaved", owner=self.owner)
        self.owner.user_permissions.add(model_permission(Source, "change_source"))
        owner = User.objects.get(pk=self.owner.pk)
        decision = decide(owner, "create", SourceAuthor, parent=unsaved)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "invalid_parent")

    def test_forged_parent_is_denied(self):
        other = Source.objects.create(title="Other", owner=self.owner)
        self.owner.user_permissions.add(model_permission(Source, "change_source"))
        owner = User.objects.get(pk=self.owner.pk)
        self.assertEqual(
            decide(owner, "create", SourceAuthor, parent=other).reason,
            "allowed",
        )
        self.assertEqual(
            decide(owner, "edit", self.child, parent=other).reason,
            "invalid_parent",
        )
        self.assertEqual(
            decide(owner, "edit", self.child, parent=self.source).reason,
            "allowed",
        )

    def test_editor_crud_inherits_parent_change_permission(self):
        self.source.add_editor(self.editor)
        decision = decide(self.editor, "edit", self.child)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "missing_model_permission")
        self.editor.user_permissions.add(model_permission(Source, "change_source"))
        editor = User.objects.get(pk=self.editor.pk)
        self.assertAllowed(decide(editor, "edit", self.child))
        self.assertAllowed(decide(editor, "delete", self.child))
        self.assertAllowed(decide(editor, "create", self.child))
        for action in (
            "submit",
            "approve",
            "reject",
            "withdraw",
            "archive",
            "transfer_ownership",
            "manage_editors",
        ):
            self.assertEqual(
                decide(editor, action, self.child).reason,
                "unsupported_action",
            )

    def test_published_parent_freezes_owned_rows(self):
        self.owner.user_permissions.add(model_permission(Source, "change_source"))
        owner = User.objects.get(pk=self.owner.pk)
        self.assertAllowed(decide(owner, "edit", self.child))
        self.source.publication_status = "published"
        self.source.save()
        decision = decide(owner, "edit", self.child)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "immutable_state")

    def test_child_read_delegates_to_parent_read(self):
        self.assertFalse(decide(self.anonymous, "read", self.child).allowed)
        self.source.add_editor(self.editor)
        self.assertAllowed(decide(self.editor, "read", self.child))
        self.assertAllowed(decide(self.editor, "export", self.child))
        self.source.publication_status = "published"
        self.source.save()
        self.assertAllowed(decide(self.anonymous, "read", self.child))

    def test_direct_and_group_editor_child_reads_and_scopes_match(self):
        self.source.add_editor(self.editor)
        self.source.add_editor_group(self.editor_group)
        children = SourceAuthor.objects.all()
        for user in (self.editor, self.group_editor):
            with self.subTest(user=user.username):
                self.assertAllowed(decide(user, "read", self.child))
                self.assertEqual(list(visible_queryset(user, children)), [self.child])
                self.assertEqual(
                    list(scope_queryset(user, children, "shared")), [self.child]
                )
        self.assertEqual(
            list(scope_queryset(self.owner, children, "owned")), [self.child]
        )
        self.assertEqual(list(scope_queryset(self.stranger, children)), [])


class MultiHopOwnedChildTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="hop-owner")
        self.editor = User.objects.create_user(username="hop-editor")
        self.stranger = User.objects.create_user(username="hop-stranger")
        self.greenhouse = Greenhouse.objects.create(
            name="Hop greenhouse", owner=self.owner
        )
        self.cycle = GreenhouseGrowthCycle.objects.create(
            owner=self.owner, greenhouse=self.greenhouse
        )
        distribution = TemporalDistribution.objects.create(
            name="Hop months", owner=self.owner
        )
        timestep = Timestep.objects.create(
            name="Hop step", owner=self.owner, distribution=distribution
        )
        self.timestepset = GrowthTimeStepSet.objects.create(
            timestep=timestep, growth_cycle=self.cycle
        )
        self.share = GrowthShare.objects.create(
            owner=self.stranger, timestepset=self.timestepset
        )

    def test_multi_hop_child_resolves_greenhouse_root(self):
        self.assertEqual(decide(self.owner, "read", self.timestepset).reason, "allowed")
        self.assertEqual(decide(self.owner, "read", self.share).reason, "allowed")
        self.assertEqual(
            decide(self.stranger, "read", self.share).reason, "no_object_access"
        )
        self.greenhouse.add_editor(self.editor)
        self.assertEqual(decide(self.editor, "read", self.share).reason, "allowed")

    def test_owned_child_owner_field_is_no_bypass(self):
        self.stranger.user_permissions.add(
            model_permission(Greenhouse, "change_greenhouse")
        )
        stranger = User.objects.get(pk=self.stranger.pk)
        decision = decide(stranger, "edit", self.share)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "no_object_access")

    def test_nullable_parent_missing_denies(self):
        orphan = GrowthShare.objects.create(owner=self.owner)
        decision = decide(self.owner, "read", orphan)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "invalid_parent")

    def test_reassign_to_missing_or_unsupported_parent_is_denied(self):
        for parent in (None, 42, "timestepset", []):
            with self.subTest(parent=parent):
                decision = decide_reassign(self.owner, self.share, parent)
                self.assertFalse(decision.allowed)
                self.assertEqual(decision.reason, "invalid_parent")

    def test_reassign_accepts_queryset_parent_selection(self):
        self.owner.user_permissions.add(
            model_permission(Greenhouse, "change_greenhouse")
        )
        owner = User.objects.get(pk=self.owner.pk)
        parents = Greenhouse.objects.filter(pk=self.greenhouse.pk)
        self.assertEqual(decide_reassign(owner, self.share, parents).reason, "allowed")

    def test_multi_hop_queryset_visibility_and_scopes(self):
        shares = GrowthShare.objects.filter(pk=self.share.pk)
        self.assertEqual(list(visible_queryset(self.stranger, shares)), [])
        self.assertEqual(list(visible_queryset(self.owner, shares)), [self.share])
        self.greenhouse.add_editor(self.editor)
        self.assertEqual(
            list(scope_queryset(self.editor, shares, "shared")), [self.share]
        )
        self.assertEqual(
            list(scope_queryset(self.owner, shares, "owned")), [self.share]
        )


class PublicCataloguePolicyTests(TestCase):
    def setUp(self):
        self.row = NantesGreenhouses.objects.create(lat=1.0, lon=2.0)
        self.staff = User.objects.create_user(username="catalogue-staff", is_staff=True)
        self.contributor = User.objects.create_user(username="catalogue-contributor")
        self.anonymous = AnonymousUser()

    def test_public_reads(self):
        self.assertTrue(decide(self.anonymous, "read", self.row).allowed)
        self.assertTrue(decide(self.anonymous, "export", self.row).allowed)
        self.assertEqual(
            list(
                visible_queryset(
                    self.anonymous, NantesGreenhouses.objects.all()
                ).values_list("pk", flat=True)
            ),
            [self.row.pk],
        )

    def test_public_reads_report_catalogue_route(self):
        for user in (self.anonymous, self.contributor):
            with self.subTest(user=user):
                self.assertTrue(decide(user, "read", self.row).allowed)
                self.assertEqual(
                    object_access_routes(user, self.row),
                    ["public catalogue (public read)"],
                )

    def test_staff_without_model_permission_is_denied(self):
        self.assertEqual(
            decide(self.staff, "edit", self.row).reason,
            "missing_model_permission",
        )
        self.assertEqual(
            decide(self.staff, "delete", self.row).reason,
            "missing_model_permission",
        )
        self.assertEqual(
            decide(self.staff, "create", NantesGreenhouses).reason,
            "missing_model_permission",
        )

    def test_lifecycle_actions_are_unsupported(self):
        for action in ("submit", "approve", "reject", "archive", "new_version"):
            self.assertEqual(
                decide(self.staff, action, self.row).reason, "unsupported_action"
            )

    def test_model_permission_grants_edit_and_delete(self):
        for codename in (
            "add_nantesgreenhouses",
            "change_nantesgreenhouses",
            "delete_nantesgreenhouses",
        ):
            self.contributor.user_permissions.add(
                model_permission(NantesGreenhouses, codename)
            )
        contributor = User.objects.get(pk=self.contributor.pk)
        self.assertTrue(decide(contributor, "edit", self.row).allowed)
        self.assertTrue(decide(contributor, "delete", self.row).allowed)
        self.assertTrue(decide(contributor, "create", NantesGreenhouses).allowed)

    def test_list_action_allows_collection_request(self):
        self.assertTrue(decide(self.anonymous, "list", NantesGreenhouses).allowed)
        self.assertTrue(decide(self.anonymous, "list", SourceAuthor).allowed)
        self.assertTrue(decide(self.anonymous, "list", Source).allowed)
        self.assertEqual(
            decide(self.anonymous, "read", Source).reason, "unsupported_action"
        )
        self.assertEqual(decide(self.anonymous, "list", Source).reason, "allowed")

    def test_catalogue_scopes(self):
        rows = NantesGreenhouses.objects.all()
        self.assertEqual(
            list(scope_queryset(self.anonymous, rows, "published")), [self.row]
        )
        self.assertEqual(list(scope_queryset(self.anonymous, rows)), [self.row])
        self.assertEqual(list(scope_queryset(self.anonymous, rows, "private")), [])
        self.assertEqual(list(scope_queryset(self.staff, rows, "private")), [])
        self.assertEqual(list(scope_queryset(self.staff, rows, "owned")), [])


class ProxyIdentityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="proxy-owner")
        self.editor = User.objects.create_user(username="proxy-editor")
        self.requester = User.objects.create_user(username="proxy-requester")

    def test_proxy_add_permission_not_concrete(self):
        component = MaterialComponent.objects.create(name="FM", owner=self.owner)
        concrete_ct = ContentType.objects.get_for_model(
            component, for_concrete_model=True
        )
        proxy_ct = ContentType.objects.get_for_model(
            MaterialComponent, for_concrete_model=False
        )
        self.assertNotEqual(concrete_ct, proxy_ct)
        self.requester.user_permissions.add(
            Permission.objects.get(
                content_type=concrete_ct, codename="add_basematerial"
            )
        )
        requester = User.objects.get(pk=self.requester.pk)
        self.assertFalse(decide(requester, "create", MaterialComponent).allowed)
        requester.user_permissions.add(
            Permission.objects.get(
                content_type=proxy_ct, codename="add_materialcomponent"
            )
        )
        requester = User.objects.get(pk=requester.pk)
        self.assertTrue(decide(requester, "create", MaterialComponent).allowed)

    def test_proxy_editor_grant_uses_concrete_content_type(self):
        component = MaterialComponent.objects.create(name="FM", owner=self.owner)
        component.add_editor(self.editor)
        grant_row = ObjectEditorGrant.objects.get(editor=self.editor)
        self.assertEqual(
            grant_row.content_type,
            ContentType.objects.get_for_model(component, for_concrete_model=True),
        )
        self.assertTrue(decide(self.editor, "read", component).allowed)

    def test_collection_catchment_proxy_identity(self):
        catchment = CollectionCatchment.objects.create(
            name="Proxy catchment", owner=self.owner
        )
        self.assertEqual(CollectionCatchment._meta.concrete_model, Catchment)
        catchment.add_editor(self.editor)
        grant_row = ObjectEditorGrant.objects.get(editor=self.editor)
        self.assertEqual(
            grant_row.content_type,
            ContentType.objects.get_for_model(Catchment),
        )
        self.assertTrue(decide(self.editor, "read", catchment).allowed)
        requester = User.objects.create_user(username="proxy-requester-2")
        self.assertFalse(decide(requester, "create", CollectionCatchment).allowed)
        proxy_ct = ContentType.objects.get_for_model(
            CollectionCatchment, for_concrete_model=False
        )
        requester.user_permissions.add(
            Permission.objects.get(
                content_type=proxy_ct, codename="add_collectioncatchment"
            )
        )
        requester = User.objects.get(pk=requester.pk)
        self.assertTrue(decide(requester, "create", CollectionCatchment).allowed)


class GeoreferencedOwnedTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="geo-owner")
        self.editor = User.objects.create_user(username="geo-editor")
        self.moderator = User.objects.create_user(username="geo-moderator")
        self.region = GeoreferencedRegion.objects.create(
            name="Geo region", owner=self.owner, country="DE"
        )
        vintage = NutsVintage.objects.create(year=2099, is_current=False)
        self.nuts = GeoreferencedNutsRegion.objects.create(
            name="Geo nuts", owner=self.owner, country="DE", version=vintage
        )
        self.catchment = GeoreferencedCatchment.objects.create(
            name="Geo catchment", owner=self.owner
        )

    def test_models_are_registered_with_app_registry(self):
        for model in (
            GeoreferencedRegion,
            GeoreferencedCatchment,
            GeoreferencedNutsRegion,
        ):
            self.assertEqual(model.__module__, "maps.models")
            self.assertIs(apps.get_model(model._meta.label_lower), model)
            self.assertEqual(model_policy(model).kind, KIND_OWNED)

    def test_registry_check_has_no_georeferenced_errors(self):
        errors = checks.registry_classification_check(None)
        self.assertEqual([e for e in errors if "georeferenced" in e.msg], [])

    def test_inherited_parent_read_and_edit(self):
        self.assertTrue(decide(self.owner, "read", self.region).allowed)
        self.assertFalse(decide(AnonymousUser(), "read", self.region).allowed)
        self.assertTrue(decide(self.owner, "read", self.catchment).allowed)
        self.assertTrue(decide(self.owner, "read", self.nuts).allowed)
        self.assertFalse(decide(self.owner, "edit", self.region).allowed)
        self.owner.user_permissions.add(
            model_permission(type(self.region.region_ptr), "change_region")
        )
        owner = User.objects.get(pk=self.owner.pk)
        self.assertTrue(decide(owner, "edit", self.region).allowed)
        self.region.region_ptr.add_editor(self.editor)
        self.editor.user_permissions.add(
            model_permission(type(self.region.region_ptr), "change_region")
        )
        editor = User.objects.get(pk=self.editor.pk)
        self.assertTrue(decide(editor, "edit", self.region).allowed)

    def test_published_parent_freezes_georeferenced_rows(self):
        self.owner.user_permissions.add(
            model_permission(type(self.region.region_ptr), "change_region")
        )
        owner = User.objects.get(pk=self.owner.pk)
        self.assertTrue(decide(owner, "edit", self.region).allowed)
        self.region.publication_status = "published"
        self.region.save()
        decision = decide(owner, "edit", self.region)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "immutable_state")

    def test_no_independent_lifecycle_actions(self):
        self.moderator.user_permissions.add(
            model_permission(type(self.region.region_ptr), "can_moderate_region")
        )
        moderator = User.objects.get(pk=self.moderator.pk)
        for action in ("approve", "submit", "archive", "transfer_ownership"):
            self.assertEqual(
                decide(moderator, action, self.region).reason,
                "unsupported_action",
            )


class ModerationPermissionSignalTests(TestCase):
    def test_recreates_deleted_permission_without_group_changes(self):
        content_type = ContentType.objects.get_for_model(
            Source, for_concrete_model=False
        )
        perm = Permission.objects.get(
            content_type=content_type, codename="can_moderate_source"
        )
        moderators, _ = Group.objects.get_or_create(name="moderators")
        member = User.objects.create_user(username="signal-mod-member")
        member.groups.add(moderators)
        legacy_extra = model_permission(Catchment, "change_catchment")
        moderators.permissions.set([legacy_extra])
        perm.delete()
        ensure_moderation_permissions(sender=None, using="default")
        recreated = Permission.objects.get(
            content_type=content_type, codename="can_moderate_source"
        )
        self.assertNotIn(recreated, moderators.permissions.all())
        ensure_moderation_permissions(sender=None, using="default")
        self.assertEqual(
            Permission.objects.filter(
                content_type=content_type, codename="can_moderate_source"
            ).count(),
            1,
        )
        moderators = Group.objects.get(name="moderators")
        self.assertEqual(list(moderators.permissions.all()), [legacy_extra])
        self.assertEqual(list(moderators.user_set.all()), [member])

    def test_ignores_post_migrate_senders_of_other_apps(self):
        content_type = ContentType.objects.get_for_model(
            Source, for_concrete_model=False
        )
        perm = Permission.objects.get(
            content_type=content_type, codename="can_moderate_source"
        )
        perm.delete()
        ensure_moderation_permissions(
            sender=SimpleNamespace(name="bibliography"), using="default"
        )
        self.assertFalse(
            Permission.objects.filter(
                content_type=content_type, codename="can_moderate_source"
            ).exists()
        )
        ensure_moderation_permissions(
            sender=SimpleNamespace(name="utils.object_management"),
            using="default",
        )
        self.assertTrue(
            Permission.objects.filter(
                content_type=content_type, codename="can_moderate_source"
            ).exists()
        )
