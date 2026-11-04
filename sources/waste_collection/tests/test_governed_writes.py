"""Boundary regressions for the migrated waste_collection domain writers.

Each case pins one ungoverned-write finding to the shared mutation boundary:
denied actors write nothing and bump no revision; allowed writes record the
governed revision bump and audit event. Views whose pattern differs from a
plain save (reparent, cross-object delete, M2M edges) additionally assert the
specific boundary semantics.
"""

import io
from contextlib import redirect_stdout
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db.models import signals
from django.http import QueryDict
from django.test import TestCase
from django.urls import reverse
from factory.django import mute_signals

from distributions.models import TemporalDistribution, Timestep
from materials.models import Material, Sample, SampleSeries
from sources.waste_collection.models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionCatchment,
    CollectionCountOptions,
    CollectionFrequency,
    CollectionPropertyValue,
    CollectionSeason,
    CollectionSystem,
    WasteCategory,
    WasteFlyer,
)
from sources.waste_collection.tasks import check_wasteflyer_urls
from utils.object_management import services as om_services
from utils.object_management.models import ReviewAction
from utils.properties.models import Property, Unit
from utils.tests.testcases import ViewWithPermissionsTestCase


def _events_for(obj):
    return ReviewAction.objects.filter(
        content_type=ContentType.objects.get_for_model(type(obj)),
        object_id=obj.pk,
    )


def _revision(obj):
    return type(obj)._base_manager.get(pk=obj.pk).content_revision


class GovernedWriteFixtures:
    """Shared fixture builders for the domain-writer boundary tests."""

    @classmethod
    def make_chain(cls, owner, status="published"):
        catchment = CollectionCatchment.objects.create(
            name="GW Catchment", publication_status="published"
        )
        system = CollectionSystem.objects.create(
            name="GW System", publication_status="published"
        )
        category = WasteCategory.objects.create(
            name="GW Category", publication_status="published"
        )
        root = Collection.objects.create(
            name="GW Root",
            catchment=catchment,
            collection_system=system,
            waste_category=category,
            valid_from=date(2020, 1, 1),
            publication_status=status,
            owner=owner,
        )
        successor = Collection.objects.create(
            name="GW Successor",
            catchment=catchment,
            collection_system=system,
            waste_category=category,
            valid_from=date(2021, 1, 1),
            publication_status=status,
            owner=owner,
        )
        successor.predecessors.add(root)
        return root, successor

    @classmethod
    def make_property_unit(cls):
        unit = Unit.objects.create(name="GW Unit", publication_status="published")
        prop = Property.objects.create(
            name="GW Property", publication_status="published"
        )
        prop.allowed_units.add(unit)
        return prop, unit

    @staticmethod
    def empty_formset():
        return {
            "form-TOTAL_FORMS": "0",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
        }


class FrequencyCreateBoundaryTestCase(
    ViewWithPermissionsTestCase, GovernedWriteFixtures
):
    """FrequencyCreateView.post must persist the form + season formset
    inside the bound create adapter (authorize + atomic + audit)."""

    member_permissions = (
        "add_collectionfrequency",
        "add_collectionseason",
        "add_collectioncountoptions",
    )
    url_name = "collectionfrequency-create"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.distribution = TemporalDistribution.objects.get(name="Months of the year")
        cls.january = Timestep.objects.get(
            distribution=cls.distribution, name="January"
        )
        cls.may = Timestep.objects.get(distribution=cls.distribution, name="May")
        cls.june = Timestep.objects.get(distribution=cls.distribution, name="June")
        cls.december = Timestep.objects.get(
            distribution=cls.distribution, name="December"
        )
        cls.distribution.publication_status = "published"
        cls.distribution.save(update_fields=["publication_status"])
        Timestep.objects.filter(distribution=cls.distribution).update(
            publication_status="published"
        )

    def post_data(self):
        # Posting the untouched whole-year initial row is a no-op
        # (empty_permitted): seasons only link when the schedule differs.
        return {
            "name": "Boundary Frequency",
            "type": "Fixed-Seasonal",
            "form-INITIAL_FORMS": "0",
            "form-TOTAL_FORMS": "2",
            "form-0-distribution": self.distribution.pk,
            "form-0-first_timestep": self.january.pk,
            "form-0-last_timestep": self.may.pk,
            "form-0-standard": 150,
            "form-1-distribution": self.distribution.pk,
            "form-1-first_timestep": self.june.pk,
            "form-1-last_timestep": self.december.pk,
            "form-1-standard": 200,
        }

    def test_post_denied_for_outsider_creates_nothing(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse(self.url_name), self.post_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            CollectionFrequency.objects.filter(name="Boundary Frequency").exists()
        )

    def test_post_authorized_creates_frequency_with_audit_and_seasons(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse(self.url_name), self.post_data())
        self.assertEqual(response.status_code, 302)
        frequency = CollectionFrequency.objects.get(name="Boundary Frequency")
        self.assertEqual(frequency.owner, self.member)
        self.assertTrue(
            frequency.seasons.filter(
                first_timestep=self.january, last_timestep=self.may
            ).exists()
        )
        self.assertTrue(
            frequency.seasons.filter(
                first_timestep=self.june, last_timestep=self.december
            ).exists()
        )
        self.assertTrue(
            _events_for(frequency)
            .filter(action=ReviewAction.ACTION_CREATED, user=self.member)
            .exists()
        )
        # The season/options children are actor-owned private rows with
        # their own creation audits.
        season = CollectionSeason.objects.get(
            first_timestep=self.january, last_timestep=self.may
        )
        self.assertEqual(season.owner, self.member)
        self.assertEqual(season.publication_status, "private")
        self.assertTrue(
            _events_for(season)
            .filter(action=ReviewAction.ACTION_CREATED, user=self.member)
            .exists()
        )
        options = CollectionCountOptions.objects.get(frequency=frequency, season=season)
        self.assertEqual(options.owner, self.member)
        self.assertEqual(options.publication_status, "private")
        self.assertTrue(
            _events_for(options)
            .filter(action=ReviewAction.ACTION_CREATED, user=self.member)
            .exists()
        )

    def test_post_without_season_create_capability_denies_with_rollback(self):
        self.member.user_permissions.remove(
            Permission.objects.get(codename="add_collectionseason")
        )
        self.client.force_login(User.objects.get(pk=self.member.pk))
        response = self.client.post(reverse(self.url_name), self.post_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            CollectionFrequency.objects.filter(name="Boundary Frequency").exists()
        )
        self.assertFalse(
            CollectionSeason.objects.filter(last_timestep=self.may).exists()
        )

    def test_post_without_count_options_create_capability_denies_with_rollback(
        self,
    ):
        self.member.user_permissions.remove(
            Permission.objects.get(codename="add_collectioncountoptions")
        )
        self.client.force_login(User.objects.get(pk=self.member.pk))
        response = self.client.post(reverse(self.url_name), self.post_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            CollectionFrequency.objects.filter(name="Boundary Frequency").exists()
        )
        self.assertFalse(
            CollectionSeason.objects.filter(last_timestep=self.may).exists()
        )

    def test_post_foreign_private_season_match_denies_with_rollback(self):
        # A private season owned by someone else must not be silently
        # reused: validate_references fails closed and rolls the root
        # creation back.
        CollectionSeason.objects.create(
            owner=self.outsider,
            distribution=self.distribution,
            first_timestep=self.january,
            last_timestep=self.may,
            publication_status="private",
        )
        season_count = CollectionSeason.objects.count()
        self.client.force_login(self.member)
        response = self.client.post(reverse(self.url_name), self.post_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            CollectionFrequency.objects.filter(name="Boundary Frequency").exists()
        )
        self.assertEqual(CollectionSeason.objects.count(), season_count)

    def test_post_preserves_unrelated_foreign_and_published_seasons(self):
        # Unreferenced seasons — including a foreign private row the actor
        # cannot see — are never touched by the schedule write.
        foreign = CollectionSeason.objects.create(
            owner=self.outsider,
            distribution=self.distribution,
            first_timestep=self.january,
            last_timestep=self.june,
            publication_status="private",
        )
        unreferenced = CollectionSeason.objects.create(
            owner=self.owner,
            distribution=self.distribution,
            first_timestep=self.june,
            last_timestep=self.december,
            publication_status="published",
        )
        foreign_revision = foreign.content_revision
        unreferenced_revision = unreferenced.content_revision
        self.client.force_login(self.member)
        # Post only row 0 so both fixtures stay unreferenced by the
        # schedule and the positive path remains authorized.
        data = self.post_data()
        data["form-TOTAL_FORMS"] = "1"
        response = self.client.post(reverse(self.url_name), data)
        self.assertEqual(response.status_code, 302)
        foreign.refresh_from_db()
        unreferenced.refresh_from_db()
        self.assertEqual(foreign.publication_status, "private")
        self.assertEqual(foreign.owner, self.outsider)
        self.assertEqual(foreign.content_revision, foreign_revision)
        self.assertEqual(unreferenced.content_revision, unreferenced_revision)
        self.assertFalse(_events_for(foreign).exists())
        self.assertFalse(_events_for(unreferenced).exists())


