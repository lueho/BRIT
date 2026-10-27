"""Policy-aware Django admin adapter tests (domain-migration admin slice).

Verifies that registered admins for governed models delegate verbs to the
shared policy core, that owned-child inlines authorize against the parent
root, that bulk actions cannot bypass per-record checks, and that the review
audit log is append-only.
"""

from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import AnonymousUser, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist, PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse

from bibliography.admin import SourceAuthorInline
from bibliography.models import Author, Source, SourceAuthor
from inventories.models import (
    InventoryAlgorithm,
    InventoryAlgorithmParameter,
    InventoryAlgorithmParameterValue,
    Scenario,
    ScenarioInventoryConfiguration,
)
from maps.admin import (
    GeoDatasetColumnPolicyInline,
    GeoDatasetRuntimeConfigurationInline,
)
from maps.models import (
    CatchmentRevision,
    GeoDataset,
    GeoDatasetColumnPolicy,
    GeoDatasetRuntimeConfiguration,
    MapConfiguration,
    Region,
)
from materials.models import (
    Composition,
    Material,
    MaterialComponentGroup,
    MaterialProperty,
    MaterialPropertyValue,
    Sample,
)
from sources.waste_collection.models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionCatchment,
    CollectionSystem,
    WasteCategory,
)
from utils.object_management.admin import (
    PolicyAdminMixin,
    PolicyOwnedInlineMixin,
)
from utils.object_management.models import (
    ReviewAction,
    UserCreatedObject,
)
from utils.object_management.registry import KIND_OWNED, model_policy
from utils.object_management.services import _ACTIVE_MUTATION_ROOTS
from utils.properties.models import Property, Unit
from utils.tests.testcases import ensure_test_default_owner


def _perm(model, codename):
    permission, _ = Permission.objects.get_or_create(
        codename=codename,
        content_type=ContentType.objects.get_for_model(model, for_concrete_model=False),
        defaults={"name": f"Can {codename.replace('_', ' ')}"},
    )
    return permission


class PolicyAdminGuardTests(TestCase):
    """Every governed admin must go through the shared policy adapters."""

    def test_governed_admins_use_policy_mixin(self):
        missing = []
        for model, model_admin in admin.site._registry.items():
            governed = model_policy(model) is not None or issubclass(
                model, UserCreatedObject
            )
            if model is ReviewAction:
                continue
            if governed and not isinstance(model_admin, PolicyAdminMixin):
                missing.append(model._meta.label_lower)
        self.assertEqual(missing, [])

    def test_owned_inlines_use_policy_inline_mixin(self):
        missing = []
        for model_admin in admin.site._registry.values():
            for inline_class in model_admin.inlines:
                policy = model_policy(inline_class.model)
                if (
                    policy is not None
                    and policy.kind == KIND_OWNED
                    and not issubclass(inline_class, PolicyOwnedInlineMixin)
                ):
                    missing.append(inline_class.model._meta.label_lower)
        self.assertEqual(missing, [])

    def test_catchment_revision_admin_has_no_bulk_approve(self):
        model_admin = admin.site._registry[CatchmentRevision]
        self.assertFalse(hasattr(model_admin, "approve_selected"))
        self.assertNotIn("approve_selected", model_admin.actions)


class PolicyAdminAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        default_owner = ensure_test_default_owner()
        Unit.objects.get_or_create(name="No unit", owner=default_owner)
        cls.owner = User.objects.create_user(username="admin-owner", is_staff=True)
        cls.owner.user_permissions.add(
            _perm(Property, "change_property"),
            _perm(Property, "add_property"),
            _perm(Property, "delete_property"),
        )
        cls.stranger = User.objects.create_user(
            username="admin-stranger", is_staff=True
        )
        cls.stranger.user_permissions.add(
            _perm(Property, "change_property"), _perm(Property, "add_property")
        )
        cls.no_perms_staff = User.objects.create_user(
            username="admin-plainstaff", is_staff=True
        )
        cls.unit = Unit.objects.create(name="kilogram", owner=cls.owner)
        cls.private_property = Property.objects.create(
            name="private-admin-property", owner=cls.owner
        )
        cls.private_property.allowed_units.add(cls.unit)
        cls.foreign_property = Property.objects.create(
            name="foreign-admin-property", owner=cls.stranger
        )
        cls.published_property = Property.objects.create(
            name="published-admin-property",
            owner=cls.stranger,
            publication_status="published",
        )

    def _change_url(self, obj):
        return reverse(
            f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change",
            args=[obj.pk],
        )

    def test_changelist_scopes_rows_by_read_visibility(self):
        self.client.force_login(self.stranger)
        response = self.client.get(reverse("admin:properties_property_changelist"))
        self.assertEqual(response.status_code, 200)
        results = response.context["cl"].result_list
        self.assertIn(self.published_property, results)
        self.assertIn(self.foreign_property, results)
        self.assertNotIn(self.private_property, results)

    def test_staff_without_object_access_denied_change(self):
        self.client.force_login(self.stranger)
        response = self.client.get(self._change_url(self.private_property))
        self.assertNotEqual(response.status_code, 200)
        self.client.post(
            self._change_url(self.private_property),
            {"name": "forged", "_save": "Save"},
        )
        self.private_property.refresh_from_db()
        self.assertEqual(self.private_property.name, "private-admin-property")

    def test_owner_changeform_post_bumps_revision_once(self):
        property_ = self.private_property
        revision_before = property_.content_revision
        self.client.force_login(self.owner)
        response = self.client.post(
            self._change_url(property_),
            {
                "name": "renamed-by-owner",
                "allowed_units": [str(self.unit.pk)],
                "_save": "Save",
            },
        )
        self.assertIn(response.status_code, (200, 302))
        property_.refresh_from_db()
        self.assertEqual(property_.name, "renamed-by-owner")
        self.assertEqual(property_.content_revision, revision_before + 1)
        edits = ReviewAction.objects.filter(
            content_type=ContentType.objects.get_for_model(Property),
            object_id=property_.pk,
            action=ReviewAction.ACTION_EDITED,
        )
        self.assertEqual(edits.count(), 1)

    def test_changeform_post_cannot_forge_protected_metadata(self):
        property_ = self.private_property
        revision_before = property_.content_revision
        self.client.force_login(self.owner)
        self.client.post(
            self._change_url(property_),
            {
                "name": "still-mine",
                "allowed_units": [str(self.unit.pk)],
                "owner": str(self.stranger.pk),
                "publication_status": "published",
                "content_revision": "99",
                "_save": "Save",
            },
        )
        property_.refresh_from_db()
        self.assertEqual(property_.owner_id, self.owner.pk)
        self.assertEqual(property_.publication_status, "private")
        self.assertEqual(property_.content_revision, revision_before + 1)

    def test_frozen_object_denies_admin_post(self):
        admin_user = User.objects.create_user(
            username="admin-frozen", is_staff=True, is_superuser=True
        )
        admin_user.user_permissions.add(_perm(Property, "change_property"))
        self.client.force_login(admin_user)
        response = self.client.post(
            self._change_url(self.published_property),
            {
                "name": "forged-edit",
                "allowed_units": [str(self.unit.pk)],
                "_save": "Save",
            },
        )
        self.assertNotEqual(response.status_code, 302)
        self.published_property.refresh_from_db()
        self.assertEqual(self.published_property.name, "published-admin-property")

    def test_addform_serverside_sets_owner_and_private(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("admin:properties_property_add"),
            {
                "name": "created-via-admin",
                "allowed_units": [str(self.unit.pk)],
                "owner": str(self.stranger.pk),
                "publication_status": "published",
                "_save": "Save",
            },
        )
        self.assertIn(response.status_code, (200, 302))
        created = Property.objects.get(name="created-via-admin")
        self.assertEqual(created.owner_id, self.owner.pk)
        self.assertEqual(created.publication_status, "private")
        self.assertTrue(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Property),
                object_id=created.pk,
                action=ReviewAction.ACTION_CREATED,
            ).exists()
        )

    def test_bulk_delete_skips_denied_records(self):
        admin_user = User.objects.create_user(username="admin-bulkdel", is_staff=True)
        admin_user.user_permissions.add(
            _perm(Property, "delete_property"), _perm(Property, "change_property")
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("admin:properties_property_changelist"),
            {
                "action": "delete_selected",
                "_selected_action": [
                    str(self.private_property.pk),
                    str(self.foreign_property.pk),
                ],
                "post": "yes",
            },
            follow=True,
        )
        self.assertIn(response.status_code, (200, 302))
        self.assertFalse(Property.objects.filter(pk=self.private_property.pk).exists())
        self.assertTrue(Property.objects.filter(pk=self.foreign_property.pk).exists())


class PolicyAdminInlineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        default_owner = ensure_test_default_owner()
        Unit.objects.get_or_create(name="No unit", owner=default_owner)
        cls.owner = User.objects.create_user(username="inline-owner", is_staff=True)
        cls.owner.user_permissions.add(
            _perm(Source, "change_source"), _perm(Author, "add_author")
        )
        # Stock child perms admit an unadapted inline into the changeform;
        # the fail-closed persistence test relies on them.
        cls.owner.user_permissions.add(
            _perm(SourceAuthor, "view_sourceauthor"),
            _perm(SourceAuthor, "add_sourceauthor"),
            _perm(SourceAuthor, "change_sourceauthor"),
        )
        cls.author = Author.objects.create(
            first_names="Ada", last_names="Lovelace", owner=cls.owner
        )
        cls.source = Source.objects.create(
            title="Inline source", type="misc", owner=cls.owner
        )

    def _inline_post_data(self, title="Inline source"):
        return {
            "title": title,
            "type": "misc",
            "sourceauthors-TOTAL_FORMS": "1",
            "sourceauthors-INITIAL_FORMS": "0",
            "sourceauthors-MIN_NUM_FORMS": "0",
            "sourceauthors-MAX_NUM_FORMS": "1000",
            "sourceauthors-0-author": str(self.author.pk),
            "sourceauthors-0-position": "1",
            "_save": "Save",
        }

    def test_owner_inline_create_uses_parent_scope(self):
        revision_before = self.source.content_revision
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("admin:bibliography_source_change", args=[self.source.pk]),
            self._inline_post_data(),
        )
        self.assertIn(response.status_code, (200, 302))
        self.source.refresh_from_db()
        self.assertEqual(self.source.sourceauthors.count(), 1)
        self.assertEqual(self.source.content_revision, revision_before + 1)

    def test_inline_on_published_parent_denied(self):
        self.source.publication_status = "published"
        self.source.save()
        self.client.force_login(self.owner)
        self.client.post(
            reverse("admin:bibliography_source_change", args=[self.source.pk]),
            self._inline_post_data(),
        )
        self.assertEqual(self.source.sourceauthors.count(), 0)

    def test_save_formset_authorization_runs_on_real_parent_post(self):
        """The parent admin's ``save_formset`` hook — the one Django
        actually invokes — must reach the inline's ``authorize_formset``;
        a denial at persistence aborts the whole response atomically."""
        revision_before = self.source.content_revision
        self.client.force_login(self.owner)
        with patch.object(
            SourceAuthorInline,
            "authorize_formset",
            autospec=True,
            side_effect=PermissionDenied("insufficient_parent_access"),
        ) as gate:
            response = self.client.post(
                reverse("admin:bibliography_source_change", args=[self.source.pk]),
                self._inline_post_data(),
            )
        self.assertTrue(gate.called)
        self.assertEqual(response.status_code, 403)
        self.source.refresh_from_db()
        self.assertEqual(self.source.sourceauthors.count(), 0)
        self.assertEqual(self.source.content_revision, revision_before)

    def test_registry_owned_inline_without_adapter_fails_closed(self):
        """A registry-owned inline model behind a plain Django inline has
        no ``authorize_formset``; touched rows must fail closed."""

        class PlainSourceAuthorInline(admin.TabularInline):
            model = SourceAuthor
            extra = 1

        source_admin = admin.site._registry[Source]
        revision_before = self.source.content_revision
        self.client.force_login(self.owner)
        with patch.object(type(source_admin), "inlines", [PlainSourceAuthorInline]):
            response = self.client.post(
                reverse("admin:bibliography_source_change", args=[self.source.pk]),
                self._inline_post_data(),
            )
        self.assertEqual(response.status_code, 403)
        self.source.refresh_from_db()
        self.assertEqual(self.source.sourceauthors.count(), 0)
        self.assertEqual(self.source.content_revision, revision_before)

    def test_get_inlines_dynamic_resolution_authorizes_owned_inline(self):
        """Dispatch resolves the declared adapter via ``get_inlines()``,
        not the static ``inlines`` list — a dynamically provided owned
        inline still gets its ``authorize_formset`` invoked."""
        source_admin = admin.site._registry[Source]
        revision_before = self.source.content_revision
        self.client.force_login(self.owner)
        with (
            patch.object(type(source_admin), "inlines", []),
            patch.object(
                type(source_admin),
                "get_inlines",
                autospec=True,
                side_effect=lambda self_, request, obj: [SourceAuthorInline],
            ),
        ):
            response = self.client.post(
                reverse("admin:bibliography_source_change", args=[self.source.pk]),
                self._inline_post_data(),
            )
        self.assertEqual(response.status_code, 302)
        self.source.refresh_from_db()
        self.assertEqual(self.source.sourceauthors.count(), 1)
        self.assertEqual(self.source.content_revision, revision_before + 1)


class InlineMisuseFailClosedTests(TestCase):
    """A governed inline model without a working ``authorize_formset``
    adapter fails closed on touched rows — covering both a plain Django
    inline and the owned-only adapter misused on independent evidence."""

    @classmethod
    def setUpTestData(cls):
        default_owner = ensure_test_default_owner()
        Unit.objects.get_or_create(name="No unit", owner=default_owner)
        cls.owner = User.objects.create_user(username="misuse-owner", is_staff=True)
        cls.owner.user_permissions.add(
            _perm(Sample, "change_sample"),
            _perm(MaterialPropertyValue, "add_materialpropertyvalue"),
            _perm(MaterialPropertyValue, "view_materialpropertyvalue"),
            _perm(MaterialPropertyValue, "change_materialpropertyvalue"),
        )
        cls.material = Material.objects.create(name="Misuse material", owner=cls.owner)
        cls.sample = Sample.objects.create(
            name="Misuse sample",
            owner=cls.owner,
            material=cls.material,
            publication_status="private",
        )
        cls.material_property = MaterialProperty.objects.create(
            name="Misuse property", owner=cls.owner
        )
        cls.unit = Unit.objects.create(name="Misuse unit", owner=cls.owner)
        cls.source = Source.objects.create(
            title="Misuse source", type="misc", owner=cls.owner
        )

    def _post_with_mpv_row(self):
        return {
            "name": self.sample.name,
            "material": str(self.material.pk),
            "standalone": "on",
            "sources": [str(self.source.pk)],
            "sample_authors-TOTAL_FORMS": "0",
            "sample_authors-INITIAL_FORMS": "0",
            "sample_authors-MIN_NUM_FORMS": "0",
            "sample_authors-MAX_NUM_FORMS": "1000",
            "property_values-TOTAL_FORMS": "1",
            "property_values-INITIAL_FORMS": "0",
            "property_values-MIN_NUM_FORMS": "0",
            "property_values-MAX_NUM_FORMS": "1000",
            "property_values-0-property": str(self.material_property.pk),
            "property_values-0-average": "1.5",
            "property_values-0-unit": str(self.unit.pk),
            "property_values-0-value_qualifier": "exact",
            "_save": "Save",
        }

    def _assert_denied_and_unchanged(self, response, revision_before):
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            MaterialPropertyValue.objects.filter(sample=self.sample).exists()
        )
        self.sample.refresh_from_db()
        self.assertEqual(self.sample.content_revision, revision_before)

    def test_plain_inline_on_independent_evidence_fails_closed(self):
        class PlainMPVInline(admin.TabularInline):
            model = MaterialPropertyValue
            extra = 1
            # No policy adapter, no authorize_formset — a governed inline
            # model behind a plain Django inline must fail closed.
            fields = ("property", "average", "unit", "value_qualifier")

        sample_admin = admin.site._registry[Sample]
        revision_before = self.sample.content_revision
        self.client.force_login(self.owner)
        with patch.object(
            type(sample_admin),
            "get_inlines",
            autospec=True,
            side_effect=lambda self_, request, obj: [
                *self_.inlines,
                PlainMPVInline,
            ],
        ):
            response = self.client.post(
                reverse("admin:materials_sample_change", args=[self.sample.pk]),
                self._post_with_mpv_row(),
            )
        self._assert_denied_and_unchanged(response, revision_before)

    def test_owned_only_adapter_on_independent_evidence_fails_closed(self):
        class MisuseMPVInline(PolicyOwnedInlineMixin, admin.TabularInline):
            model = MaterialPropertyValue
            extra = 1

        sample_admin = admin.site._registry[Sample]
        revision_before = self.sample.content_revision
        self.client.force_login(self.owner)
        # The owned-only adapter denies every admission predicate for a
        # non-owned model; force admission open so the persistence-time
        # authorize_formset gate is what rejects the touched rows.
        with (
            patch.object(
                type(sample_admin),
                "get_inlines",
                autospec=True,
                side_effect=lambda self_, request, obj: [
                    *self_.inlines,
                    MisuseMPVInline,
                ],
            ),
            patch.object(
                MisuseMPVInline,
                "has_add_permission",
                autospec=True,
                return_value=True,
            ),
        ):
            response = self.client.post(
                reverse("admin:materials_sample_change", args=[self.sample.pk]),
                self._post_with_mpv_row(),
            )
        self._assert_denied_and_unchanged(response, revision_before)


class ReviewActionAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        default_owner = ensure_test_default_owner()
        Unit.objects.get_or_create(name="No unit", owner=default_owner)
        cls.superuser = User.objects.create_user(
            username="audit-super", is_staff=True, is_superuser=True
        )
        cls.owner = User.objects.create_user(username="audit-owner", is_staff=True)
        cls.stranger = User.objects.create_user(
            username="audit-stranger", is_staff=True
        )
        cls.moderator = User.objects.create_user(
            username="audit-moderator", is_staff=True
        )
        cls.moderator.user_permissions.add(_perm(Property, "can_moderate_property"))
        cls.property = Property.objects.create(
            name="audit-target", owner=cls.owner, publication_status="review"
        )
        cls.event = ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(Property),
            object_id=cls.property.pk,
            action=ReviewAction.ACTION_SUBMITTED,
            user=cls.owner,
        )

    def test_superuser_cannot_add_change_or_delete(self):
        model_admin = admin.site._registry[ReviewAction]
        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = self.superuser
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
        self.assertEqual(model_admin.actions, [])

    def test_owner_and_moderator_see_target_history(self):
        model_admin = admin.site._registry[ReviewAction]
        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = self.owner
        self.assertIn(self.event, list(model_admin.get_queryset(request)))
        request.user = self.moderator
        self.assertIn(self.event, list(model_admin.get_queryset(request)))

    def test_stranger_cannot_see_private_target_history(self):
        model_admin = admin.site._registry[ReviewAction]
        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = self.stranger
        self.assertNotIn(self.event, list(model_admin.get_queryset(request)))

    def test_inactive_and_anonymous_actors_see_nothing(self):
        model_admin = admin.site._registry[ReviewAction]
        factory = RequestFactory()
        inactive = User.objects.create_user(
            username="audit-inactive", is_staff=True, is_active=False
        )
        request = factory.get("/admin/")
        request.user = inactive
        self.assertFalse(model_admin.has_view_permission(request))
        self.assertEqual(list(model_admin.get_queryset(request)), [])
        request.user = AnonymousUser()
        self.assertFalse(model_admin.has_view_permission(request))
        self.assertEqual(list(model_admin.get_queryset(request)), [])

    def test_raw_view_permission_does_not_expose_foreign_history(self):
        model_admin = admin.site._registry[ReviewAction]
        viewer = User.objects.create_user(username="audit-viewperm", is_staff=True)
        viewer.user_permissions.add(_perm(ReviewAction, "view_reviewaction"))
        request = RequestFactory().get("/admin/")
        request.user = viewer
        # Site-level permission admits the changelist URL but cannot widen
        # which target histories the queryset contains.
        self.assertTrue(model_admin.has_view_permission(request))
        self.assertNotIn(self.event, list(model_admin.get_queryset(request)))
        request_with_obj = RequestFactory().get("/admin/")
        request_with_obj.user = viewer
        self.assertFalse(model_admin.has_view_permission(request_with_obj, self.event))

    def test_moderator_sees_archived_target_history(self):
        archived = Property.objects.create(
            name="audit-archived",
            owner=self.stranger,
            publication_status="archived",
        )
        event = ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(Property),
            object_id=archived.pk,
            action=ReviewAction.ACTION_ARCHIVED,
            user=self.owner,
        )
        model_admin = admin.site._registry[ReviewAction]
        request = RequestFactory().get("/admin/")
        request.user = self.moderator
        self.assertIn(event, list(model_admin.get_queryset(request)))
        request.user = User.objects.create_user(username="audit-plain", is_staff=True)
        self.assertNotIn(event, list(model_admin.get_queryset(request)))

    def test_administrator_sees_orphan_target_history(self):
        orphan = ReviewAction.objects.create(
            content_type=ContentType.objects.get_for_model(Property),
            object_id=999999,
            action=ReviewAction.ACTION_DELETED,
            user=self.owner,
        )
        model_admin = admin.site._registry[ReviewAction]
        request = RequestFactory().get("/admin/")
        request.user = self.superuser
        self.assertIn(orphan, list(model_admin.get_queryset(request)))
        self.assertTrue(model_admin.has_view_permission(request, orphan))
        request.user = self.stranger
        self.assertNotIn(orphan, list(model_admin.get_queryset(request)))
        self.assertFalse(model_admin.has_view_permission(request, orphan))

    def test_changelist_admits_core_participants_without_model_permission(self):
        # Owner and model moderator hold no view_reviewaction permission;
        # active-actor class admission plus the scoped queryset must still
        # open the real changelist and show only allowed history.
        url = reverse("admin:object_management_reviewaction_changelist")
        self.assertFalse(self.owner.has_perm("object_management.view_reviewaction"))
        self.assertFalse(self.moderator.has_perm("object_management.view_reviewaction"))
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.event, list(response.context["cl"].result_list))
        self.client.force_login(self.moderator)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.event, list(response.context["cl"].result_list))

    def test_changelist_empty_for_plain_staff_and_inactive_denied(self):
        url = reverse("admin:object_management_reviewaction_changelist")
        self.client.force_login(self.stranger)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.event, list(response.context["cl"].result_list))
        inactive = User.objects.create_user(
            username="audit-inactive-cl", is_staff=True, is_active=False
        )
        self.client.force_login(inactive)
        # Inactive staff fail the admin site gate and are bounced to login.
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])
        model_admin = admin.site._registry[ReviewAction]
        request = RequestFactory().get("/admin/")
        request.user = self.owner
        self.assertTrue(model_admin.has_module_permission(request))
        request.user = inactive
        self.assertFalse(model_admin.has_module_permission(request))
        request.user = AnonymousUser()
        self.assertFalse(model_admin.has_module_permission(request))

    def test_raw_view_permission_changelist_never_widens_rows(self):
        viewer = User.objects.create_user(username="audit-viewperm-cl", is_staff=True)
        viewer.user_permissions.add(_perm(ReviewAction, "view_reviewaction"))
        self.client.force_login(viewer)
        response = self.client.get(
            reverse("admin:object_management_reviewaction_changelist")
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.event, list(response.context["cl"].result_list))


