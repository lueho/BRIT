from io import StringIO

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from bibliography.models import Source, SourceAuthor
from sources.waste_collection.models import Collection
from users.roles import MANAGED_ROLES, ROLE_ADMINISTRATORS, ROLE_ANALYSIS_API
from utils.object_management.models import ReviewAction


def run_sync(*args):
    out = StringIO()
    call_command("sync_roles", *args, stdout=out)
    return out.getvalue()


def permission_for(model, codename):
    return Permission.objects.get(
        content_type=ContentType.objects.get_for_model(model, for_concrete_model=False),
        codename=codename,
    )


def group_permissions(name):
    return set(
        Group.objects.get(name=name).permissions.values_list(
            "content_type__app_label", "codename"
        )
    )


class SyncRolesTests(TestCase):
    def test_dry_run_creates_no_groups_or_grants(self):
        for name in MANAGED_ROLES:
            Group.objects.filter(name=name).delete()
        out = run_sync()
        for name in MANAGED_ROLES:
            self.assertFalse(
                Group.objects.filter(name=name).exists(),
                msg=f"dry-run must not create group {name}",
            )
        self.assertIn("registered", out)
        self.assertIn("missing", out)

    def test_apply_provisions_registered_baseline(self):
        run_sync("--apply")
        member = User.objects.create_user(username="role-member")
        member.groups.add(Group.objects.get(name="registered"))
        member = User.objects.get(pk=member.pk)
        for perm in (
            "bibliography.change_author",
            "bibliography.change_source",
            "materials.change_analyticalmethod",
            "materials.change_sample",
            "waste_collection.change_collection",
        ):
            self.assertTrue(member.has_perm(perm), msg=perm)
        registered = group_permissions("registered")
        self.assertIn(("bibliography", "change_source"), registered)
        self.assertIn(("bibliography", "change_author"), registered)
        self.assertIn(("waste_collection", "change_collection"), registered)
        self.assertIn(("materials", "change_sample"), registered)
        self.assertIn(("materials", "change_analyticalmethod"), registered)
        self.assertIn(("bibliography", "view_author"), registered)
        self.assertIn(("bibliography", "view_source"), registered)
        self.assertIn(("materials", "view_sample"), registered)

    def test_apply_provisions_analysis_api_capability(self):
        run_sync("--apply")
        analysis_api = group_permissions(ROLE_ANALYSIS_API)
        self.assertEqual(analysis_api, {("waste_collection", "access_analysis_api")})
        member = User.objects.create_user(username="analyst")
        member.groups.add(Group.objects.get(name=ROLE_ANALYSIS_API))
        member = User.objects.get(pk=member.pk)
        self.assertTrue(member.has_perm("waste_collection.access_analysis_api"))

    def test_apply_revokes_unmanifested_analysis_api_capability(self):
        run_sync("--apply")
        registered = Group.objects.get(name="registered")
        registered.permissions.add(permission_for(Collection, "access_analysis_api"))
        run_sync("--apply")
        registered = Group.objects.get(name="registered")
        self.assertNotIn(
            ("waste_collection", "access_analysis_api"),
            group_permissions("registered"),
        )

    def test_apply_does_not_grant_privileged_or_through_permissions(self):
        run_sync("--apply")
        registered = group_permissions("registered")
        self.assertNotIn(("object_management", "administer_objects"), registered)
        self.assertFalse(
            any(c.startswith("can_moderate_") for _, c in registered),
            msg=f"registered must not hold moderation rights: {sorted(registered)}",
        )
        through_ct = ContentType.objects.get_for_model(SourceAuthor)
        through_perms = {
            (through_ct.app_label, codename)
            for codename in Permission.objects.filter(
                content_type=through_ct
            ).values_list("codename", flat=True)
        }
        self.assertTrue(through_perms)
        self.assertTrue(registered.isdisjoint(through_perms))
        administrators = group_permissions(ROLE_ADMINISTRATORS)
        self.assertIn(("object_management", "administer_objects"), administrators)
        self.assertTrue(administrators.isdisjoint(through_perms))
        self.assertTrue(
            administrators.isdisjoint(
                {("auth", c) for c in ("add_user", "change_user", "delete_user")}
            )
        )

    def test_apply_is_idempotent(self):
        run_sync("--apply")
        snapshot = {
            name: set(
                Group.objects.get(name=name).permissions.values_list("pk", flat=True)
            )
            for name in MANAGED_ROLES
        }
        out = run_sync("--apply")
        for name, before in snapshot.items():
            self.assertEqual(
                set(
                    Group.objects.get(name=name).permissions.values_list(
                        "pk", flat=True
                    )
                ),
                before,
                msg=f"second --apply changed {name}",
            )
        self.assertIn("registered", out)

    def test_apply_preserves_extra_grants_and_membership(self):
        run_sync("--apply")
        registered = Group.objects.get(name="registered")
        extra = permission_for(SourceAuthor, "view_sourceauthor")
        registered.permissions.add(extra)
        member = User.objects.create_user(username="preserved-member")
        member.groups.add(registered)
        run_sync("--apply")
        registered = Group.objects.get(name="registered")
        self.assertIn(extra, registered.permissions.all())
        self.assertIn(member, registered.user_set.all())

    def test_apply_revokes_unmanifested_privileged_grants(self):
        run_sync("--apply")
        registered = Group.objects.get(name="registered")
        administer = Permission.objects.get(
            content_type=ContentType.objects.get_for_model(ReviewAction),
            codename="administer_objects",
        )
        moderate = permission_for(Source, "can_moderate_source")
        extra = permission_for(SourceAuthor, "view_sourceauthor")
        registered.permissions.add(administer, moderate, extra)
        member = User.objects.create_user(username="privileged-member")
        member.groups.add(registered)

        out = run_sync("--apply")

        registered = Group.objects.get(name="registered")
        granted = set(registered.permissions.all())
        self.assertNotIn(administer, granted)
        self.assertNotIn(moderate, granted)
        self.assertIn(extra, granted)
        self.assertIn("registered: revoked 2 privileged permissions", out)
        member = User.objects.get(pk=member.pk)
        self.assertFalse(member.has_perm("object_management.administer_objects"))
        self.assertFalse(member.has_perm("bibliography.can_moderate_source"))
        self.assertTrue(
            Group.objects.get(name=ROLE_ADMINISTRATORS)
            .permissions.filter(pk=administer.pk)
            .exists()
        )
        self.assertTrue(
            Group.objects.get(name="moderators")
            .permissions.filter(pk=moderate.pk)
            .exists()
        )

    def test_check_denies_extraneous_grants_and_preserves_them(self):
        Group.objects.filter(name="moderators").delete()
        run_sync("--apply")
        registered = Group.objects.get(name="registered")
        extra = permission_for(SourceAuthor, "view_sourceauthor")
        registered.permissions.add(extra)
        with self.assertRaises(CommandError):
            run_sync("--check")
        registered = Group.objects.get(name="registered")
        self.assertIn(extra, registered.permissions.all())
        run_sync("--apply")
        registered = Group.objects.get(name="registered")
        self.assertIn(extra, registered.permissions.all())

    def test_check_detects_drift_without_writes(self):
        run_sync("--apply")
        registered = Group.objects.get(name="registered")
        required = permission_for(Source, "change_source")
        registered.permissions.remove(required)
        with self.assertRaises(CommandError):
            run_sync("--check")
        registered = Group.objects.get(name="registered")
        self.assertNotIn(
            required.pk,
            set(registered.permissions.values_list("pk", flat=True)),
        )

    def test_missing_permission_row_fails_sync(self):
        admin_perm = Permission.objects.get(
            content_type=ContentType.objects.get_for_model(ReviewAction),
            codename="administer_objects",
        )
        admin_perm.delete()
        with self.assertRaises(CommandError) as caught:
            run_sync("--apply")
        self.assertIn("administer_objects", str(caught.exception))