class FrequencyUpdateBoundaryTestCase(
    ViewWithPermissionsTestCase, GovernedWriteFixtures
):
    """FrequencyUpdateView.post must write inside content_mutation on the
    frequency root: denied actors bump nothing; allowed edits bump the
    revision once for form + formset changes."""

    member_permissions = "change_collectionfrequency"
    url_name = "collectionfrequency-update"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.distribution = TemporalDistribution.objects.get(name="Months of the year")
        cls.january = Timestep.objects.get(
            distribution=cls.distribution, name="January"
        )
        cls.december = Timestep.objects.get(
            distribution=cls.distribution, name="December"
        )
        cls.distribution.publication_status = "published"
        cls.distribution.save(update_fields=["publication_status"])
        Timestep.objects.filter(distribution=cls.distribution).update(
            publication_status="published"
        )
        cls.whole_year, _ = CollectionSeason.objects.get_or_create(
            distribution=cls.distribution,
            first_timestep=cls.january,
            last_timestep=cls.december,
            defaults={"publication_status": "published"},
        )
        if cls.whole_year.publication_status != "published":
            cls.whole_year.publication_status = "published"
            cls.whole_year.save(update_fields=["publication_status"])
        cls.frequency = CollectionFrequency.objects.create(
            name="Owned Frequency", owner=cls.owner, type="Fixed-Seasonal"
        )
        cls.owner.user_permissions.add(
            Permission.objects.get(codename="change_collectionfrequency"),
            Permission.objects.get(codename="add_collectionseason"),
            Permission.objects.get(codename="add_collectioncountoptions"),
            Permission.objects.get(codename="change_collectioncountoptions"),
            Permission.objects.get(codename="delete_collectioncountoptions"),
        )

    def post_data(self, name="Owned Frequency edited"):
        return {
            "name": name,
            "type": "Fixed-Seasonal",
            "form-INITIAL_FORMS": "0",
            "form-TOTAL_FORMS": "1",
            "form-0-distribution": self.distribution.pk,
            "form-0-first_timestep": self.january.pk,
            "form-0-last_timestep": self.december.pk,
            "form-0-standard": 60,
        }

    def test_post_denied_for_member_without_object_access(self):
        self.client.force_login(self.member)
        revision = _revision(self.frequency)
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.frequency.pk}),
            self.post_data(),
        )
        self.assertEqual(response.status_code, 403)
        self.frequency.refresh_from_db()
        self.assertEqual(self.frequency.name, "Owned Frequency")
        self.assertEqual(_revision(self.frequency), revision)
        self.assertFalse(
            _events_for(self.frequency)
            .filter(action=ReviewAction.ACTION_EDITED)
            .exists()
        )

    def test_post_authorized_bumps_revision_and_saves_formset(self):
        self.client.force_login(self.owner)
        revision = _revision(self.frequency)
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.frequency.pk}),
            self.post_data(),
        )
        self.assertEqual(response.status_code, 302)
        self.frequency.refresh_from_db()
        self.assertEqual(self.frequency.name, "Owned Frequency edited")
        self.assertTrue(
            self.frequency.seasons.filter(
                first_timestep=self.january, last_timestep=self.december
            ).exists()
        )
        self.assertEqual(_revision(self.frequency), revision + 1)
        self.assertTrue(
            _events_for(self.frequency)
            .filter(action=ReviewAction.ACTION_EDITED, user=self.owner)
            .exists()
        )

    def test_post_owned_options_change_bumps_revision_and_audits(self):
        season, _ = CollectionSeason.objects.get_or_create(
            distribution=self.distribution,
            first_timestep=self.january,
            last_timestep=self.december,
            defaults={
                "owner": self.owner,
                "publication_status": "published",
            },
        )
        if season.publication_status != "published":
            season.publication_status = "published"
            season.save(update_fields=["publication_status"])
        options = CollectionCountOptions.objects.create(
            owner=self.owner,
            frequency=self.frequency,
            season=season,
            standard=60,
            publication_status="private",
        )
        options_revision = options.content_revision
        self.client.force_login(self.owner)
        data = self.post_data(name="Owned Frequency edited")
        data["form-0-standard"] = 75
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.frequency.pk}), data
        )
        self.assertEqual(response.status_code, 302)
        options.refresh_from_db()
        self.assertEqual(options.standard, 75)
        self.assertEqual(options.content_revision, options_revision + 1)
        self.assertTrue(
            _events_for(options)
            .filter(action=ReviewAction.ACTION_EDITED, user=self.owner)
            .exists()
        )

    def test_post_foreign_private_season_match_denies_full_rollback(self):
        foreign_season, _ = CollectionSeason.objects.get_or_create(
            distribution=self.distribution,
            first_timestep=self.january,
            last_timestep=self.december,
        )
        foreign_season.owner = self.outsider
        foreign_season.publication_status = "private"
        foreign_season.save(update_fields=["owner", "publication_status"])
        revision = _revision(self.frequency)
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.frequency.pk}),
            self.post_data(),
        )
        self.assertEqual(response.status_code, 403)
        self.frequency.refresh_from_db()
        self.assertEqual(self.frequency.name, "Owned Frequency")
        self.assertEqual(_revision(self.frequency), revision)
        self.assertFalse(
            _events_for(self.frequency)
            .filter(action=ReviewAction.ACTION_EDITED)
            .exists()
        )

    def test_post_changed_foreign_count_options_denies_full_rollback(self):
        season, _ = CollectionSeason.objects.get_or_create(
            distribution=self.distribution,
            first_timestep=self.january,
            last_timestep=self.december,
            defaults={
                "owner": self.owner,
                "publication_status": "published",
            },
        )
        if season.publication_status != "published":
            season.publication_status = "published"
            season.save(update_fields=["publication_status"])
        options = CollectionCountOptions.objects.create(
            owner=self.outsider,
            frequency=self.frequency,
            season=season,
            standard=60,
            publication_status="published",
        )
        options_revision = options.content_revision
        revision = _revision(self.frequency)
        self.client.force_login(self.owner)
        data = self.post_data(name="Owned Frequency edited")
        data["form-0-standard"] = 75
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.frequency.pk}), data
        )
        self.assertEqual(response.status_code, 403)
        self.frequency.refresh_from_db()
        options.refresh_from_db()
        self.assertEqual(self.frequency.name, "Owned Frequency")
        self.assertEqual(options.standard, 60)
        self.assertEqual(_revision(self.frequency), revision)
        self.assertEqual(options.content_revision, options_revision)

    def test_post_removed_foreign_count_options_denies_full_rollback(self):
        march = Timestep.objects.get(distribution=self.distribution, name="March")
        detached_season, _ = CollectionSeason.objects.get_or_create(
            distribution=self.distribution,
            first_timestep=self.january,
            last_timestep=march,
            defaults={
                "owner": self.owner,
                "publication_status": "published",
            },
        )
        if detached_season.publication_status != "published":
            detached_season.publication_status = "published"
            detached_season.save(update_fields=["publication_status"])
        options = CollectionCountOptions.objects.create(
            owner=self.outsider,
            frequency=self.frequency,
            season=detached_season,
            standard=30,
            publication_status="published",
        )
        revision = _revision(self.frequency)
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.frequency.pk}),
            self.post_data(),
        )
        self.assertEqual(response.status_code, 403)
        self.frequency.refresh_from_db()
        self.assertEqual(self.frequency.name, "Owned Frequency")
        self.assertEqual(_revision(self.frequency), revision)
        self.assertTrue(CollectionCountOptions.objects.filter(pk=options.pk).exists())