class PolicyOwnedInlineScopingTests(TestCase):
    """Inline reference formfields only offer and accept rows the acting user
    may read; a forged inaccessible reference fails without side effects."""

    @classmethod
    def setUpTestData(cls):
        default_owner = ensure_test_default_owner()
        Unit.objects.get_or_create(name="No unit", owner=default_owner)
        cls.owner = User.objects.create_user(username="scope-owner", is_staff=True)
        cls.owner.user_permissions.add(
            _perm(Source, "change_source"), _perm(Source, "add_source")
        )
        cls.stranger = User.objects.create_user(
            username="scope-stranger", is_staff=True
        )
        cls.own_author = Author.objects.create(
            first_names="Own", last_names="Author", owner=cls.owner
        )
        cls.shared_author = Author.objects.create(
            first_names="Shared", last_names="Author", owner=cls.stranger
        )
        cls.shared_author.add_editor(cls.owner)
        cls.published_author = Author.objects.create(
            first_names="Published",
            last_names="Author",
            owner=cls.stranger,
            publication_status="published",
        )
        cls.foreign_author = Author.objects.create(
            first_names="Foreign", last_names="Private", owner=cls.stranger
        )
        cls.source = Source.objects.create(
            title="Scoped source", type="misc", owner=cls.owner
        )

    def _inline_post(self, *authors):
        data = {
            "title": "Scoped source",
            "type": "misc",
            "sourceauthors-TOTAL_FORMS": str(len(authors)),
            "sourceauthors-INITIAL_FORMS": "0",
            "sourceauthors-MIN_NUM_FORMS": "0",
            "sourceauthors-MAX_NUM_FORMS": "1000",
            "_save": "Save",
        }
        for index, author in enumerate(authors):
            data[f"sourceauthors-{index}-author"] = str(author.pk)
            data[f"sourceauthors-{index}-position"] = str(index + 1)
        return data

    def test_inaccessible_inline_reference_fails_without_side_effects(self):
        revision_before = self.source.content_revision
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("admin:bibliography_source_change", args=[self.source.pk]),
            self._inline_post(self.foreign_author),
        )
        self.assertNotEqual(response.status_code, 302)
        self.source.refresh_from_db()
        self.assertEqual(self.source.sourceauthors.count(), 0)
        self.assertEqual(self.source.content_revision, revision_before)
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Source),
                object_id=self.source.pk,
            ).exists()
        )

    def test_accessible_inline_references_save_in_one_revision(self):
        revision_before = self.source.content_revision
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("admin:bibliography_source_change", args=[self.source.pk]),
            self._inline_post(
                self.own_author, self.shared_author, self.published_author
            ),
        )
        self.assertIn(response.status_code, (200, 302))
        self.source.refresh_from_db()
        self.assertEqual(self.source.sourceauthors.count(), 3)
        self.assertEqual(self.source.content_revision, revision_before + 1)


class CompoundSourceCreationTests(TestCase):
    """New Source + author rows are a compound create governed by add_source
    alone; inaccessible references reject atomically."""

    @classmethod
    def setUpTestData(cls):
        default_owner = ensure_test_default_owner()
        Unit.objects.get_or_create(name="No unit", owner=default_owner)
        cls.creator = User.objects.create_user(
            username="compound-creator", is_staff=True
        )
        cls.creator.user_permissions.add(_perm(Source, "add_source"))
        cls.stranger = User.objects.create_user(
            username="compound-stranger", is_staff=True
        )
        cls.published_author = Author.objects.create(
            first_names="Visible",
            last_names="Author",
            owner=cls.stranger,
            publication_status="published",
        )
        cls.foreign_author = Author.objects.create(
            first_names="Foreign",
            last_names="Private",
            owner=cls.stranger,
        )

    def _add_post(self, author):
        return {
            "title": "Compound source",
            "type": "misc",
            "sourceauthors-TOTAL_FORMS": "1",
            "sourceauthors-INITIAL_FORMS": "0",
            "sourceauthors-MIN_NUM_FORMS": "0",
            "sourceauthors-MAX_NUM_FORMS": "1000",
            "sourceauthors-0-author": str(author.pk),
            "sourceauthors-0-position": "1",
            "_save": "Save",
        }

    def test_compound_create_with_accessible_author(self):
        self.client.force_login(self.creator)
        response = self.client.post(
            reverse("admin:bibliography_source_add"),
            self._add_post(self.published_author),
        )
        self.assertEqual(response.status_code, 302)
        source = Source.objects.get(title="Compound source")
        self.assertEqual(source.owner_id, self.creator.pk)
        self.assertEqual(source.publication_status, "private")
        self.assertEqual(source.sourceauthors.count(), 1)
        event = ReviewAction.objects.get(
            content_type=ContentType.objects.get_for_model(Source),
            object_id=source.pk,
            action=ReviewAction.ACTION_CREATED,
        )
        self.assertEqual(event.content_revision, source.content_revision)

    def test_compound_create_with_inaccessible_author_is_atomic(self):
        self.client.force_login(self.creator)
        response = self.client.post(
            reverse("admin:bibliography_source_add"),
            self._add_post(self.foreign_author),
        )
        self.assertNotEqual(response.status_code, 302)
        self.assertFalse(Source.objects.filter(title="Compound source").exists())
        self.assertFalse(
            SourceAuthor.objects.filter(author=self.foreign_author).exists()
        )
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Source),
                action=ReviewAction.ACTION_CREATED,
            ).exists()
        )


class AdminBoundaryRequestLocalTests(TestCase):
    """The changeform boundary lives on the request, keyed to the locked row —
    never on the shared ModelAdmin singleton."""

    @classmethod
    def setUpTestData(cls):
        default_owner = ensure_test_default_owner()
        Unit.objects.get_or_create(name="No unit", owner=default_owner)
        cls.owner = User.objects.create_user(username="boundary-owner", is_staff=True)
        cls.owner.user_permissions.add(
            _perm(Property, "change_property"), _perm(Author, "add_author")
        )
        cls.owner.user_permissions.add(_perm(Source, "change_source"))
        cls.property = Property.objects.create(name="boundary-prop", owner=cls.owner)
        cls.author = Author.objects.create(
            first_names="Ada", last_names="Lovelace", owner=cls.owner
        )
        cls.source = Source.objects.create(
            title="Boundary source", type="misc", owner=cls.owner
        )

    def test_boundary_state_is_scoped_per_request(self):
        model_admin = admin.site._registry[Property]
        factory = RequestFactory()
        request_a = factory.post("/admin/x/")
        request_a.user = self.owner
        request_b = factory.post("/admin/x/")
        request_b.user = self.owner

        model_admin._open_policy_boundary(request_a, self.property)
        self.assertTrue(model_admin._policy_boundary_open(request_a, self.property))
        # A second request to the same admin shares no boundary state.
        self.assertFalse(model_admin._policy_boundary_open(request_b, self.property))
        model_admin._close_policy_boundary(request_a, self.property)
        self.assertFalse(model_admin._policy_boundary_open(request_a, self.property))

    def test_inline_audit_failure_rolls_back_root_and_children(self):
        revision_before = self.source.content_revision
        self.client.force_login(self.owner)
        self.client.raise_request_exception = False
        post = {
            "title": "Boundary source",
            "type": "misc",
            "sourceauthors-TOTAL_FORMS": "1",
            "sourceauthors-INITIAL_FORMS": "0",
            "sourceauthors-MIN_NUM_FORMS": "0",
            "sourceauthors-MAX_NUM_FORMS": "1000",
            "sourceauthors-0-author": str(self.author.pk),
            "sourceauthors-0-position": "1",
            "_save": "Save",
        }
        with (
            self.assertLogs("django.request", level="ERROR") as logged,
            patch(
                "utils.object_management.services._record_event",
                side_effect=RuntimeError("audit transport failed"),
            ),
        ):
            response = self.client.post(
                reverse("admin:bibliography_source_change", args=[self.source.pk]),
                post,
            )
        self.assertEqual(response.status_code, 500)
        self.assertIn("audit transport failed", "\n".join(logged.output))
        self.source.refresh_from_db()
        self.assertEqual(self.source.content_revision, revision_before)
        self.assertEqual(self.source.sourceauthors.count(), 0)

    def test_owned_save_boundary_reused_for_same_parent(self):
        """Registering the same parent twice on one request reuses the
        open boundary — no second context, and the root still bumps and
        audits exactly once."""
        model_admin = admin.site._registry[Property]
        request = RequestFactory().post("/admin/x/")
        request.user = self.owner
        revision_before = self.property.content_revision
        first = model_admin._open_owned_save_boundary(request, self.property)
        second = model_admin._open_owned_save_boundary(request, self.property)
        self.assertIs(first, second)
        self.property.name = "boundary-reused"
        self.property.save()
        model_admin._close_owned_save_boundaries(request)
        self.property.refresh_from_db()
        self.assertEqual(self.property.name, "boundary-reused")
        self.assertEqual(self.property.content_revision, revision_before + 1)
        self.assertEqual(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Property),
                object_id=self.property.pk,
            ).count(),
            1,
        )
        self.assertFalse(_ACTIVE_MUTATION_ROOTS.get())

    def test_owned_save_boundaries_unwind_all_on_inner_exit_failure(self):
        """A failing inner boundary exit must still unwind the outer
        boundary: both roots roll back, no ContextVar or request state
        leaks, and the next request audits normally."""
        model_admin = admin.site._registry[Property]
        other = Property.objects.create(name="boundary-two", owner=self.owner)
        request = RequestFactory().post("/admin/x/")
        request.user = self.owner
        revision_before = self.property.content_revision
        other_revision_before = other.content_revision
        model_admin._open_owned_save_boundary(request, self.property)
        model_admin._open_owned_save_boundary(request, other)
        self.property.name = "boundary-one-changed"
        self.property.save()
        other.name = "boundary-two-changed"
        other.save()
        with (
            patch(
                "utils.object_management.services._record_event",
                side_effect=RuntimeError("audit transport failed"),
            ),
            self.assertRaises(RuntimeError),
        ):
            model_admin._close_owned_save_boundaries(request)
        self.property.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(self.property.name, "boundary-prop")
        self.assertEqual(other.name, "boundary-two")
        self.assertEqual(self.property.content_revision, revision_before)
        self.assertEqual(other.content_revision, other_revision_before)
        self.assertFalse(_ACTIVE_MUTATION_ROOTS.get())
        self.assertIsNone(getattr(request, "_policy_owned_save_boundaries", None))

        # The next request performs the audit normally.
        followup = RequestFactory().post("/admin/x/")
        followup.user = self.owner
        model_admin._open_owned_save_boundary(followup, self.property)
        self.property.name = "boundary-one-final"
        self.property.save()
        model_admin._close_owned_save_boundaries(followup)
        self.property.refresh_from_db()
        self.assertEqual(self.property.content_revision, revision_before + 1)
        self.assertEqual(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Property),
                object_id=self.property.pk,
            ).count(),
            1,
        )


