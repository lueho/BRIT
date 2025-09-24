from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from materials.models import MaterialProperty, MaterialPropertyValue
from utils.object_management import publication
from utils.object_management.models import UserCreatedObject


class PublicationUtilitiesTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="owner", password="pw")

        default_username = getattr(
            settings,
            "DEFAULT_OBJECT_OWNER_USERNAME",
            getattr(settings, "ADMIN_USERNAME", None),
        )
        if default_username and not user_model.objects.filter(
            username=default_username
        ).exists():
            user_model.objects.create_user(username=default_username, password="pw")

        self.property = MaterialProperty.objects.create(
            name="Total carbon",
            owner=self.owner,
            unit="%",
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )
        self.property_value = MaterialPropertyValue.objects.create(
            name="Total carbon value",
            owner=self.owner,
            property=self.property,
            average=10.0,
            standard_deviation=0.5,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )

    def test_prepublish_check_blocks_unpublished_dependencies(self):
        report = publication.prepublish_check(
            self.property_value, target_status=UserCreatedObject.STATUS_REVIEW
        )
        self.assertTrue(report.blocking)

        self.property.publication_status = UserCreatedObject.STATUS_PUBLISHED
        self.property.save(update_fields=["publication_status"])

        report = publication.prepublish_check(
            self.property_value, target_status=UserCreatedObject.STATUS_REVIEW
        )
        self.assertFalse(report.blocking)

    def test_cascade_publication_status_updates_children(self):
        registry_key = ("materials", "materialproperty")
        original_config = publication.REGISTRY.get(registry_key)

        def restore_registry():
            if original_config is None:
                publication.REGISTRY.pop(registry_key, None)
            else:
                publication.REGISTRY[registry_key] = original_config

        publication.REGISTRY[registry_key] = publication.DependencyConfig(
            follows_parent=(publication.RelationRule("materialpropertyvalue_set"),)
        )
        self.addCleanup(restore_registry)

        self.property.publication_status = UserCreatedObject.STATUS_REVIEW
        self.property.save(update_fields=["publication_status"])
        self.property_value.publication_status = UserCreatedObject.STATUS_PRIVATE
        self.property_value.save(update_fields=["publication_status"])

        publication.cascade_publication_status(
            self.property, UserCreatedObject.STATUS_REVIEW
        )
        self.property_value.refresh_from_db()
        self.assertEqual(
            self.property_value.publication_status, UserCreatedObject.STATUS_REVIEW
        )


class PublicationChecklistViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="check-owner", password="pw")

        default_username = getattr(
            settings,
            "DEFAULT_OBJECT_OWNER_USERNAME",
            getattr(settings, "ADMIN_USERNAME", None),
        )
        if default_username and not user_model.objects.filter(
            username=default_username
        ).exists():
            user_model.objects.create_user(username=default_username, password="pw")

        self.property = MaterialProperty.objects.create(
            name="Nitrogen",
            owner=self.owner,
            unit="%",
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )
        self.property_value = MaterialPropertyValue.objects.create(
            name="Nitrogen value",
            owner=self.owner,
            property=self.property,
            average=2.5,
            standard_deviation=0.2,
            publication_status=UserCreatedObject.STATUS_PRIVATE,
        )

    def test_checklist_displays_blocking_dependencies(self):
        self.client.force_login(self.owner)
        url = reverse(
            "object_management:publication_checklist",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(
                    self.property_value.__class__
                ).pk,
                "object_id": self.property_value.pk,
            },
        )

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        blocking = response.context["blocking_issues"]
        self.assertTrue(blocking)

        self.property.publication_status = UserCreatedObject.STATUS_PUBLISHED
        self.property.save(update_fields=["publication_status"])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["blocking_issues"])