class CollectionPropertyValueCreateBoundaryTestCase(
    ViewWithPermissionsTestCase, GovernedWriteFixtures
):
    member_permissions = ("add_collectionpropertyvalue", "add_wasteflyer")
    url_name = "collectionpropertyvalue-create"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.collection = Collection.objects.create(
            name="CPV Host",
            publication_status="published",
            owner=cls.owner,
        )
        cls.prop, cls.unit = cls.make_property_unit()

    def post_data(self, **overrides):
        data = {
            "collection": self.collection.pk,
            "property": self.prop.pk,
            "unit": self.unit.pk,
            "year": 2022,
            "average": 12.5,
            "standard_deviation": "",
        }
        data.update(self.empty_formset())
        data.update(overrides)
        return data

    def test_post_denied_for_outsider_creates_nothing(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse(self.url_name), self.post_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            CollectionPropertyValue.objects.filter(property=self.prop).exists()
        )

    def test_post_rejects_foreign_private_collection_reference(self):
        foreign = Collection.objects.create(
            name="Foreign Private",
            publication_status="private",
            owner=self.owner,
        )
        self.client.force_login(self.member)
        response = self.client.post(
            reverse(self.url_name), self.post_data(collection=foreign.pk)
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            CollectionPropertyValue.objects.filter(collection=foreign).exists()
        )

    def test_post_authorized_creates_cpv_and_audit_inside_boundary(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse(self.url_name),
            self.post_data(
                **{
                    "form-TOTAL_FORMS": "1",
                    "form-0-url": "http://example.com/cpv-flyer.pdf",
                }
            ),
        )
        self.assertEqual(response.status_code, 302)
        cpv = CollectionPropertyValue.objects.get(
            collection=self.collection, property=self.prop, year=2022
        )
        self.assertEqual(cpv.owner, self.member)
        flyer = WasteFlyer.objects.get(url="http://example.com/cpv-flyer.pdf")
        self.assertIn(flyer, cpv.sources.all())
        # The resolved flyer is actor-owned/private with its own creation
        # audit — not silently adopted under someone else's authority.
        self.assertEqual(flyer.owner, self.member)
        self.assertEqual(flyer.publication_status, "private")
        self.assertTrue(
            _events_for(flyer)
            .filter(action=ReviewAction.ACTION_CREATED, user=self.member)
            .exists()
        )
        self.assertTrue(
            _events_for(cpv)
            .filter(action=ReviewAction.ACTION_CREATED, user=self.member)
            .exists()
        )

    def test_post_foreign_private_flyer_url_denies_with_full_rollback(self):
        foreign_flyer = WasteFlyer.objects.create(
            url="http://example.com/foreign.pdf",
            owner=self.outsider,
            publication_status="private",
        )
        flyer_events = _events_for(foreign_flyer).count()
        self.client.force_login(self.member)
        response = self.client.post(
            reverse(self.url_name),
            self.post_data(
                **{
                    "form-TOTAL_FORMS": "1",
                    "form-0-url": foreign_flyer.url,
                }
            ),
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            CollectionPropertyValue.objects.filter(property=self.prop).exists()
        )
        self.assertEqual(WasteFlyer.objects.count(), 1)
        self.assertEqual(_events_for(foreign_flyer).count(), flyer_events)

    def test_post_new_flyer_url_without_add_wasteflyer_denies(self):
        self.member.user_permissions.remove(
            Permission.objects.get(codename="add_wasteflyer")
        )
        self.client.force_login(User.objects.get(pk=self.member.pk))
        audits_before = ReviewAction.objects.count()
        response = self.client.post(
            reverse(self.url_name),
            self.post_data(
                **{
                    "form-TOTAL_FORMS": "1",
                    "form-0-url": "http://example.com/new-flyer.pdf",
                }
            ),
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            CollectionPropertyValue.objects.filter(property=self.prop).exists()
        )
        self.assertFalse(WasteFlyer.objects.exists())
        self.assertEqual(ReviewAction.objects.count(), audits_before)

    def test_post_existing_readable_flyer_url_attaches_without_create_cap(self):
        existing = WasteFlyer.objects.create(
            url="http://example.com/readable.pdf",
            owner=self.outsider,
            publication_status="published",
        )
        existing_events = _events_for(existing).count()
        self.member.user_permissions.remove(
            Permission.objects.get(codename="add_wasteflyer")
        )
        self.client.force_login(User.objects.get(pk=self.member.pk))
        response = self.client.post(
            reverse(self.url_name),
            self.post_data(
                **{
                    "form-TOTAL_FORMS": "1",
                    "form-0-url": existing.url,
                }
            ),
        )
        self.assertEqual(response.status_code, 302)
        cpv = CollectionPropertyValue.objects.get(
            collection=self.collection, property=self.prop, year=2022
        )
        self.assertIn(existing, cpv.sources.all())
        self.assertEqual(WasteFlyer.objects.count(), 1)
        self.assertEqual(_events_for(existing).count(), existing_events)