class OwnedStandaloneAdminTests(TestCase):
    """Standalone owned-child admin (Composition on Sample): create goes
    through the validated parent; edits and forged reparents are contained."""

    @classmethod
    def setUpTestData(cls):
        default_owner = ensure_test_default_owner()
        Unit.objects.get_or_create(name="No unit", owner=default_owner)
        cls.owner = User.objects.create_user(username="owned-owner", is_staff=True)
        # No add_composition/change_composition: the parent edit rule is the
        # capability for owned children.
        cls.owner.user_permissions.add(_perm(Sample, "change_sample"))
        cls.stranger = User.objects.create_user(
            username="owned-stranger", is_staff=True
        )
        cls.stranger.user_permissions.add(_perm(Sample, "change_sample"))

        cls.material = Material.objects.create(
            name="Owned admin material", owner=cls.owner
        )
        cls.sample = Sample.objects.create(
            name="Owned admin sample",
            owner=cls.owner,
            material=cls.material,
            publication_status="private",
        )
        cls.archived_sample = Sample.objects.create(
            name="Owned archived sample",
            owner=cls.owner,
            material=cls.material,
            publication_status="archived",
        )
        cls.foreign_sample = Sample.objects.create(
            name="Foreign sample",
            owner=cls.stranger,
            material=cls.material,
            publication_status="private",
        )
        cls.group = MaterialComponentGroup.objects.create(
            name="Owned admin group", owner=cls.owner
        )
        cls.composition = Composition.objects.create(
            sample=cls.sample, group=cls.group, order=10
        )

    def test_owner_adds_composition_through_own_sample_once(self):
        revision_before = self.sample.content_revision
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("admin:materials_composition_add"),
            {
                "name": "Admin composition",
                "sample": str(self.sample.pk),
                "group": str(self.group.pk),
                "order": "20",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = Composition.objects.get(
            name="Admin composition",
            sample=self.sample,
            group=self.group,
        )
        self.assertEqual(created.owner, self.owner)
        self.assertEqual(created.publication_status, "private")
        self.sample.refresh_from_db()
        self.assertEqual(self.sample.content_revision, revision_before + 1)
        events = ReviewAction.objects.filter(
            content_type=ContentType.objects.get_for_model(Sample),
            object_id=self.sample.pk,
        )
        self.assertEqual(events.count(), 1)

    def test_failure_between_save_model_and_save_related_cleans_up(self):
        """An exception after the owned child is persisted but before
        ``save_related`` closes the manually opened parent boundary must
        roll back everything and leave no boundary state behind."""
        revision_before = self.sample.content_revision
        event_ct = ContentType.objects.get_for_model(Sample)
        post = {
            "name": "Orphaned composition",
            "sample": str(self.sample.pk),
            "group": str(self.group.pk),
            "order": "20",
            "_save": "Save",
        }
        self.client.force_login(self.owner)
        self.client.raise_request_exception = False
        with (
            self.assertLogs("django.request", level="ERROR") as logged,
            patch(
                "django.contrib.admin.options.ModelAdmin.save_related",
                autospec=True,
                side_effect=RuntimeError("injected save_related failure"),
            ),
        ):
            response = self.client.post(
                reverse("admin:materials_composition_add"), post
            )
        self.assertEqual(response.status_code, 500)
        self.assertIn("injected save_related failure", "\n".join(logged.output))
        self.assertFalse(
            Composition.objects.filter(name="Orphaned composition").exists()
        )
        self.sample.refresh_from_db()
        self.assertEqual(self.sample.content_revision, revision_before)
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=event_ct, object_id=self.sample.pk
            ).exists()
        )
        self.assertFalse(_ACTIVE_MUTATION_ROOTS.get())

        # The next request reuses a fresh boundary: exactly one parent
        # revision and one audit event, and no leftover state.
        response = self.client.post(
            reverse("admin:materials_composition_add"),
            {**post, "name": "Recovered composition"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Composition.objects.filter(name="Recovered composition").exists()
        )
        self.sample.refresh_from_db()
        self.assertEqual(self.sample.content_revision, revision_before + 1)
        self.assertEqual(
            ReviewAction.objects.filter(
                content_type=event_ct, object_id=self.sample.pk
            ).count(),
            1,
        )
        self.assertFalse(_ACTIVE_MUTATION_ROOTS.get())

    def test_parent_field_readonly_only_when_persisted(self):
        """Structural parent fields stay editable on the create form and
        become read-only once the row is persisted; server metadata is
        read-only through the declared ``policy_metadata_readonly``."""
        model_admin = admin.site._registry[Composition]
        request = RequestFactory().get("/admin/")
        request.user = self.owner
        unsaved = model_admin.get_readonly_fields(request, Composition())
        self.assertNotIn("sample", unsaved)
        persisted = model_admin.get_readonly_fields(request, self.composition)
        self.assertIn("sample", persisted)
        for field in model_admin.policy_metadata_readonly:
            with self.subTest(field=field):
                try:
                    Composition._meta.get_field(field)
                except FieldDoesNotExist:
                    continue
                self.assertIn(field, persisted)

    def test_add_form_offered_only_with_editable_parent(self):
        model_admin = admin.site._registry[Composition]
        request = RequestFactory().get("/admin/")
        request.user = self.owner
        self.assertTrue(model_admin.has_add_permission(request))
        request.user = User.objects.create_user(
            username="owned-no-roots", is_staff=True
        )
        self.assertFalse(model_admin.has_add_permission(request))
        inactive = User.objects.create_user(
            username="owned-inactive", is_staff=True, is_active=False
        )
        request.user = inactive
        self.assertFalse(model_admin.has_add_permission(request))

    def test_foreign_parent_add_denied_without_rows(self):
        self.client.force_login(self.stranger)
        response = self.client.post(
            reverse("admin:materials_composition_add"),
            {
                "name": "Admin composition",
                "sample": str(self.sample.pk),
                "group": str(self.group.pk),
                "order": "20",
                "_save": "Save",
            },
        )
        self.assertNotEqual(response.status_code, 302)
        self.assertFalse(
            Composition.objects.filter(
                sample=self.sample, name="Admin composition"
            ).exists()
        )

    def test_frozen_parent_add_denied(self):
        revision_before = self.archived_sample.content_revision
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("admin:materials_composition_add"),
            {
                "name": "Frozen composition",
                "sample": str(self.archived_sample.pk),
                "group": str(self.group.pk),
                "order": "20",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            Composition.objects.filter(
                sample=self.archived_sample, name="Frozen composition"
            ).exists()
        )
        self.archived_sample.refresh_from_db()
        self.assertEqual(self.archived_sample.content_revision, revision_before)

    def test_forged_reparent_rejected_without_revision(self):
        revision_before = self.sample.content_revision
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("admin:materials_composition_change", args=[self.composition.pk]),
            {
                "name": "Reparented",
                "sample": str(self.foreign_sample.pk),
                "group": str(self.group.pk),
                "order": "10",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.composition.refresh_from_db()
        self.assertEqual(self.composition.sample_id, self.sample.pk)
        self.sample.refresh_from_db()
        self.assertEqual(self.sample.content_revision, revision_before)
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(Sample),
                object_id=self.sample.pk,
            ).exists()
        )

    def test_same_parent_value_is_not_forged(self):
        owner_before = self.composition.owner_id
        status_before = self.composition.publication_status
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("admin:materials_composition_change", args=[self.composition.pk]),
            {
                "name": "Still same parent",
                "sample": str(self.sample.pk),
                "group": str(self.group.pk),
                "order": "30",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.composition.refresh_from_db()
        self.assertEqual(self.composition.name, "Still same parent")
        self.assertEqual(self.composition.sample_id, self.sample.pk)
        # Updates never reassign server-owned metadata.
        self.assertEqual(self.composition.owner_id, owner_before)
        self.assertEqual(self.composition.publication_status, status_before)


class IndependentEvidenceAdminTests(TestCase):
    """Standalone evidence creates validate every declared parent from
    cleaned data, including M2M parent sets."""

    @classmethod
    def setUpTestData(cls):
        default_owner = ensure_test_default_owner()
        Unit.objects.get_or_create(name="No unit", owner=default_owner)
        cls.owner = User.objects.create_user(username="acpv-owner", is_staff=True)
        cls.editor = User.objects.create_user(username="acpv-editor", is_staff=True)
        cls.editor.user_permissions.add(
            _perm(
                AggregatedCollectionPropertyValue,
                "add_aggregatedcollectionpropertyvalue",
            ),
            _perm(
                AggregatedCollectionPropertyValue,
                "change_aggregatedcollectionpropertyvalue",
            ),
        )
        cls.property = Property.objects.create(
            name="ACPV admin property", publication_status="published"
        )
        cls.unit = Unit.objects.create(
            name="ACPV admin unit", publication_status="published"
        )
        cls.catchment = CollectionCatchment.objects.create(
            name="ACPV Catchment", publication_status="published"
        )
        cls.system = CollectionSystem.objects.create(
            name="ACPV System", publication_status="published"
        )
        cls.category = WasteCategory.objects.create(
            name="ACPV Category", publication_status="published"
        )
        cls.archived_collection = Collection.objects.create(
            name="ACPV archived",
            owner=cls.owner,
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_category=cls.category,
            publication_status="archived",
        )
        cls.private_collection = Collection.objects.create(
            name="ACPV private foreign",
            owner=cls.owner,
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_category=cls.category,
            publication_status="private",
        )

    def _add_post(self, *collections):
        return {
            "name": "ACPV admin row",
            "collections": [str(collection.pk) for collection in collections],
            "property": str(self.property.pk),
            "unit": str(self.unit.pk),
            "average": "12.5",
            "year": "2024",
            "_save": "Save",
        }

    def test_add_to_public_archived_parent_allowed(self):
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse("admin:waste_collection_aggregatedcollectionpropertyvalue_add"),
            self._add_post(self.archived_collection),
        )
        self.assertEqual(response.status_code, 302)
        acpv = AggregatedCollectionPropertyValue.objects.get(name="ACPV admin row")
        self.assertEqual(acpv.owner_id, self.editor.pk)
        self.assertEqual(acpv.publication_status, "private")
        self.assertEqual(list(acpv.collections.all()), [self.archived_collection])
        event = ReviewAction.objects.get(
            content_type=ContentType.objects.get_for_model(
                AggregatedCollectionPropertyValue
            ),
            object_id=acpv.pk,
            action=ReviewAction.ACTION_CREATED,
        )
        self.assertEqual(event.user_id, self.editor.pk)

    def test_forged_m2m_reparent_rejected(self):
        acpv = AggregatedCollectionPropertyValue.objects.create(
            name="ACPV forged reparent",
            owner=self.editor,
            property=self.property,
            unit=self.unit,
            average=5.0,
            year=2024,
        )
        acpv.collections.set([self.archived_collection])
        revision_before = acpv.content_revision
        # The M2M parent relation is read-only on the persisted row; a
        # forged POSTed parent set must be rejected, not silently ignored.
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse(
                "admin:waste_collection_aggregatedcollectionpropertyvalue_change",
                args=[acpv.pk],
            ),
            {
                "name": "ACPV forged reparent",
                "collections": [str(self.private_collection.pk)],
                "property": str(self.property.pk),
                "unit": str(self.unit.pk),
                "average": "5.0",
                "year": "2024",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 403)
        acpv.refresh_from_db()
        self.assertEqual(list(acpv.collections.all()), [self.archived_collection])
        self.assertEqual(acpv.content_revision, revision_before)

    def test_foreign_private_parent_in_m2m_rejects_without_rows(self):
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse("admin:waste_collection_aggregatedcollectionpropertyvalue_add"),
            self._add_post(self.archived_collection, self.private_collection),
        )
        # Rejection happens either at formfield scoping (200 with errors)
        # or at the persistence-time policy check (403) — never persisted.
        self.assertNotEqual(response.status_code, 302)
        self.assertFalse(
            AggregatedCollectionPropertyValue.objects.filter(
                name="ACPV admin row"
            ).exists()
        )
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(
                    AggregatedCollectionPropertyValue
                ),
                action=ReviewAction.ACTION_CREATED,
            ).exists()
        )


