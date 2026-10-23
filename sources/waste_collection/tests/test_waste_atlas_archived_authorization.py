from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse, reverse_lazy
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, APITestCase

from maps.models import CatchmentRevision, GeoPolygon, Region
from maps.utils import get_or_set_cache
from sources.waste_collection.models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionCatchment,
    CollectionPropertyValue,
    CollectionSystem,
    WasteCategory,
)
from sources.waste_collection.waste_atlas.viewsets import (
    _collection_qs,
    _map_aggregated_property_value_q,
    _property_value_q,
    _revision_q,
    _supporting_queryset,
)
from utils.object_management.models import ReviewAction
from utils.object_management.policy import (
    PUBLIC_READ_STATES,
    decide,
    is_admin,
)
from utils.properties.models import Property, Unit


def _request(user, scope=None):
    params = {} if scope is None else {"scope": scope}
    request = Request(APIRequestFactory().get("/waste-atlas/", params))
    request.user = user
    return request


def _pk_set(queryset):
    return set(queryset.values_list("pk", flat=True))


class AtlasArchivedScopeTests(TestCase):
    """Shared-visibility Atlas scopes with public historical archives."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("atlas-owner")
        cls.other_owner = User.objects.create_user("atlas-other")
        cls.regular = User.objects.create_user("atlas-regular")
        cls.staff = User.objects.create_user("atlas-staff", is_staff=True)
        cls.inactive = User.objects.create_user("atlas-inactive", is_active=False)
        cls.moderator = User.objects.create_user("atlas-mod")
        cls.cpv_moderator = User.objects.create_user("atlas-cpv-mod")
        cls.revision_moderator = User.objects.create_user("atlas-rev-mod")
        cls.administrator = User.objects.create_user("atlas-admin")
        cls.anonymous = AnonymousUser()

        collection_ct = ContentType.objects.get_for_model(Collection)
        cpv_ct = ContentType.objects.get_for_model(CollectionPropertyValue)
        revision_ct = ContentType.objects.get_for_model(CatchmentRevision)
        cls.moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_collection", content_type=collection_ct
            )
        )
        cls.cpv_moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_collectionpropertyvalue",
                content_type=cpv_ct,
            )
        )
        cls.revision_moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_catchmentrevision",
                content_type=revision_ct,
            )
        )
        administer_permission, _ = Permission.objects.get_or_create(
            codename="administer_objects",
            content_type=ContentType.objects.get_for_model(ReviewAction),
            defaults={"name": "Can administer objects"},
        )
        cls.administrator.user_permissions.add(administer_permission)

        cls.system = CollectionSystem.objects.create(
            name="Atlas Scope System", publication_status="published"
        )
        cls.category = WasteCategory.objects.create(
            name="Atlas Scope Category", publication_status="published"
        )

        cls.catchments = {}
        cls.collections = {}
        for status, valid_from, owner in (
            ("published", date(2024, 1, 1), cls.owner),
            ("archived", date(2022, 1, 1), cls.owner),
            ("private", date(2024, 1, 1), cls.owner),
            ("review", date(2024, 1, 1), cls.owner),
            ("declined", date(2024, 1, 1), cls.owner),
            ("foreign_private", date(2024, 1, 1), cls.other_owner),
        ):
            catchment = CollectionCatchment.objects.create(
                name=f"Atlas {status} catchment",
                region=Region.objects.create(
                    name=f"Atlas {status} region",
                    country="DE",
                    borders=GeoPolygon.objects.create(
                        geom="MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))"
                    ),
                ),
                publication_status="published",
            )
            cls.catchments[status] = catchment
            cls.collections[status] = Collection.objects.create(
                name=f"Atlas {status} collection",
                owner=owner,
                catchment=catchment,
                collection_system=cls.system,
                waste_category=cls.category,
                valid_from=valid_from,
                publication_status=status if status != "foreign_private" else "private",
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

    def _public_historical(self):
        return {
            self.collections["published"].pk,
            self.collections["archived"].pk,
        }

    def test_public_read_states_matches_public_visible(self):
        from sources.waste_collection.waste_atlas.viewsets import _PUBLIC_VISIBLE

        self.assertEqual(_PUBLIC_VISIBLE, PUBLIC_READ_STATES)

    def test_default_scope_is_public_historical_for_every_actor(self):
        expected = self._public_historical()
        for persona, user in self._personas().items():
            with self.subTest(persona=persona):
                self.assertEqual(_pk_set(_collection_qs(_request(user))), expected)
                self.assertEqual(
                    _pk_set(_collection_qs(_request(user, "published"))),
                    expected,
                )

    def test_archived_scope_includes_archives_for_public_personas(self):
        expected = {self.collections["archived"].pk}
        for persona in ("anonymous", "inactive", "regular", "staff"):
            with self.subTest(persona=persona):
                ids = _pk_set(
                    _collection_qs(_request(self._personas()[persona], "archived"))
                )
                self.assertEqual(ids, expected)

    def test_unknown_scope_returns_no_records_for_every_actor(self):
        for persona, user in self._personas().items():
            with self.subTest(persona=persona):
                self.assertEqual(
                    _pk_set(_collection_qs(_request(user, "bogus-scope"))),
                    set(),
                )

    def test_explicit_all_is_administrator_only(self):
        admin_ids = _pk_set(_collection_qs(_request(self.administrator, "all")))
        self.assertEqual(
            admin_ids,
            {
                self.collections[s].pk
                for s in (
                    "published",
                    "archived",
                    "private",
                    "review",
                    "declined",
                    "foreign_private",
                )
            },
        )
        for persona in ("anonymous", "inactive", "regular", "staff", "moderator"):
            with self.subTest(persona=persona):
                self.assertEqual(
                    _pk_set(_collection_qs(_request(self._personas()[persona], "all"))),
                    set(),
                )

    def test_admin_default_scope_is_public_historical(self):
        self.assertTrue(is_admin(self.administrator))
        self.assertEqual(
            _pk_set(_collection_qs(_request(self.administrator))),
            self._public_historical(),
        )

    def test_mine_includes_owned_private_and_review_collections(self):
        ids = _pk_set(_collection_qs(_request(self.owner, "mine")))
        self.assertEqual(
            ids,
            {
                self.collections[s].pk
                for s in ("published", "archived", "private", "review", "declined")
            },
        )
        self.assertNotIn(self.collections["foreign_private"].pk, ids)

    def test_mine_includes_direct_and_group_granted_rows(self):
        granted = self.collections["foreign_private"]
        granted.add_editor(self.regular)
        ids = _pk_set(_collection_qs(_request(self.regular, "mine")))
        self.assertIn(granted.pk, ids)
        self.assertNotIn(self.collections["private"].pk, ids)

        group = Group.objects.create(name="atlas-review-editors")
        granted_review = self.collections["review"]
        granted_review.add_editor_group(group)
        member = User.objects.create_user("atlas-group-member")
        member.groups.add(group)

        member_ids = _pk_set(_collection_qs(_request(member, "mine")))
        self.assertIn(granted_review.pk, member_ids)

        member.groups.remove(group)
        # A fresh user instance models the next request: revocation applies
        # immediately, with no shared cache serving stale grants.
        member = User.objects.get(pk=member.pk)
        member_ids = _pk_set(_collection_qs(_request(member, "mine")))
        self.assertNotIn(granted_review.pk, member_ids)

    def test_owned_and_shared_scopes_are_distinct(self):
        shared = self.collections["foreign_private"]
        shared.add_editor(self.owner)
        self.assertEqual(
            _pk_set(_collection_qs(_request(self.owner, "owned"))),
            {
                self.collections[s].pk
                for s in ("published", "archived", "private", "review", "declined")
            },
        )
        self.assertEqual(
            _pk_set(_collection_qs(_request(self.owner, "shared"))),
            {shared.pk},
        )

    def test_collection_moderator_cannot_read_private_or_foreign_review(self):
        ids = _pk_set(_collection_qs(_request(self.moderator, "review")))
        self.assertEqual(ids, {self.collections["review"].pk})
        ids = _pk_set(_collection_qs(_request(self.moderator, "private")))
        self.assertEqual(ids, set())


class AtlasSupportingQuerysetTests(TestCase):
    """Independent evidence keeps its own governance in Atlas queries."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("atlas-sup-owner")
        cls.moderator = User.objects.create_user("atlas-sup-mod")
        cls.cpv_moderator = User.objects.create_user("atlas-sup-cpv-mod")
        cls.revision_moderator = User.objects.create_user("atlas-sup-rev-mod")

        cls.moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_collection",
                content_type=ContentType.objects.get_for_model(Collection),
            )
        )
        cls.cpv_moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_collectionpropertyvalue",
                content_type=ContentType.objects.get_for_model(CollectionPropertyValue),
            )
        )
        cls.revision_moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_catchmentrevision",
                content_type=ContentType.objects.get_for_model(CatchmentRevision),
            )
        )

        cls.system = CollectionSystem.objects.create(
            name="Supporting System", publication_status="published"
        )
        cls.category = WasteCategory.objects.create(
            name="Supporting Category", publication_status="published"
        )
        cls.prop = Property.objects.create(
            name="Supporting prop", publication_status="published"
        )
        cls.unit = Unit.objects.create(
            name="Supporting unit", publication_status="published"
        )
        cls.prop.allowed_units.add(cls.unit)

        cls.catchment = CollectionCatchment.objects.create(
            name="Supporting catchment",
            region=Region.objects.create(
                name="Supporting region",
                country="DE",
                borders=GeoPolygon.objects.create(
                    geom="MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))"
                ),
            ),
            publication_status="published",
        )
        cls.published_collection = Collection.objects.create(
            name="Supporting published collection",
            owner=cls.owner,
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_category=cls.category,
            valid_from=date(2024, 1, 1),
            publication_status="published",
        )
        cls.private_collection = Collection.objects.create(
            name="Supporting private collection",
            owner=cls.owner,
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_category=cls.category,
            valid_from=date(2024, 1, 1),
            publication_status="private",
        )

        cls.public_cpv = CollectionPropertyValue.objects.create(
            collection=cls.published_collection,
            property=cls.prop,
            unit=cls.unit,
            owner=cls.owner,
            year=2024,
            average=1.0,
            publication_status="published",
        )
        cls.archived_cpv = CollectionPropertyValue.objects.create(
            collection=cls.published_collection,
            property=cls.prop,
            unit=cls.unit,
            owner=cls.owner,
            year=2023,
            average=2.0,
            publication_status="archived",
        )
        cls.review_cpv = CollectionPropertyValue.objects.create(
            collection=cls.published_collection,
            property=cls.prop,
            unit=cls.unit,
            owner=cls.owner,
            year=2025,
            average=3.0,
            publication_status="review",
        )
        cls.private_cpv = CollectionPropertyValue.objects.create(
            collection=cls.private_collection,
            property=cls.prop,
            unit=cls.unit,
            owner=cls.owner,
            year=2024,
            average=4.0,
            publication_status="private",
        )

        cls.public_acpv = AggregatedCollectionPropertyValue.objects.create(
            property=cls.prop,
            unit=cls.unit,
            owner=cls.owner,
            year=2024,
            average=5.0,
            publication_status="published",
        )
        cls.public_acpv.collections.add(cls.published_collection)
        cls.archived_acpv = AggregatedCollectionPropertyValue.objects.create(
            property=cls.prop,
            unit=cls.unit,
            owner=cls.owner,
            year=2022,
            average=6.0,
            publication_status="archived",
        )
        cls.archived_acpv.collections.add(cls.published_collection)
        cls.review_acpv = AggregatedCollectionPropertyValue.objects.create(
            property=cls.prop,
            unit=cls.unit,
            owner=cls.owner,
            year=2025,
            average=7.0,
            publication_status="review",
        )
        cls.review_acpv.collections.add(cls.published_collection)
        cls.private_acpv = AggregatedCollectionPropertyValue.objects.create(
            property=cls.prop,
            unit=cls.unit,
            owner=cls.owner,
            year=2026,
            average=8.0,
            publication_status="private",
        )
        cls.private_acpv.collections.add(cls.private_collection)
        cls.acpv_moderator = User.objects.create_user("atlas-sup-acpv-mod")
        cls.acpv_moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_aggregatedcollectionpropertyvalue",
                content_type=ContentType.objects.get_for_model(
                    AggregatedCollectionPropertyValue
                ),
            )
        )

        cls.published_revision = CatchmentRevision.objects.create(
            catchment=cls.catchment,
            name="Published revision",
            geom="MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))",
            effective_from=date(2010, 1, 1),
            effective_to=date(2020, 1, 1),
            publication_status="published",
        )
        cls.archived_revision = CatchmentRevision.objects.create(
            catchment=cls.catchment,
            name="Archived revision",
            geom="MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))",
            effective_from=date(2020, 1, 1),
            effective_to=date(2030, 1, 1),
            publication_status="archived",
        )
        cls.private_revision = CatchmentRevision.objects.create(
            catchment=cls.catchment,
            name="Foreign private revision",
            owner=cls.owner,
            geom="MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))",
            effective_from=date(2030, 1, 1),
            publication_status="private",
        )
        cls.review_revision = CatchmentRevision.objects.create(
            catchment=cls.catchment,
            name="Review revision",
            owner=cls.owner,
            geom="MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))",
            effective_from=date(2040, 1, 1),
            publication_status="review",
        )

    def test_property_values_default_public_historical(self):
        ids = _pk_set(
            CollectionPropertyValue.objects.filter(
                _property_value_q(_request(AnonymousUser()))
            )
        )
        self.assertEqual(ids, {self.public_cpv.pk, self.archived_cpv.pk})

    def test_mine_scope_exposes_owned_private_evidence(self):
        ids = _pk_set(
            CollectionPropertyValue.objects.filter(
                _property_value_q(_request(self.owner, "mine"))
            )
        )
        self.assertEqual(
            ids,
            {
                self.public_cpv.pk,
                self.archived_cpv.pk,
                self.review_cpv.pk,
                self.private_cpv.pk,
            },
        )

    def test_collection_moderator_alone_cannot_read_review_evidence(self):
        ids = _pk_set(
            CollectionPropertyValue.objects.filter(
                _property_value_q(_request(self.moderator, "review"))
            )
        )
        self.assertEqual(ids, {self.public_cpv.pk, self.archived_cpv.pk})
        ids = _pk_set(
            CatchmentRevision.objects.filter(
                _revision_q(_request(self.moderator, "review"))
            )
        )
        self.assertEqual(ids, {self.published_revision.pk, self.archived_revision.pk})

    def test_model_moderator_reads_own_review_rows(self):
        ids = _pk_set(
            CollectionPropertyValue.objects.filter(
                _property_value_q(_request(self.cpv_moderator, "review"))
            )
        )
        self.assertEqual(
            ids,
            {self.public_cpv.pk, self.archived_cpv.pk, self.review_cpv.pk},
        )
        ids = _pk_set(
            CatchmentRevision.objects.filter(
                _revision_q(_request(self.revision_moderator, "review"))
            )
        )
        self.assertEqual(
            ids,
            {
                self.published_revision.pk,
                self.archived_revision.pk,
                self.review_revision.pk,
            },
        )

    def test_private_evidence_needs_its_own_access(self):
        ids = _pk_set(
            CollectionPropertyValue.objects.filter(
                _property_value_q(_request(self.moderator, "private"))
            )
        )
        self.assertNotIn(self.private_cpv.pk, ids)
        self.assertNotIn(
            self.private_revision.pk,
            _pk_set(
                CatchmentRevision.objects.filter(
                    _revision_q(_request(self.moderator, "private"))
                )
            ),
        )
        ids = _pk_set(
            CollectionPropertyValue.objects.filter(
                _property_value_q(_request(self.owner, "private"))
            )
        )
        self.assertIn(self.private_cpv.pk, ids)

    def test_supporting_queryset_includes_public_and_scoped_rows(self):
        ids = _pk_set(
            _supporting_queryset(CollectionPropertyValue, _request(self.owner, "mine"))
        )
        self.assertEqual(
            ids,
            {
                self.public_cpv.pk,
                self.archived_cpv.pk,
                self.review_cpv.pk,
                self.private_cpv.pk,
            },
        )
        self.assertEqual(
            _pk_set(
                _supporting_queryset(CollectionPropertyValue, _request(AnonymousUser()))
            ),
            {self.public_cpv.pk, self.archived_cpv.pk},
        )
        self.assertEqual(
            _pk_set(
                _supporting_queryset(
                    CollectionPropertyValue, _request(AnonymousUser(), "bogus")
                )
            ),
            set(),
        )

    def test_aggregated_values_default_public_historical(self):
        ids = _pk_set(
            AggregatedCollectionPropertyValue.objects.filter(
                _map_aggregated_property_value_q(_request(AnonymousUser()))
            )
        )
        self.assertEqual(ids, {self.public_acpv.pk, self.archived_acpv.pk})

    def test_aggregated_values_keep_own_governance(self):
        # Collection moderation alone does not expose ACPV review/private rows.
        ids = _pk_set(
            AggregatedCollectionPropertyValue.objects.filter(
                _map_aggregated_property_value_q(_request(self.moderator, "review"))
            )
        )
        self.assertEqual(ids, {self.public_acpv.pk, self.archived_acpv.pk})
        ids = _pk_set(
            AggregatedCollectionPropertyValue.objects.filter(
                _map_aggregated_property_value_q(_request(self.moderator, "private"))
            )
        )
        self.assertNotIn(self.private_acpv.pk, ids)
        self.assertNotIn(self.review_acpv.pk, ids)

        # The ACPV moderator sees review rows of its own model.
        ids = _pk_set(
            AggregatedCollectionPropertyValue.objects.filter(
                _map_aggregated_property_value_q(
                    _request(self.acpv_moderator, "review")
                )
            )
        )
        self.assertEqual(
            ids,
            {self.public_acpv.pk, self.archived_acpv.pk, self.review_acpv.pk},
        )

        # Owners see their own private ACPV under the workspace scope.
        ids = _pk_set(
            AggregatedCollectionPropertyValue.objects.filter(
                _map_aggregated_property_value_q(_request(self.owner, "mine"))
            )
        )
        self.assertEqual(
            ids,
            {
                self.public_acpv.pk,
                self.archived_acpv.pk,
                self.review_acpv.pk,
                self.private_acpv.pk,
            },
        )

    def test_aggregated_value_selected_collection_join_stays_caller_scoped(
        self,
    ):
        """The helper contributes only ``pk__in``; the caller's M2M selection
        filter decides which collection the rows are joined to."""
        ids = _pk_set(
            AggregatedCollectionPropertyValue.objects.filter(
                _map_aggregated_property_value_q(_request(self.owner, "mine")),
                collections=self.published_collection,
            )
        )
        self.assertEqual(
            ids,
            {self.public_acpv.pk, self.archived_acpv.pk, self.review_acpv.pk},
        )
        ids = _pk_set(
            AggregatedCollectionPropertyValue.objects.filter(
                _map_aggregated_property_value_q(_request(AnonymousUser())),
                collections=self.private_collection,
            )
        )
        # Anonymous callers may join the private collection selection, but the
        # ACPV rows themselves stay public-historical only.
        self.assertEqual(ids, set())