class CollectionPropertyValueUpdateBoundaryTestCase(
    ViewWithPermissionsTestCase, GovernedWriteFixtures
):
    """The update route re-parents through the boundary's reassignment
    semantics, never through a silent field overwrite."""

    member_permissions = "change_collectionpropertyvalue"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.root, cls.succ = cls.make_chain(cls.owner)
        cls.prop, cls.unit = cls.make_property_unit()
        cls.cpv = CollectionPropertyValue.objects.create(
            owner=cls.owner,
            collection=cls.succ,
            property=cls.prop,
            unit=cls.unit,
            year=2020,
            average=5,
            publication_status="private",
        )
        cls.owner.user_permissions.add(
            Permission.objects.get(codename="change_collectionpropertyvalue")
        )

    def post_data(self, collection=None):
        data = {
            "collection": (collection or self.succ).pk,
            "property": self.prop.pk,
            "unit": self.unit.pk,
            "year": 2020,
            "average": 6,
            "standard_deviation": "",
        }
        data.update(self.empty_formset())
        return data

    def test_post_denied_for_member_without_object_access(self):
        self.client.force_login(self.member)
        revision = _revision(self.cpv)
        response = self.client.post(
            reverse("collectionpropertyvalue-update", kwargs={"pk": self.cpv.pk}),
            self.post_data(),
        )
        self.assertEqual(response.status_code, 403)
        self.cpv.refresh_from_db()
        self.assertEqual(self.cpv.average, 5)
        self.assertEqual(_revision(self.cpv), revision)

    def test_update_reanchors_through_authorized_reassignment(self):
        """Posting a non-anchor parent moves the row to its chain anchor via
        decide_reassign — locked roots, revision bump, audit."""
        self.client.force_login(self.owner)
        revision = _revision(self.cpv)
        response = self.client.post(
            reverse("collectionpropertyvalue-update", kwargs={"pk": self.cpv.pk}),
            self.post_data(),
        )
        self.assertEqual(response.status_code, 302)
        self.cpv.refresh_from_db()
        self.assertEqual(self.cpv.collection_id, self.root.pk)
        self.assertEqual(_revision(self.cpv), revision + 1)
        self.assertTrue(
            _events_for(self.cpv)
            .filter(action=ReviewAction.ACTION_EDITED, user=self.owner)
            .exists()
        )

    def test_update_denied_when_proposed_parent_is_invisible(self):
        foreign = Collection.objects.create(
            name="Foreign Private",
            publication_status="private",
            owner=self.member,
        )
        self.client.force_login(self.owner)
        revision = _revision(self.cpv)
        response = self.client.post(
            reverse("collectionpropertyvalue-update", kwargs={"pk": self.cpv.pk}),
            self.post_data(collection=foreign),
        )
        # Forged invisible reference: form-level rejection, no reparent.
        self.assertEqual(response.status_code, 200)
        self.cpv.refresh_from_db()
        self.assertEqual(self.cpv.collection_id, self.succ.pk)
        self.assertEqual(_revision(self.cpv), revision)


