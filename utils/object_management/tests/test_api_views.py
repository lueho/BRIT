"""Tests for review workflow API endpoints in object_management."""

from datetime import date

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save, pre_save
from django.test import TestCase
from django.urls import reverse
from factory.django import mute_signals

from bibliography.models import Source
from distributions.models import TemporalDistribution, Timestep
from sources.waste_collection.models import (
    Collection,
    CollectionCountOptions,
    CollectionFrequency,
    CollectionPropertyValue,
    CollectionSeason,
    WasteFlyer,
)
from utils.object_management.models import ReviewAction, UserCreatedObject
from utils.properties.models import Property, Unit


class ReviewAPIViewsTests(TestCase):
    """Validate review queue, comment, and review-context API behavior."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner")
        cls.moderator = User.objects.create_user(username="moderator")
        cls.regular_user = User.objects.create_user(username="regular")
        distribution = TemporalDistribution.objects.get(name="Months of the year")
        january = Timestep.objects.get(name="January")
        june = Timestep.objects.get(name="June")
        july = Timestep.objects.get(name="July")
        december = Timestep.objects.get(name="December")
        first_half_year, _ = CollectionSeason.objects.get_or_create(
            distribution=distribution,
            first_timestep=january,
            last_timestep=june,
        )
        second_half_year, _ = CollectionSeason.objects.get_or_create(
            distribution=distribution,
            first_timestep=july,
            last_timestep=december,
        )
        cls.frequency = CollectionFrequency.objects.create(
            name="Seasonal flexibility",
            type="Fixed-Seasonal",
            publication_status="published",
        )
        CollectionCountOptions.objects.create(
            frequency=cls.frequency,
            season=first_half_year,
            standard=26,
            option_1=52,
        )
        CollectionCountOptions.objects.create(
            frequency=cls.frequency,
            season=second_half_year,
            standard=13,
        )

        content_type = ContentType.objects.get_for_model(Collection)
        permission, _ = Permission.objects.get_or_create(
            codename="can_moderate_collection",
            content_type=content_type,
            defaults={"name": "Can moderate collections"},
        )
        cls.moderator.user_permissions.add(permission)

        with mute_signals(post_save, pre_save):
            cls.review_collection = Collection.objects.create(
                name="Review Collection",
                owner=cls.owner,
                frequency=cls.frequency,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )
            cls.moderator_owned_review_collection = Collection.objects.create(
                name="Moderator Owned Review Collection",
                owner=cls.moderator,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )

        cls.content_type_id = content_type.id

    def test_review_queue_requires_authentication(self):
        """Anonymous callers are denied by API auth requirements."""
        url = reverse("object_management:api_review_queue")

        response = self.client.get(url)

        self.assertIn(response.status_code, (401, 403))

    def test_review_queue_returns_items_for_moderator(self):
        """Moderators receive queue items, excluding their own submissions."""
        url = reverse("object_management:api_review_queue")
        self.client.force_login(self.moderator)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("results", payload)

        names = [item["name"] for item in payload["results"]]
        self.assertIn("Review Collection", names)
        self.assertNotIn("Moderator Owned Review Collection", names)

    def test_add_review_comment_api_allows_moderator(self):
        """Moderators can add review comments via API."""
        url = reverse(
            "object_management:api_add_review_comment",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )
        self.client.force_login(self.moderator)

        response = self.client.post(url, data={"comment": "Looks good"})

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            ReviewAction.objects.filter(
                content_type_id=self.content_type_id,
                object_id=self.review_collection.id,
                action=ReviewAction.ACTION_COMMENT,
                user=self.moderator,
                comment="Looks good",
            ).exists()
        )

    def test_add_review_comment_api_forbids_regular_user(self):
        """Non-moderator users cannot comment on others' review items."""
        url = reverse(
            "object_management:api_add_review_comment",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )
        self.client.force_login(self.regular_user)

        response = self.client.post(url, data={"comment": "No access"})

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            ReviewAction.objects.filter(
                content_type_id=self.content_type_id,
                object_id=self.review_collection.id,
                action=ReviewAction.ACTION_COMMENT,
                user=self.regular_user,
            ).exists()
        )

    def test_review_context_api_success(self):
        """Context endpoint returns object and review-history payload."""
        url = reverse(
            "object_management:api_review_context",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )
        self.client.force_login(self.moderator)

        ReviewAction.objects.create(
            content_type_id=self.content_type_id,
            object_id=self.review_collection.id,
            action=ReviewAction.ACTION_COMMENT,
            comment="Existing comment",
            user=self.moderator,
        )

        response = self.client.get(url, data={"include_history": True})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("context", payload)
        self.assertEqual(
            payload["context"]["object"]["object_id"], self.review_collection.id
        )
        self.assertEqual(
            payload["context"]["review_history"][0]["comment"], "Existing comment"
        )

    def test_review_context_allows_owner_and_returns_feedback_summary(self):
        """Owners of in-review collections can read structured review feedback."""
        url = reverse(
            "object_management:api_review_context",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )
        self.client.force_login(self.owner)

        ReviewAction.objects.create(
            content_type_id=self.content_type_id,
            object_id=self.review_collection.id,
            action=ReviewAction.ACTION_SUBMITTED,
            comment="",
            user=self.owner,
        )
        ReviewAction.objects.create(
            content_type_id=self.content_type_id,
            object_id=self.review_collection.id,
            action=ReviewAction.ACTION_COMMENT,
            comment="Please clarify the collection frequency.",
            user=self.moderator,
        )

        response = self.client.get(url, data={"include_history": True})

        self.assertEqual(response.status_code, 200)
        payload = response.json()["context"]
        self.assertTrue(payload["review_feedback"]["has_feedback"])
        self.assertEqual(
            payload["review_feedback"]["latest_submission"]["action"],
            ReviewAction.ACTION_SUBMITTED,
        )
        self.assertEqual(
            payload["review_feedback"]["latest_feedback_action"]["comment"],
            "Please clarify the collection frequency.",
        )
        self.assertEqual(
            payload["review_feedback"]["feedback_actions_since_submission"][0][
                "comment"
            ],
            "Please clarify the collection frequency.",
        )

    def test_review_context_exposes_collection_update_contract_for_owner_only(self):
        """Only owners receive programmatic collection update hints in context."""
        url = reverse(
            "object_management:api_review_context",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )

        self.client.force_login(self.owner)
        owner_response = self.client.get(url)
        self.assertEqual(owner_response.status_code, 200)
        owner_context = owner_response.json()["context"]["collection_update"]
        self.assertTrue(owner_context["available"])
        self.assertEqual(
            owner_context["expected_identity"]["expected_publication_status"],
            self.review_collection.publication_status,
        )
        self.assertEqual(
            owner_context["expected_identity"]["expected_waste_category_id"],
            None,
        )
        self.assertIn("description", owner_context["mutable_fields"])
        self.assertIn("comments", owner_context["mutable_fields"])
        self.assertEqual(
            owner_context["update_url"],
            reverse(
                "api-waste-collection-update",
                kwargs={"pk": self.review_collection.pk},
            ),
        )

        self.client.force_login(self.moderator)
        moderator_response = self.client.get(url)
        self.assertEqual(moderator_response.status_code, 200)
        moderator_context = moderator_response.json()["context"]["collection_update"]
        self.assertFalse(moderator_context["available"])

    def test_review_context_rejects_invalid_history_limit(self):
        """history_limit must be parseable as integer."""
        url = reverse(
            "object_management:api_review_context",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )
        self.client.force_login(self.moderator)

        response = self.client.get(url, data={"history_limit": "invalid"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "history_limit must be an integer.",
        )

    def test_review_context_forbids_regular_user(self):
        """Non-moderators cannot access context for others' review items."""
        url = reverse(
            "object_management:api_review_context",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )
        self.client.force_login(self.regular_user)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_review_context_returns_404_for_stale_content_type(self):
        """Stale content types are handled as not found instead of raising ValueError."""
        stale_content_type = ContentType.objects.create(
            app_label="missing_app",
            model="missing_model",
        )
        url = reverse(
            "object_management:api_review_context",
            kwargs={
                "content_type_id": stale_content_type.id,
                "object_id": self.review_collection.id,
            },
        )
        self.client.force_login(self.moderator)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_review_context_includes_sources(self):
        """Context payload includes serialized sources from the object."""
        source = Source.objects.create(
            title="Test Source",
            abbreviation="TS2024",
            url="https://example.com/report.pdf",
            url_valid=False,
            url_checked=date(2026, 3, 24),
            year=2024,
            type="article",
        )
        self.review_collection.sources.add(source)

        url = reverse(
            "object_management:api_review_context",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )
        self.client.force_login(self.moderator)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        ctx = response.json()["context"]
        self.assertIn("sources", ctx)
        self.assertEqual(len(ctx["sources"]), 1)
        self.assertEqual(ctx["sources"][0]["title"], "Test Source")
        self.assertEqual(ctx["sources"][0]["url"], "https://example.com/report.pdf")
        self.assertFalse(ctx["sources"][0]["url_valid"])
        self.assertEqual(ctx["sources"][0]["url_checked"], "2026-03-24")
        self.assertTrue(ctx["sources"][0]["url_valid_is_advisory"])

    def test_review_context_includes_related_display(self):
        """Context payload includes human-readable FK display strings."""
        url = reverse(
            "object_management:api_review_context",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )
        self.client.force_login(self.moderator)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        ctx = response.json()["context"]
        self.assertIn("related_display", ctx)
        self.assertIn("owner", ctx["related_display"])

    def test_review_context_includes_flyers_for_collection(self):
        """Context payload includes flyers section for Collection items."""
        flyer = WasteFlyer.objects.create(
            owner=self.owner,
            url="https://example.com/flyer.pdf",
            url_valid=False,
            url_checked=date(2026, 3, 24),
        )
        self.review_collection.flyers.add(flyer)

        url = reverse(
            "object_management:api_review_context",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )
        self.client.force_login(self.moderator)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        ctx = response.json()["context"]
        self.assertIn("flyers", ctx)
        self.assertEqual(len(ctx["flyers"]), 1)
        self.assertEqual(ctx["flyers"][0]["url"], "https://example.com/flyer.pdf")
        self.assertFalse(ctx["flyers"][0]["url_valid"])
        self.assertEqual(ctx["flyers"][0]["url_checked"], "2026-03-24")
        self.assertTrue(ctx["flyers"][0]["url_valid_is_advisory"])

    def test_review_context_includes_normalized_frequency_display(self):
        url = reverse(
            "object_management:api_review_context",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )
        self.client.force_login(self.moderator)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        ctx = response.json()["context"]
        self.assertIn("frequency_display", ctx)
        self.assertEqual(
            ctx["frequency_display"]["canonical_label"], "Seasonal flexibility"
        )
        self.assertEqual(ctx["frequency_display"]["type"], "Fixed-Seasonal")
        self.assertEqual(len(ctx["frequency_display"]["rows"]), 2)
        self.assertEqual(
            ctx["frequency_display"]["rows"][0]["segment"], "January to June"
        )
        self.assertEqual(ctx["frequency_display"]["rows"][0]["standard"], "Weekly")
        self.assertEqual(
            ctx["frequency_display"]["rows"][1]["standard"], "Every 2 weeks"
        )

    def test_review_context_does_not_include_review_guidance(self):
        """BRIT context payload contains only domain data; guidance is assembled by MCP."""
        url = reverse(
            "object_management:api_review_context",
            kwargs={
                "content_type_id": self.content_type_id,
                "object_id": self.review_collection.id,
            },
        )
        self.client.force_login(self.moderator)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("review_guidance", response.json()["context"])

    def test_review_queue_includes_tracking_fields(self):
        """Queue items include my_last_comment_at and lastmodified_at."""
        url = reverse("object_management:api_review_queue")
        self.client.force_login(self.moderator)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertTrue(len(results) > 0)
        first = results[0]
        self.assertIn("my_last_comment_at", first)
        self.assertIn("lastmodified_at", first)

    def test_review_queue_my_last_comment_at_reflects_comments(self):
        """my_last_comment_at is set after the moderator posts a comment."""
        url = reverse("object_management:api_review_queue")
        self.client.force_login(self.moderator)

        response = self.client.get(url)
        item = next(
            i
            for i in response.json()["results"]
            if i["object_id"] == self.review_collection.id
        )
        self.assertIsNone(item["my_last_comment_at"])

        ReviewAction.objects.create(
            content_type_id=self.content_type_id,
            object_id=self.review_collection.id,
            action=ReviewAction.ACTION_COMMENT,
            comment="Review note",
            user=self.moderator,
        )

        response = self.client.get(url)
        item = next(
            i
            for i in response.json()["results"]
            if i["object_id"] == self.review_collection.id
        )
        self.assertIsNotNone(item["my_last_comment_at"])


class ReviewContextCPVEnrichmentTests(TestCase):
    """Validate CPV-specific enrichments in the review context API."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="cpv_owner")
        cls.moderator = User.objects.create_user(username="cpv_moderator")

        collection_ct = ContentType.objects.get_for_model(Collection)
        cpv_ct = ContentType.objects.get_for_model(CollectionPropertyValue)

        for ct in (collection_ct, cpv_ct):
            perm, _ = Permission.objects.get_or_create(
                codename=f"can_moderate_{ct.model}",
                content_type=ct,
                defaults={"name": f"Can moderate {ct.model}"},
            )
            cls.moderator.user_permissions.add(perm)

        cls.unit = Unit.objects.create(
            name="tonnes", symbol="t", publication_status="published"
        )
        cls.prop = Property.objects.create(
            name="total waste collected", unit="t", publication_status="published"
        )
        cls.prop.allowed_units.add(cls.unit)

        with mute_signals(post_save, pre_save):
            cls.collection = Collection.objects.create(
                name="CPV Test Collection",
                owner=cls.owner,
                publication_status="published",
            )

        cls.cpv_2020 = CollectionPropertyValue.objects.create(
            collection=cls.collection,
            property=cls.prop,
            unit=cls.unit,
            year=2020,
            average=100.0,
            owner=cls.owner,
            publication_status="published",
        )
        cls.cpv_2021 = CollectionPropertyValue.objects.create(
            collection=cls.collection,
            property=cls.prop,
            unit=cls.unit,
            year=2021,
            average=105.0,
            owner=cls.owner,
            publication_status=UserCreatedObject.STATUS_REVIEW,
        )
        cls.cpv_ct_id = cpv_ct.id

    def test_context_includes_value_timeline_for_non_derived_cpv(self):
        """Non-derived CPV context includes timeline of sibling values."""
        url = reverse(
            "object_management:api_review_context",
            kwargs={
                "content_type_id": self.cpv_ct_id,
                "object_id": self.cpv_2021.id,
            },
        )
        self.client.force_login(self.moderator)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        ctx = response.json()["context"]
        self.assertIn("value_timeline", ctx)
        self.assertEqual(len(ctx["value_timeline"]), 1)
        self.assertEqual(ctx["value_timeline"][0]["year"], 2020)
        self.assertEqual(ctx["value_timeline"][0]["average"], 100.0)

    def test_context_includes_parent_collection(self):
        """CPV context includes parent collection with name and sources."""
        url = reverse(
            "object_management:api_review_context",
            kwargs={
                "content_type_id": self.cpv_ct_id,
                "object_id": self.cpv_2021.id,
            },
        )
        self.client.force_login(self.moderator)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        ctx = response.json()["context"]
        self.assertIn("parent_collection", ctx)
        self.assertEqual(ctx["parent_collection"]["id"], self.collection.id)
        self.assertEqual(ctx["parent_collection"]["name"], str(self.collection))

    def test_context_excludes_timeline_for_derived_cpv(self):
        """Derived CPVs do not get a value_timeline in the context."""
        derived_cpv = CollectionPropertyValue.objects.create(
            collection=self.collection,
            property=self.prop,
            unit=self.unit,
            year=2021,
            average=50.0,
            owner=self.owner,
            is_derived=True,
            publication_status=UserCreatedObject.STATUS_REVIEW,
        )
        url = reverse(
            "object_management:api_review_context",
            kwargs={
                "content_type_id": self.cpv_ct_id,
                "object_id": derived_cpv.id,
            },
        )
        self.client.force_login(self.moderator)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        ctx = response.json()["context"]
        self.assertNotIn("value_timeline", ctx)
        self.assertIn("parent_collection", ctx)

    def test_context_does_not_include_cpv_review_guidance(self):
        """CPV context payload contains only domain data; guidance is assembled by MCP."""
        url = reverse(
            "object_management:api_review_context",
            kwargs={
                "content_type_id": self.cpv_ct_id,
                "object_id": self.cpv_2021.id,
            },
        )
        self.client.force_login(self.moderator)

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("review_guidance", response.json()["context"])
