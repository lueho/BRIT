from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from distributions.models import TemporalDistribution, Timestep
from sources.waste_collection.models import (
    CollectionCountOptions,
    CollectionFrequency,
    CollectionSeason,
)


class CollectionCountOptionsReviewDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create(username="count-options-owner")
        cls.staff = User.objects.create(username="count-options-staff", is_staff=True)
        cls.moderator = User.objects.create(username="count-options-moderator")
        cls.outsider = User.objects.create(username="count-options-outsider")
        content_type = ContentType.objects.get_for_model(CollectionCountOptions)
        permission, _ = Permission.objects.get_or_create(
            content_type=content_type,
            codename="can_moderate_collectioncountoptions",
            defaults={"name": "Can moderate collection count options"},
        )
        cls.moderator.user_permissions.add(permission)
        frequency = CollectionFrequency.objects.create(
            name="Seasonal review schedule", owner=cls.owner
        )
        season = CollectionSeason.objects.create(
            distribution=TemporalDistribution.objects.get(name="Months of the year"),
            first_timestep=Timestep.objects.get(name="January"),
            last_timestep=Timestep.objects.get(name="May"),
            owner=cls.owner,
        )
        cls.options = CollectionCountOptions.objects.create(
            frequency=frequency,
            season=season,
            standard=12,
            option_1=0,
            option_2=24,
            option_3=None,
            owner=cls.owner,
            publication_status="review",
        )
        cls.url = reverse(
            "object_management:review_item_detail",
            kwargs={"content_type_id": content_type.pk, "object_id": cls.options.pk},
        )

    def test_review_detail_renders_fields_in_shared_review_shell(self):
        for user in (self.owner, self.staff, self.moderator):
            with self.subTest(user=user):
                self.client.force_login(user)
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(
                    response, "waste_collection/collectioncountoptions_detail.html"
                )
                self.assertTemplateUsed(response, "object_management/review_panel.html")
                for label, value in (
                    ("Frequency", "Seasonal review schedule"),
                    ("Season", "January - May"),
                    ("Standard", "12"),
                    ("Option 1", "0"),
                    ("Option 2", "24"),
                    ("Option 3", "Not specified"),
                    ("Owner", "count-options-owner"),
                ):
                    self.assertContains(
                        response,
                        f'<dt class="col-sm-3">{label}</dt>'
                        f'<dd class="col-sm-9">{value}</dd>',
                        html=True,
                    )
                self.assertNotContains(response, "Collection count optionss")

    def test_model_labels_use_correct_plural(self):
        self.assertEqual(
            CollectionCountOptions._meta.verbose_name, "collection count options"
        )
        self.assertEqual(
            CollectionCountOptions._meta.verbose_name_plural, "collection count options"
        )

    def test_review_detail_distinguishes_zero_from_unspecified_for_every_count(self):
        self.client.force_login(self.staff)
        for value, display in ((0, "0"), (None, "Not specified")):
            with self.subTest(value=value):
                CollectionCountOptions.objects.filter(pk=self.options.pk).update(
                    standard=value, option_1=value, option_2=value, option_3=value
                )
                response = self.client.get(self.url)
                for label in ("Standard", "Option 1", "Option 2", "Option 3"):
                    self.assertContains(
                        response,
                        f'<dt class="col-sm-3">{label}</dt>'
                        f'<dd class="col-sm-9">{display}</dd>',
                        html=True,
                    )

    def test_review_detail_remains_restricted(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.outsider)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