class CollectionPropertyValueModalDeleteBoundaryTestCase(
    ViewWithPermissionsTestCase, GovernedWriteFixtures
):
    """The anchor-twin deletion crosses to a different governed record: it
    runs its own decide(\"delete\") + content_mutation boundary, so a frozen
    twin aborts the whole request instead of vanishing silently."""

    member_permissions = "delete_collectionpropertyvalue"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.root, cls.succ = cls.make_chain(cls.owner)
        cls.prop, cls.unit = cls.make_property_unit()
        cls.anchor_value = CollectionPropertyValue.objects.create(
            owner=cls.owner,
            collection=cls.root,
            property=cls.prop,
            unit=cls.unit,
            year=2020,
            average=10,
            publication_status="private",
        )
        cls.child_value = CollectionPropertyValue.objects.create(
            owner=cls.owner,
            collection=cls.succ,
            property=cls.prop,
            unit=cls.unit,
            year=2020,
            average=11,
            publication_status="private",
        )
        cls.owner.user_permissions.add(
            Permission.objects.get(codename="delete_collectionpropertyvalue")
        )

    def test_delete_child_governs_anchor_twin_delete(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse(
                "collectionpropertyvalue-delete-modal",
                kwargs={"pk": self.child_value.pk},
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            CollectionPropertyValue.objects.filter(
                pk__in=[self.child_value.pk, self.anchor_value.pk]
            ).exists()
        )
        self.assertTrue(
            ReviewAction.objects.filter(
                content_type=ContentType.objects.get_for_model(CollectionPropertyValue),
                object_id=self.anchor_value.pk,
                action=ReviewAction.ACTION_DELETED,
                user=self.owner,
            ).exists()
        )

    def test_primary_delete_failure_rolls_back_twin_deletion(self):
        # The twin's own governed delete runs first inside the shared
        # transaction: at the moment the primary delete fails, the twin is
        # already gone with its delete audit written — yet the rolled-back
        # request must restore both rows and the audit state.
        real_delete = CollectionPropertyValue.delete
        calls = []

        def flaky_delete(instance, *args, **kwargs):
            calls.append(instance.pk)
            if len(calls) == 1:
                return real_delete(instance, *args, **kwargs)
            assert not CollectionPropertyValue.objects.filter(
                pk=self.anchor_value.pk
            ).exists()
            assert (
                _events_for(self.anchor_value)
                .filter(action=ReviewAction.ACTION_DELETED)
                .exists()
            )
            raise RuntimeError("primary delete failed")

        self.client.force_login(self.owner)
        audits_before = ReviewAction.objects.count()
        anchor_revision = self.anchor_value.content_revision
        child_revision = self.child_value.content_revision
        anchor_average = self.anchor_value.average
        child_average = self.child_value.average
        with (
            patch.object(CollectionPropertyValue, "delete", flaky_delete),
            self.assertLogs("django.request", level="ERROR") as logs,
            self.assertRaises(RuntimeError),
        ):
            self.client.post(
                reverse(
                    "collectionpropertyvalue-delete-modal",
                    kwargs={"pk": self.child_value.pk},
                )
            )
        self.assertTrue(any("primary delete failed" in line for line in logs.output))
        self.assertEqual(calls, [self.anchor_value.pk, self.child_value.pk])
        self.assertCountEqual(
            list(
                CollectionPropertyValue.objects.filter(
                    pk__in=[self.child_value.pk, self.anchor_value.pk]
                ).values_list("pk", flat=True)
            ),
            [self.anchor_value.pk, self.child_value.pk],
        )
        self.anchor_value.refresh_from_db()
        self.child_value.refresh_from_db()
        self.assertEqual(self.anchor_value.average, anchor_average)
        self.assertEqual(self.child_value.average, child_average)
        self.assertEqual(self.anchor_value.content_revision, anchor_revision)
        self.assertEqual(self.child_value.content_revision, child_revision)
        self.assertEqual(ReviewAction.objects.count(), audits_before)

    def test_primary_audit_failure_after_both_deletes_rolls_back(self):
        # Even when BOTH physical deletions already ran, a failure writing
        # the primary's delete audit still rolls everything back.
        real_record_event = om_services._record_event
        seen = {}

        def flaky_event(obj, actor, action, **kwargs):
            object_id = kwargs.get("object_id", getattr(obj, "pk", None))
            if (
                action == ReviewAction.ACTION_DELETED
                and object_id == self.child_value.pk
            ):
                seen["anchor_gone"] = not CollectionPropertyValue.objects.filter(
                    pk=self.anchor_value.pk
                ).exists()
                seen["child_gone"] = not CollectionPropertyValue.objects.filter(
                    pk=self.child_value.pk
                ).exists()
                seen["anchor_audit"] = (
                    _events_for(self.anchor_value)
                    .filter(action=ReviewAction.ACTION_DELETED)
                    .exists()
                )
                raise RuntimeError("primary audit failed")
            return real_record_event(obj, actor, action, **kwargs)

        self.client.force_login(self.owner)
        audits_before = ReviewAction.objects.count()
        with (
            patch(
                "utils.object_management.services._record_event",
                side_effect=flaky_event,
            ),
            self.assertLogs("django.request", level="ERROR") as logs,
            self.assertRaises(RuntimeError),
        ):
            self.client.post(
                reverse(
                    "collectionpropertyvalue-delete-modal",
                    kwargs={"pk": self.child_value.pk},
                )
            )
        self.assertTrue(any("primary audit failed" in line for line in logs.output))
        self.assertEqual(
            seen,
            {
                "anchor_gone": True,
                "child_gone": True,
                "anchor_audit": True,
            },
        )
        self.assertCountEqual(
            list(
                CollectionPropertyValue.objects.filter(
                    pk__in=[self.child_value.pk, self.anchor_value.pk]
                ).values_list("pk", flat=True)
            ),
            [self.anchor_value.pk, self.child_value.pk],
        )
        self.assertEqual(ReviewAction.objects.count(), audits_before)

    def test_published_twin_denies_the_whole_delete(self):
        self.anchor_value.publication_status = "published"
        self.anchor_value.save(update_fields=["publication_status"])
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse(
                "collectionpropertyvalue-delete-modal",
                kwargs={"pk": self.child_value.pk},
            )
        )
        self.assertEqual(response.status_code, 403)
        # The twin's denied delete aborts before the primary governed delete.
        self.assertTrue(
            CollectionPropertyValue.objects.filter(
                pk__in=[self.child_value.pk, self.anchor_value.pk]
            ).exists()
        )