class AtlasArchivedHttpTests(APITestCase):
    """HTTP parity for archives across detail, lists, geojson and exports."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("atlas-http-owner")
        cls.system = CollectionSystem.objects.create(
            name="HTTP System", publication_status="published"
        )
        cls.category = WasteCategory.objects.create(
            name="Biowaste", publication_status="published"
        )
        cls.published_catchment = CollectionCatchment.objects.create(
            name="HTTP published catchment",
            region=Region.objects.create(
                name="HTTP published region",
                country="DE",
                borders=GeoPolygon.objects.create(
                    geom="MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))"
                ),
            ),
            publication_status="published",
        )
        cls.published_collection = Collection.objects.create(
            name="HTTP published collection",
            owner=cls.owner,
            catchment=cls.published_catchment,
            collection_system=cls.system,
            waste_category=cls.category,
            valid_from=date(2024, 1, 1),
            publication_status="published",
        )
        cls.archived_catchment = CollectionCatchment.objects.create(
            name="HTTP archived catchment",
            region=Region.objects.create(
                name="HTTP archived region",
                country="DE",
                borders=GeoPolygon.objects.create(
                    geom="MULTIPOLYGON(((2 2, 2 3, 3 3, 3 2, 2 2)))"
                ),
            ),
            publication_status="published",
        )
        cls.archived_collection = Collection.objects.create(
            name="HTTP archived collection",
            owner=cls.owner,
            catchment=cls.archived_catchment,
            collection_system=cls.system,
            waste_category=cls.category,
            valid_from=date(2022, 1, 1),
            publication_status="archived",
        )

    def test_anonymous_reads_archived_collection_detail(self):
        response = self.client.get(
            reverse("collection-detail", kwargs={"pk": self.archived_collection.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_anonymous_api_retrieve_and_archived_scope_list(self):
        """Public archived read applies to the collection REST API too:
        anonymous retrieve of an archived row succeeds and the archived scope
        list exposes it while active rows stay out."""
        detail_url = reverse(
            "api-waste-collection-detail",
            kwargs={"pk": self.archived_collection.pk},
        )
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.archived_collection.pk)

        response = self.client.get(
            reverse("api-waste-collection-list"), {"scope": "archived"}
        )
        self.assertEqual(response.status_code, 200)
        results = (
            response.data["results"] if "results" in response.data else response.data
        )
        ids = {row["id"] for row in results}
        self.assertIn(self.archived_collection.pk, ids)
        self.assertNotIn(self.published_collection.pk, ids)

        response = self.client.get(
            reverse("api-waste-collection-list"), {"scope": "published"}
        )
        self.assertEqual(response.status_code, 200)
        results = (
            response.data["results"] if "results" in response.data else response.data
        )
        ids = {row["id"] for row in results}
        self.assertIn(self.published_collection.pk, ids)
        self.assertNotIn(self.archived_collection.pk, ids)

    def test_export_view_dispatches_authorized_archived_queryset(self):
        """The owning export view requires an authenticated reader; with the
        Celery worker mocked, the view's own row-count estimate proves the
        dispatched queryset includes the archived row for ``list_type``."""
        user = User.objects.create_user("atlas-export-user")
        self.client.force_login(user)
        with patch(
            "utils.file_export.generic_tasks.export_user_created_object_to_file"
        ) as mock_task:
            mock_task.delay.return_value.task_id = "export-task-id"
            response = self.client.get(
                reverse("collection-export"),
                {"format": "csv", "list_type": "archived"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["task_id"], "export-task-id")
        self.assertEqual(payload["row_count"], 1)
        mock_task.delay.assert_called_once()
        _model_label, _file_format, filter_params, export_context = (
            mock_task.delay.call_args.args
        )
        self.assertEqual(_model_label, "waste_collection.Collection")
        self.assertEqual(export_context["list_type"], "archived")
        self.assertEqual(filter_params.get("publication_status"), ["archived"])

    def test_anonymous_export_decision_matches_read(self):
        self.assertTrue(
            decide(AnonymousUser(), "export", self.archived_collection).allowed
        )

    def test_active_only_list_omits_archives(self):
        self.client.force_login(User.objects.create_user("atlas-list-user"))
        response = self.client.get(reverse("collection-list"), follow=True)
        self.assertEqual(response.status_code, 200)
        listed_ids = {obj.pk for obj in response.context["object_list"]}
        self.assertIn(self.published_collection.pk, listed_ids)
        self.assertNotIn(self.archived_collection.pk, listed_ids)

    def test_historical_year_map_resolves_archived_collection(self):
        response = self.client.get(
            reverse("api-waste-atlas-collection-system-list"),
            {"country": "DE", "year": 2022},
        )
        self.assertEqual(response.status_code, 200)
        ids = {row["catchment_id"] for row in response.data}
        self.assertIn(self.archived_catchment.pk, ids)

        response = self.client.get(
            reverse("api-waste-atlas-collection-system-list"),
            {"country": "DE", "year": 2024},
        )
        ids = {row["catchment_id"] for row in response.data}
        self.assertIn(self.published_catchment.pk, ids)
        self.assertNotIn(self.archived_catchment.pk, ids)

    def test_geojson_includes_archived_catchment_for_historical_year(self):
        response = self.client.get(
            reverse("api-waste-atlas-catchment-geojson"),
            {"country": "DE", "year": 2022},
        )
        self.assertEqual(response.status_code, 200)
        ids = {
            feature["properties"]["catchment_id"]
            for feature in response.data["features"]
        }
        self.assertIn(self.archived_catchment.pk, ids)


class AtlasChangeOverlayCacheTests(APITestCase):
    """Shared overlay cache must never leak grants or scope between actors."""

    endpoint = reverse_lazy("api-waste-atlas-catchment-collection-change-geojson")

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("atlas-cache-user")
        cls.catchment = CollectionCatchment.objects.create(
            name="Cache catchment",
            region=Region.objects.create(
                name="Cache region",
                country="DE",
                borders=GeoPolygon.objects.create(
                    geom="MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))"
                ),
            ),
            publication_status="published",
        )
        cls.system = CollectionSystem.objects.create(
            name="Cache system", publication_status="published"
        )
        cls.category = WasteCategory.objects.create(
            name="Cache category", publication_status="published"
        )
        Collection.objects.create(
            name="Cache collection 2022",
            owner=cls.user,
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_category=cls.category,
            valid_from=date(2022, 1, 1),
            publication_status="published",
        )
        Collection.objects.create(
            name="Cache collection 2024",
            owner=cls.user,
            catchment=cls.catchment,
            collection_system=cls.system,
            waste_category=cls.category,
            valid_from=date(2024, 1, 1),
            publication_status="published",
        )
        cls.other_owner = User.objects.create_user("atlas-cache-other")
        cls.published_from_revision = CatchmentRevision.objects.create(
            catchment=cls.catchment,
            name="From revision",
            geom="MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))",
            effective_from=date(2015, 1, 1),
            effective_to=date(2020, 1, 1),
            publication_status="published",
        )
        cls.published_to_revision = CatchmentRevision.objects.create(
            catchment=cls.catchment,
            name="To revision",
            geom="MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))",
            effective_from=date(2020, 1, 1),
            effective_to=date(2030, 1, 1),
            publication_status="published",
        )
        # A foreign private revision whose window overlaps the to-year and
        # whose later effective_from wins the snapshot ordering while the
        # requesting user holds an editor grant on it.
        cls.private_revision = CatchmentRevision.objects.create(
            catchment=cls.catchment,
            name="Private revision",
            owner=cls.other_owner,
            geom="MULTIPOLYGON(((0 0, 0 2, 2 2, 2 0, 0 0)))",
            effective_from=date(2022, 6, 1),
            effective_to=date(2030, 1, 1),
            publication_status="private",
        )

    def _get(self, **params):
        return self.client.get(
            self.endpoint,
            {
                "country": "DE",
                "from_year": 2022,
                "to_year": 2024,
                **params,
            },
        )

    def test_authenticated_requests_bypass_shared_cache(self):
        self.client.force_login(self.user)
        with patch(
            "sources.waste_collection.waste_atlas.viewsets.get_or_set_cache"
        ) as mock_cache:
            response = self._get()
        self.assertEqual(response.status_code, 200)
        mock_cache.assert_not_called()

    def test_anonymous_requests_use_namespaced_public_cache(self):
        with patch(
            "sources.waste_collection.waste_atlas.viewsets.get_or_set_cache",
            wraps=get_or_set_cache,
        ) as mock_cache:
            response = self._get()
        self.assertEqual(response.status_code, 200)
        mock_cache.assert_called_once()
        cache_key = mock_cache.call_args.args[0]
        self.assertTrue(cache_key.startswith("authz-v1:"))

    @staticmethod
    def _revision_ids(response):
        return {
            feature["properties"]["to_revision_id"]
            for feature in response.data["features"]
        } | {
            feature["properties"]["from_revision_id"]
            for feature in response.data["features"]
        }

    def test_revoked_revision_grant_is_not_served_from_overlay(self):
        """An authenticated overlay recomputes visibility per request: once the
        editor grant on a foreign private revision is revoked, its geometry can
        no longer appear — no shared cache may serve the formerly permitted
        snapshot."""
        self.private_revision.add_editor(self.user)
        self.client.force_login(self.user)
        with patch(
            "sources.waste_collection.waste_atlas.viewsets.get_or_set_cache"
        ) as mock_cache:
            granted = self._get(scope="mine")
        self.assertEqual(granted.status_code, 200)
        mock_cache.assert_not_called()
        self.assertIn(self.private_revision.pk, self._revision_ids(granted))

        self.private_revision.remove_editor(self.user)
        # force_login re-resolves the user per request; refetch models the
        # next-request permission refresh explicitly.
        self.client.force_login(User.objects.get(pk=self.user.pk))
        with patch(
            "sources.waste_collection.waste_atlas.viewsets.get_or_set_cache"
        ) as mock_cache:
            revoked = self._get(scope="mine")
        self.assertEqual(revoked.status_code, 200)
        mock_cache.assert_not_called()
        revision_ids = self._revision_ids(revoked)
        self.assertNotIn(self.private_revision.pk, revision_ids)
        self.assertIn(self.published_to_revision.pk, revision_ids)