class NonUcoOwnedAdminTests(TestCase):
    """Plain-model owned children (no UserCreatedObject base) cannot bypass
    their root through standalone admin write paths."""

    @classmethod
    def setUpTestData(cls):
        default_owner = ensure_test_default_owner()
        Unit.objects.get_or_create(name="No unit", owner=default_owner)
        cls.owner = User.objects.create_user(username="sic-owner", is_staff=True)
        cls.owner.user_permissions.add(
            _perm(Scenario, "change_scenario"),
            _perm(
                ScenarioInventoryConfiguration,
                "change_scenarioinventoryconfiguration",
            ),
            _perm(
                ScenarioInventoryConfiguration,
                "delete_scenarioinventoryconfiguration",
            ),
        )
        cls.stranger = User.objects.create_user(username="sic-stranger", is_staff=True)
        # Even with every stock model permission (including the root's own
        # change permission), a foreign root cannot be bypassed.
        cls.stranger.user_permissions.add(
            _perm(Scenario, "change_scenario"),
            _perm(Scenario, "delete_scenario"),
            _perm(
                ScenarioInventoryConfiguration,
                "change_scenarioinventoryconfiguration",
            ),
            _perm(
                ScenarioInventoryConfiguration,
                "delete_scenarioinventoryconfiguration",
            ),
        )
        cls.region = Region.objects.create(
            name="SIC region", country="DE", publication_status="published"
        )
        cls.dataset = GeoDataset.objects.create(
            name="SIC dataset",
            owner=cls.owner,
            region=cls.region,
            publication_status="published",
        )
        cls.algorithm = InventoryAlgorithm.objects.create(
            name="SIC algo", geodataset=cls.dataset
        )
        cls.material = Material.objects.create(name="SIC material", owner=cls.owner)
        cls.parameter = InventoryAlgorithmParameter.objects.create(
            descriptive_name="SIC parameter", short_name="sic_param"
        )
        cls.value = InventoryAlgorithmParameterValue.objects.create(
            name="SIC value", parameter=cls.parameter, value=1.0
        )
        # Published so the row is publicly readable — the denial below must
        # come from authorization, not invisibility.
        cls.scenario = Scenario.objects.create(
            name="SIC scenario",
            owner=cls.owner,
            publication_status="published",
        )
        cls.archived_scenario = Scenario.objects.create(
            name="SIC archived scenario",
            owner=cls.owner,
            publication_status="archived",
        )
        cls.config = ScenarioInventoryConfiguration.objects.create(
            scenario=cls.scenario,
            geodataset=cls.dataset,
            inventory_algorithm=cls.algorithm,
        )
        cls.frozen_config = ScenarioInventoryConfiguration.objects.create(
            scenario=cls.archived_scenario,
            geodataset=cls.dataset,
            inventory_algorithm=cls.algorithm,
        )

    def _config_post(self, scenario):
        return {
            "scenario": str(scenario.pk),
            "feedstock": str(self.material.pk),
            "geodataset": str(self.dataset.pk),
            "inventory_algorithm": str(self.algorithm.pk),
            "inventory_parameter": str(self.parameter.pk),
            "inventory_value": str(self.value.pk),
            "_save": "Save",
        }

    def test_stranger_cannot_edit_config_on_foreign_root(self):
        self.client.force_login(self.stranger)
        response = self.client.post(
            reverse(
                "admin:inventories_scenarioinventoryconfiguration_change",
                args=[self.config.pk],
            ),
            self._config_post(self.scenario),
        )
        self.assertEqual(response.status_code, 403)

    def test_owner_cannot_edit_config_on_frozen_root(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse(
                "admin:inventories_scenarioinventoryconfiguration_change",
                args=[self.frozen_config.pk],
            ),
            self._config_post(self.archived_scenario),
        )
        self.assertEqual(response.status_code, 403)
        self.frozen_config.refresh_from_db()
        self.assertEqual(self.frozen_config.scenario_id, self.archived_scenario.pk)

    def test_stranger_cannot_delete_config_on_foreign_root(self):
        self.client.force_login(self.stranger)
        response = self.client.post(
            reverse(
                "admin:inventories_scenarioinventoryconfiguration_delete",
                args=[self.config.pk],
            ),
            {"post": "yes"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            ScenarioInventoryConfiguration.objects.filter(pk=self.config.pk).exists()
        )


class GeoDatasetConfigAdminTests(TestCase):
    """Runtime relation/column configuration additionally requires explicit
    application administration — dataset edit capability alone is never
    enough, and a frozen parent denies even administrators."""

    @classmethod
    def setUpTestData(cls):
        default_owner = ensure_test_default_owner()
        Unit.objects.get_or_create(name="No unit", owner=default_owner)
        cls.owner = User.objects.create_user(username="cfg-owner", is_staff=True)
        cls.owner.user_permissions.add(_perm(GeoDataset, "change_geodataset"))
        cls.owner.user_permissions.add(
            _perm(
                GeoDatasetRuntimeConfiguration,
                "change_geodatasetruntimeconfiguration",
            ),
            _perm(
                GeoDatasetRuntimeConfiguration,
                "add_geodatasetruntimeconfiguration",
            ),
            _perm(GeoDatasetColumnPolicy, "add_geodatasetcolumnpolicy"),
            _perm(GeoDatasetColumnPolicy, "change_geodatasetcolumnpolicy"),
        )
        cls.administrator = User.objects.create_user(
            username="cfg-admin", is_staff=True
        )
        cls.administrator.user_permissions.add(
            _perm(GeoDataset, "change_geodataset"),
            _perm(
                GeoDatasetRuntimeConfiguration,
                "change_geodatasetruntimeconfiguration",
            ),
            _perm(
                GeoDatasetRuntimeConfiguration,
                "add_geodatasetruntimeconfiguration",
            ),
        )
        administer, _ = Permission.objects.get_or_create(
            codename="administer_objects",
            content_type=ContentType.objects.get_for_model(ReviewAction),
            defaults={"name": "Can administer objects"},
        )
        cls.administrator.user_permissions.add(administer)

        cls.region = Region.objects.create(
            name="CFG region", country="DE", publication_status="published"
        )
        cls.map_source = Source.objects.create(
            title="CFG source", type="misc", owner=cls.owner
        )
        cls.map_config = MapConfiguration.objects.create(
            name="CFG map", owner=cls.owner
        )
        # The changeform POSTs the stored relation values so a legitimate
        # post is a no-op on the parent's own fields.
        cls.dataset = GeoDataset.objects.create(
            name="CFG dataset",
            description="",
            owner=cls.owner,
            region=cls.region,
            data_content_type=ContentType.objects.get_for_model(Region),
            data_object_id=cls.region.pk,
            map_configuration=cls.map_config,
        )
        cls.dataset.sources.set([cls.map_source])
        cls.published_dataset = GeoDataset.objects.create(
            name="CFG published",
            owner=cls.owner,
            region=cls.region,
            publication_status="published",
        )
        cls.other_dataset = GeoDataset.objects.create(
            name="CFG other", owner=cls.owner, region=cls.region
        )
        cls.config = GeoDatasetRuntimeConfiguration.objects.create(
            dataset=cls.dataset, backend_type="local_relation"
        )
        cls.frozen_config = GeoDatasetRuntimeConfiguration.objects.create(
            dataset=cls.published_dataset, backend_type="local_relation"
        )

    def _dataset_changeform_post(self):
        return {
            "name": self.dataset.name,
            "region": str(self.region.pk),
            "sources": [str(self.map_source.pk)],
            "data_content_type": str(ContentType.objects.get_for_model(Region).pk),
            "data_object_id": str(self.region.pk),
            "map_configuration": str(self.map_config.pk),
            "runtime_configuration-TOTAL_FORMS": "1",
            "runtime_configuration-INITIAL_FORMS": "1",
            "runtime_configuration-MIN_NUM_FORMS": "0",
            "runtime_configuration-MAX_NUM_FORMS": "1",
            "runtime_configuration-0-id": str(self.config.pk),
            "runtime_configuration-0-backend_type": "legacy_model",
            "column_policies-TOTAL_FORMS": "1",
            "column_policies-INITIAL_FORMS": "0",
            "column_policies-MIN_NUM_FORMS": "0",
            "column_policies-MAX_NUM_FORMS": "1000",
            "column_policies-0-column_name": "geom",
            "_save": "Save",
        }

    def test_forged_config_inline_rows_denied_for_dataset_owner(self):
        """An ordinary dataset owner cannot write configuration rows
        through the real parent changeform, even with all stock child CRUD
        permissions.

        The mixin's ``has_*`` predicates already exclude the inline at
        render level; forcing them open proves the persistence-time
        ``authorize_formset`` gate still rejects the forged rows."""
        revision_before = self.dataset.content_revision
        self.client.force_login(self.owner)
        admitted = [
            patch.object(
                inline_class,
                permission,
                autospec=True,
                return_value=True,
            )
            for inline_class in (
                GeoDatasetRuntimeConfigurationInline,
                GeoDatasetColumnPolicyInline,
            )
            for permission in (
                "has_add_permission",
                "has_change_permission",
                "has_delete_permission",
            )
        ]
        with (
            admitted[0],
            admitted[1],
            admitted[2],
            admitted[3],
            admitted[4],
            admitted[5],
        ):
            response = self.client.post(
                reverse("admin:maps_geodataset_change", args=[self.dataset.pk]),
                self._dataset_changeform_post(),
            )
        self.assertEqual(response.status_code, 403)
        self.config.refresh_from_db()
        self.assertEqual(self.config.backend_type, "local_relation")
        self.assertFalse(
            GeoDatasetColumnPolicy.objects.filter(dataset=self.dataset).exists()
        )
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.content_revision, revision_before)

    def test_owner_forged_inline_rows_excluded_without_admission(self):
        """Without patched admission the mixin's ``has_*`` predicates
        exclude both configuration inlines from the owner's changeform, so
        forged management data is ignored entirely."""
        revision_before = self.dataset.content_revision
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("admin:maps_geodataset_change", args=[self.dataset.pk]),
            self._dataset_changeform_post(),
        )
        self.assertEqual(response.status_code, 302)
        self.config.refresh_from_db()
        self.assertEqual(self.config.backend_type, "local_relation")
        self.assertFalse(
            GeoDatasetColumnPolicy.objects.filter(dataset=self.dataset).exists()
        )
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.content_revision, revision_before)

    def test_administrator_writes_config_inline_rows_once(self):
        revision_before = self.dataset.content_revision
        self.client.force_login(self.administrator)
        response = self.client.post(
            reverse("admin:maps_geodataset_change", args=[self.dataset.pk]),
            self._dataset_changeform_post(),
        )
        self.assertEqual(response.status_code, 302)
        self.config.refresh_from_db()
        self.assertEqual(self.config.backend_type, "legacy_model")
        self.assertEqual(
            GeoDatasetColumnPolicy.objects.filter(dataset=self.dataset).count(),
            1,
        )
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.content_revision, revision_before + 1)
        self.assertEqual(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(GeoDataset),
                object_id=self.dataset.pk,
            ).count(),
            1,
        )

    def test_dataset_owner_cannot_write_config(self):
        self.client.force_login(self.owner)
        add_response = self.client.post(
            reverse("admin:maps_geodatasetruntimeconfiguration_add"),
            {
                "dataset": str(self.dataset.pk),
                "backend_type": "local_relation",
                "_save": "Save",
            },
        )
        self.assertEqual(add_response.status_code, 403)
        change_response = self.client.post(
            reverse(
                "admin:maps_geodatasetruntimeconfiguration_change",
                args=[self.config.pk],
            ),
            {
                "dataset": str(self.dataset.pk),
                "backend_type": "legacy_model",
                "_save": "Save",
            },
        )
        self.assertEqual(change_response.status_code, 403)
        self.config.refresh_from_db()
        self.assertEqual(self.config.backend_type, "local_relation")
        column_response = self.client.post(
            reverse("admin:maps_geodatasetcolumnpolicy_add"),
            {
                "dataset": str(self.dataset.pk),
                "column_name": "geom",
                "_save": "Save",
            },
        )
        self.assertEqual(column_response.status_code, 403)
        self.assertFalse(
            GeoDatasetColumnPolicy.objects.filter(dataset=self.dataset).exists()
        )

    def test_administrator_writes_config_with_single_parent_audit(self):
        revision_before = self.dataset.content_revision
        self.client.force_login(self.administrator)
        response = self.client.post(
            reverse(
                "admin:maps_geodatasetruntimeconfiguration_change",
                args=[self.config.pk],
            ),
            {
                "dataset": str(self.dataset.pk),
                "backend_type": "legacy_model",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.config.refresh_from_db()
        self.assertEqual(self.config.backend_type, "legacy_model")
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.content_revision, revision_before + 1)
        events = ReviewAction.objects.filter(
            content_type=ContentType.objects.get_for_model(GeoDataset),
            object_id=self.dataset.pk,
        )
        self.assertEqual(events.count(), 1)

    def test_administrator_only_flag_constrains_class_level_verbs(self):
        """The narrowing applies before the ``obj=None`` list fallback:
        ordinary owners get no class-level change/delete admission while
        administrators still cannot write frozen parents."""
        model_admin = admin.site._registry[GeoDatasetRuntimeConfiguration]
        request = RequestFactory().get("/admin/")
        request.user = self.owner
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
        self.assertFalse(model_admin.has_change_permission(request, self.config))
        request.user = self.administrator
        self.assertTrue(model_admin.has_change_permission(request))
        self.assertTrue(model_admin.has_change_permission(request, self.config))
        self.assertFalse(model_admin.has_change_permission(request, self.frozen_config))

    def test_frozen_parent_denies_administrator(self):
        self.client.force_login(self.administrator)
        response = self.client.post(
            reverse(
                "admin:maps_geodatasetruntimeconfiguration_change",
                args=[self.frozen_config.pk],
            ),
            {
                "dataset": str(self.published_dataset.pk),
                "backend_type": "legacy_model",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.frozen_config.refresh_from_db()
        self.assertEqual(self.frozen_config.backend_type, "local_relation")

    def test_forged_dataset_change_rejected(self):
        revision_before = self.dataset.content_revision
        self.client.force_login(self.administrator)
        response = self.client.post(
            reverse(
                "admin:maps_geodatasetruntimeconfiguration_change",
                args=[self.config.pk],
            ),
            {
                "dataset": str(self.other_dataset.pk),
                "backend_type": "local_relation",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.config.refresh_from_db()
        self.assertEqual(self.config.dataset_id, self.dataset.pk)
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.content_revision, revision_before)

    def test_config_audit_failure_rolls_back_row_and_parent(self):
        revision_before = self.dataset.content_revision
        self.client.force_login(self.administrator)
        self.client.raise_request_exception = False
        with (
            self.assertLogs("django.request", level="ERROR") as logged,
            patch(
                "utils.object_management.services._record_event",
                side_effect=RuntimeError("audit transport failed"),
            ),
        ):
            response = self.client.post(
                reverse(
                    "admin:maps_geodatasetruntimeconfiguration_change",
                    args=[self.config.pk],
                ),
                {
                    "dataset": str(self.dataset.pk),
                    "backend_type": "legacy_model",
                    "_save": "Save",
                },
            )
        self.assertEqual(response.status_code, 500)
        self.assertIn("audit transport failed", "\n".join(logged.output))
        self.config.refresh_from_db()
        self.assertEqual(self.config.backend_type, "local_relation")
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.content_revision, revision_before)

    def test_config_inlines_follow_the_same_boundary(self):
        model_admin = admin.site._registry[GeoDataset]
        inlines = {
            inline.model: inline(GeoDataset, admin.site)
            for inline in model_admin.inlines
        }
        factory = RequestFactory()
        request = factory.get("/admin/")
        request.user = self.owner
        for inline in inlines.values():
            with self.subTest(inline=type(inline).__name__):
                self.assertFalse(inline.has_add_permission(request, self.dataset))
                self.assertFalse(inline.has_change_permission(request, self.dataset))
        request.user = self.administrator
        for inline in inlines.values():
            with self.subTest(inline=type(inline).__name__):
                self.assertTrue(inline.has_add_permission(request, self.dataset))
                self.assertFalse(
                    inline.has_add_permission(request, self.published_dataset)
                )

    def test_root_m2m_and_two_inline_changes_share_one_revision(self):
        extra = Source.objects.create(
            owner=self.administrator, title="Extra source", type="misc"
        )
        payload = self._dataset_changeform_post()
        payload["name"] = "Compound change"
        payload["sources"] = [str(self.map_source.pk), str(extra.pk)]
        self.client.force_login(self.administrator)
        response = self.client.post(
            reverse("admin:maps_geodataset_change", args=[self.dataset.pk]),
            payload,
        )
        self.assertEqual(response.status_code, 302)
        self.dataset.refresh_from_db()
        self.config.refresh_from_db()
        self.assertEqual(self.dataset.name, "Compound change")
        self.assertCountEqual(self.dataset.sources.all(), [self.map_source, extra])
        self.assertEqual(self.config.backend_type, "legacy_model")
        self.assertEqual(self.dataset.column_policies.count(), 1)
        self.assertEqual(self.dataset.content_revision, 2)
        events = ReviewAction.objects.filter(
            content_type=ContentType.objects.get_for_model(GeoDataset),
            object_id=self.dataset.pk,
        )
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.get().action, "edited")
        self.assertEqual(events.get().content_revision, 2)

    def test_compound_audit_failure_rolls_back_scalar_m2m_and_both_inlines(self):
        extra = Source.objects.create(
            owner=self.administrator, title="Extra source", type="misc"
        )
        before_name = self.dataset.name
        payload = self._dataset_changeform_post()
        payload["name"] = "Must roll back"
        payload["sources"] = [str(extra.pk)]
        self.client.force_login(self.administrator)
        self.client.raise_request_exception = False
        with (
            patch(
                "utils.object_management.services._record_event",
                side_effect=RuntimeError("compound audit unavailable"),
            ),
            self.assertLogs("django.request", level="ERROR") as logged,
        ):
            response = self.client.post(
                reverse("admin:maps_geodataset_change", args=[self.dataset.pk]),
                payload,
            )
        self.assertEqual(response.status_code, 500)
        self.assertIn("compound audit unavailable", "\n".join(logged.output))
        self.dataset.refresh_from_db()
        self.config.refresh_from_db()
        self.assertEqual(self.dataset.name, before_name)
        self.assertEqual(list(self.dataset.sources.all()), [self.map_source])
        self.assertEqual(self.config.backend_type, "local_relation")
        self.assertFalse(self.dataset.column_policies.exists())
        self.assertEqual(self.dataset.content_revision, 1)
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(GeoDataset),
                object_id=self.dataset.pk,
            ).exists()
        )