class AggregatedCollectionPropertyValueBoundaryTestCase(
    ViewWithPermissionsTestCase, GovernedWriteFixtures
):
    member_permissions = (
        "add_aggregatedcollectionpropertyvalue",
        "change_aggregatedcollectionpropertyvalue",
        "add_wasteflyer",
    )

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.collection = Collection.objects.create(
            name="ACPV Host",
            publication_status="published",
            owner=cls.owner,
        )
        cls.prop, cls.unit = cls.make_property_unit()
        cls.acpv = AggregatedCollectionPropertyValue.objects.create(
            name="ACPV",
            owner=cls.owner,
            property=cls.prop,
            unit=cls.unit,
            year=2021,
            average=7,
            publication_status="private",
        )
        cls.acpv.collections.add(cls.collection)
        cls.owner.user_permissions.add(
            Permission.objects.get(codename="change_aggregatedcollectionpropertyvalue")
        )

    def post_data(self, collections=None, average=9, **overrides):
        data = {
            "collections": [c.pk for c in (collections or [self.collection])],
            "property": self.prop.pk,
            "unit": self.unit.pk,
            "year": 2021,
            "average": average,
            "standard_deviation": "",
        }
        data.update(self.empty_formset())
        data.update(overrides)
        return data

    def test_create_denied_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse("aggregatedcollectionpropertyvalue-create"),
            self.post_data(),
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            AggregatedCollectionPropertyValue.objects.filter(
                property=self.prop, year=2021, average=9
            ).exists()
        )

    def test_create_authorized_persists_parent_and_sources_inside_boundary(
        self,
    ):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("aggregatedcollectionpropertyvalue-create"),
            self.post_data(
                **{
                    "form-TOTAL_FORMS": "1",
                    "form-0-url": "http://example.com/acpv-flyer.pdf",
                }
            ),
        )
        self.assertEqual(response.status_code, 302)
        acpv = AggregatedCollectionPropertyValue.objects.get(
            property=self.prop, year=2021, average=9
        )
        self.assertEqual(acpv.owner, self.member)
        self.assertEqual(
            list(acpv.collections.values_list("pk", flat=True)),
            [self.collection.pk],
        )
        flyer = WasteFlyer.objects.get(url="http://example.com/acpv-flyer.pdf")
        self.assertIn(flyer, acpv.sources.all())
        self.assertTrue(
            _events_for(acpv)
            .filter(action=ReviewAction.ACTION_CREATED, user=self.member)
            .exists()
        )

    def test_create_foreign_private_flyer_url_denies_full_rollback(self):
        foreign_flyer = WasteFlyer.objects.create(
            url="http://example.com/acpv-foreign.pdf",
            owner=self.outsider,
            publication_status="private",
        )
        flyer_events = _events_for(foreign_flyer).count()
        self.client.force_login(self.member)
        audits_before = ReviewAction.objects.count()
        response = self.client.post(
            reverse("aggregatedcollectionpropertyvalue-create"),
            self.post_data(
                **{
                    "form-TOTAL_FORMS": "1",
                    "form-0-url": foreign_flyer.url,
                }
            ),
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            AggregatedCollectionPropertyValue.objects.filter(
                property=self.prop, year=2021
            )
            .exclude(pk=self.acpv.pk)
            .exists()
        )
        self.assertEqual(WasteFlyer.objects.count(), 1)
        self.assertEqual(_events_for(foreign_flyer).count(), flyer_events)
        self.assertEqual(ReviewAction.objects.count(), audits_before)

    def test_create_new_flyer_url_without_add_wasteflyer_denies(self):
        self.member.user_permissions.remove(
            Permission.objects.get(codename="add_wasteflyer")
        )
        self.client.force_login(User.objects.get(pk=self.member.pk))
        audits_before = ReviewAction.objects.count()
        response = self.client.post(
            reverse("aggregatedcollectionpropertyvalue-create"),
            self.post_data(
                **{
                    "form-TOTAL_FORMS": "1",
                    "form-0-url": "http://example.com/acpv-new.pdf",
                }
            ),
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            AggregatedCollectionPropertyValue.objects.filter(
                property=self.prop, year=2021
            )
            .exclude(pk=self.acpv.pk)
            .exists()
        )
        self.assertFalse(WasteFlyer.objects.exists())
        self.assertEqual(ReviewAction.objects.count(), audits_before)

    def test_update_denied_for_member_without_object_access(self):
        self.client.force_login(self.member)
        revision = _revision(self.acpv)
        response = self.client.post(
            reverse(
                "aggregatedcollectionpropertyvalue-update",
                kwargs={"pk": self.acpv.pk},
            ),
            self.post_data(),
        )
        self.assertEqual(response.status_code, 403)
        self.acpv.refresh_from_db()
        self.assertEqual(self.acpv.average, 7)
        self.assertEqual(_revision(self.acpv), revision)

    def test_update_authorized_bumps_revision_and_audit(self):
        self.client.force_login(self.owner)
        revision = _revision(self.acpv)
        response = self.client.post(
            reverse(
                "aggregatedcollectionpropertyvalue-update",
                kwargs={"pk": self.acpv.pk},
            ),
            self.post_data(average=11),
        )
        self.assertEqual(response.status_code, 302)
        self.acpv.refresh_from_db()
        self.assertEqual(self.acpv.average, 11)
        self.assertEqual(_revision(self.acpv), revision + 1)
        self.assertTrue(
            _events_for(self.acpv)
            .filter(action=ReviewAction.ACTION_EDITED, user=self.owner)
            .exists()
        )


class CollectionWasteSamplesBoundaryTestCase(
    ViewWithPermissionsTestCase, GovernedWriteFixtures
):
    """samples.add/remove is a content edit on the Collection root."""

    member_permissions = "change_collection"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(
            name="GW Material", publication_status="published"
        )
        series = SampleSeries.objects.create(
            name="GW Series", material=material, publication_status="published"
        )
        cls.collection = Collection.objects.create(
            name="Sample Host", publication_status="private", owner=cls.owner
        )
        cls.sample = Sample.objects.create(
            name="GW Published Sample",
            material=material,
            series=series,
            publication_status="published",
        )
        cls.foreign_sample = Sample.objects.create(
            name="Foreign Private Sample",
            material=material,
            series=series,
            publication_status="private",
            owner=cls.member,
        )
        cls.owner.user_permissions.add(
            Permission.objects.get(codename="change_collection")
        )

    def url(self):
        return reverse("collection-wastesamples", kwargs={"pk": self.collection.pk})

    def test_post_denied_for_member_without_object_access(self):
        self.client.force_login(self.member)
        revision = _revision(self.collection)
        response = self.client.post(
            self.url(), {"sample": self.sample.pk, "submit": "Add"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.collection.samples.exists())
        self.assertEqual(_revision(self.collection), revision)

    def test_post_rejects_foreign_private_sample_reference(self):
        self.client.force_login(self.owner)
        revision = _revision(self.collection)
        response = self.client.post(
            self.url(), {"sample": self.foreign_sample.pk, "submit": "Add"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.collection.samples.exists())
        self.assertEqual(_revision(self.collection), revision)

    def test_post_authorized_links_sample_with_revision_and_audit(self):
        self.client.force_login(self.owner)
        revision = _revision(self.collection)
        response = self.client.post(
            self.url(), {"sample": self.sample.pk, "submit": "Add"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.collection.samples.filter(pk=self.sample.pk).exists())
        self.assertEqual(_revision(self.collection), revision + 1)
        self.assertTrue(
            _events_for(self.collection)
            .filter(action=ReviewAction.ACTION_EDITED, user=self.owner)
            .exists()
        )


class CollectionPredecessorsBoundaryTestCase(
    ViewWithPermissionsTestCase, GovernedWriteFixtures
):
    """predecessors.add/remove is a content edit on this Collection; the
    policy declares no parent_path for Collection so edit + reference read
    govern — there is no reassign-level decision for the edge."""

    member_permissions = "change_collection"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.collection = Collection.objects.create(
            name="Edge Host", publication_status="private", owner=cls.owner
        )
        cls.predecessor = Collection.objects.create(
            name="GW Published Predecessor", publication_status="published"
        )
        cls.foreign_predecessor = Collection.objects.create(
            name="Foreign Private Predecessor",
            publication_status="private",
            owner=cls.member,
        )
        cls.owner.user_permissions.add(
            Permission.objects.get(codename="change_collection")
        )

    def url(self):
        return reverse("collection-predecessors", kwargs={"pk": self.collection.pk})

    def test_post_denied_for_member_without_object_access(self):
        self.client.force_login(self.member)
        revision = _revision(self.collection)
        response = self.client.post(
            self.url(), {"predecessor": self.predecessor.pk, "submit": "Add"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.collection.predecessors.exists())
        self.assertEqual(_revision(self.collection), revision)

    def test_post_rejects_foreign_private_predecessor_reference(self):
        self.client.force_login(self.owner)
        revision = _revision(self.collection)
        response = self.client.post(
            self.url(),
            {"predecessor": self.foreign_predecessor.pk, "submit": "Add"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.collection.predecessors.exists())
        self.assertEqual(_revision(self.collection), revision)

    def test_post_authorized_links_predecessor_with_revision_and_audit(self):
        self.client.force_login(self.owner)
        revision = _revision(self.collection)
        response = self.client.post(
            self.url(), {"predecessor": self.predecessor.pk, "submit": "Add"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            self.collection.predecessors.filter(pk=self.predecessor.pk).exists()
        )
        self.assertEqual(_revision(self.collection), revision + 1)
        self.assertTrue(
            _events_for(self.collection)
            .filter(action=ReviewAction.ACTION_EDITED, user=self.owner)
            .exists()
        )


class CollectionAddPropertyValueBoundaryTestCase(
    ViewWithPermissionsTestCase, GovernedWriteFixtures
):
    """The add-property gate is the central attached-create decision."""

    member_permissions = "add_collectionpropertyvalue"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.published_collection = Collection.objects.create(
            name="Public Host", publication_status="published", owner=cls.owner
        )
        cls.private_collection = Collection.objects.create(
            name="Foreign Private", publication_status="private", owner=cls.owner
        )
        cls.prop, cls.unit = cls.make_property_unit()

    def post_data(self, collection):
        data = {
            "collection": collection.pk,
            "property": self.prop.pk,
            "unit": self.unit.pk,
            "year": 2022,
            "average": 20,
        }
        data.update(self.empty_formset())
        return data

    def test_post_denied_for_invisible_parent(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse(
                "collection-add-property", kwargs={"pk": self.private_collection.pk}
            ),
            self.post_data(self.private_collection),
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            CollectionPropertyValue.objects.filter(property=self.prop).exists()
        )

    def test_post_authorized_attaches_to_anchor_with_audit(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse(
                "collection-add-property",
                kwargs={"pk": self.published_collection.pk},
            ),
            self.post_data(self.published_collection),
        )
        self.assertEqual(response.status_code, 302)
        cpv = CollectionPropertyValue.objects.get(property=self.prop)
        self.assertEqual(
            cpv.collection_id,
            (self.published_collection.version_anchor or self.published_collection).pk,
        )
        self.assertTrue(
            _events_for(cpv)
            .filter(action=ReviewAction.ACTION_CREATED, user=self.member)
            .exists()
        )


class WasteFlyerCheckUrlBoundaryTestCase(ViewWithPermissionsTestCase):
    """The single-flyer check gate is the central ``check_url`` decision:
    active actor + change capability + read access on the target. The staff
    flag alone no longer opens it."""

    member_permissions = "change_wasteflyer"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        with mute_signals(signals.post_save):
            cls.published_flyer = WasteFlyer.objects.create(
                title="Public flyer",
                abbreviation="PF",
                url="http://example.com/public.pdf",
                publication_status="published",
            )
            cls.foreign_flyer = WasteFlyer.objects.create(
                title="Foreign private flyer",
                abbreviation="FPF",
                url="http://example.com/private.pdf",
                publication_status="private",
                owner=cls.owner,
            )

    @patch("sources.waste_collection.views.check_wasteflyer_url")
    def test_get_authorized_for_member_on_published_flyer(self, mock_task):
        mock_task.delay.return_value.task_id = "task-id"
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("wasteflyer-check-url", kwargs={"pk": self.published_flyer.pk})
        )
        self.assertEqual(response.status_code, 200)
        mock_task.delay.assert_called_once_with(self.published_flyer.pk)

    @patch("sources.waste_collection.views.check_wasteflyer_url")
    def test_get_denied_for_invisible_flyer(self, mock_task):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("wasteflyer-check-url", kwargs={"pk": self.foreign_flyer.pk})
        )
        self.assertEqual(response.status_code, 403)
        mock_task.delay.assert_not_called()

    @patch("sources.waste_collection.views.check_wasteflyer_url")
    def test_get_denied_for_staff_without_change_permission(self, mock_task):
        """is_staff never was a capability: without change_wasteflyer the
        central decision denies."""
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("wasteflyer-check-url", kwargs={"pk": self.published_flyer.pk})
        )
        self.assertEqual(response.status_code, 403)
        mock_task.delay.assert_not_called()

    @patch("sources.waste_collection.views.check_wasteflyer_url")
    def test_get_denied_for_outsider(self, mock_task):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("wasteflyer-check-url", kwargs={"pk": self.published_flyer.pk})
        )
        self.assertEqual(response.status_code, 403)
        mock_task.delay.assert_not_called()


@patch("sources.waste_collection.tasks.chord")
class WasteFlyerListCheckUrlsScopingTestCase(TestCase):
    """The bulk URL check must schedule signatures only for flyers the
    requesting user may read — forged filter params cannot reach invisible
    private records."""

    def setUp(self):
        self.owner = User.objects.create_user("flyer_task_owner")
        self.other_owner = User.objects.create_user("flyer_task_other")
        with mute_signals(signals.post_save):
            self.own_flyer = WasteFlyer.objects.create(
                owner=self.owner,
                title="Own private flyer",
                abbreviation="OWN",
                publication_status="private",
            )
            self.foreign_flyer = WasteFlyer.objects.create(
                owner=self.other_owner,
                title="Foreign private flyer",
                abbreviation="FRN",
                publication_status="private",
            )
            self.public_flyer = WasteFlyer.objects.create(
                owner=self.other_owner,
                title="Published flyer",
                abbreviation="PUB",
                publication_status="published",
            )

    def _scheduled_ids(self, mock_chord, params, user_id):
        captured = {}

        def fake_chord(header):
            captured["header"] = header
            return lambda _: type("task", (object,), {"task_id": "cb-id"})()

        mock_chord.side_effect = fake_chord
        check_wasteflyer_urls.run(params, user_id)
        return sorted(signature.args[0] for signature in captured["header"])

    def test_unscoped_params_never_schedule_foreign_private_flyers(self, mock_chord):
        scheduled = self._scheduled_ids(
            mock_chord, QueryDict("", mutable=True), self.owner.pk
        )
        self.assertEqual(scheduled, sorted([self.own_flyer.pk, self.public_flyer.pk]))
        self.assertNotIn(self.foreign_flyer.pk, scheduled)

    def test_anonymous_user_schedules_only_public_flyers(self, mock_chord):
        scheduled = self._scheduled_ids(mock_chord, QueryDict("", mutable=True), None)
        self.assertEqual(scheduled, [self.public_flyer.pk])


class FrequencyProvisionedRoleEndToEndTestCase(TestCase):
    """End-to-end frequency create/update through the governed schedule
    write by a user whose capabilities come from the manifest-provisioned
    ``editors`` role — not a hand-assembled permission list."""

    @classmethod
    def setUpTestData(cls):
        with redirect_stdout(io.StringIO()):
            call_command("sync_roles", "--apply")
        cls.distribution = TemporalDistribution.objects.get(name="Months of the year")
        cls.distribution.publication_status = "published"
        cls.distribution.save(update_fields=["publication_status"])
        Timestep.objects.filter(distribution=cls.distribution).update(
            publication_status="published"
        )
        cls.january = Timestep.objects.get(
            distribution=cls.distribution, name="January"
        )
        cls.may = Timestep.objects.get(distribution=cls.distribution, name="May")
        cls.june = Timestep.objects.get(distribution=cls.distribution, name="June")
        cls.december = Timestep.objects.get(
            distribution=cls.distribution, name="December"
        )
        cls.editor = User.objects.create(username="role-editor")
        cls.editor.groups.add(Group.objects.get(name="editors"))

    def schedule_data(self, name, **overrides):
        data = {
            "name": name,
            "type": "Fixed-Seasonal",
            "form-INITIAL_FORMS": "0",
            "form-TOTAL_FORMS": "2",
            "form-0-distribution": self.distribution.pk,
            "form-0-first_timestep": self.january.pk,
            "form-0-last_timestep": self.may.pk,
            "form-0-standard": 150,
            "form-1-distribution": self.distribution.pk,
            "form-1-first_timestep": self.june.pk,
            "form-1-last_timestep": self.december.pk,
            "form-1-standard": 200,
        }
        data.update(overrides)
        return data

    def test_editor_role_creates_and_updates_frequency_schedule(self):
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse("collectionfrequency-create"), self.schedule_data("Role Frequency")
        )
        self.assertEqual(response.status_code, 302)
        frequency = CollectionFrequency.objects.get(name="Role Frequency")
        self.assertEqual(frequency.owner, self.editor)
        season = CollectionSeason.objects.get(
            first_timestep=self.january, last_timestep=self.may
        )
        options = CollectionCountOptions.objects.get(frequency=frequency, season=season)
        self.assertTrue(
            _events_for(season)
            .filter(action=ReviewAction.ACTION_CREATED, user=self.editor)
            .exists()
        )
        self.assertTrue(
            _events_for(options)
            .filter(action=ReviewAction.ACTION_CREATED, user=self.editor)
            .exists()
        )

        response = self.client.post(
            reverse("collectionfrequency-update", kwargs={"pk": frequency.pk}),
            self.schedule_data("Role Frequency", **{"form-0-standard": 175}),
        )
        self.assertEqual(response.status_code, 302)
        options.refresh_from_db()
        self.assertEqual(options.standard, 175)
        self.assertTrue(
            _events_for(options)
            .filter(action=ReviewAction.ACTION_EDITED, user=self.editor)
            .exists()
        )
