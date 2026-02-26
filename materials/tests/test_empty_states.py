from uuid import uuid4

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from materials.models import (
    AnalyticalMethod,
    Material,
    MaterialCategory,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialProperty,
    Sample,
    SampleSeries,
)


class EmptyStateViewsTestCase(TestCase):
    """Test empty state messaging and CTAs across Materials views."""

    def setUp(self):
        self.regular_user = User.objects.create_user(
            username="regular", password="test123"
        )
        self.staff_user = User.objects.create_user(
            username="staff", password="test123", is_staff=True
        )

        # Grant create permissions to staff user for testing CTAs
        content_types = {
            "material": ContentType.objects.get_for_model(Material),
            "sample": ContentType.objects.get_for_model(Sample),
            "sampleseries": ContentType.objects.get_for_model(SampleSeries),
            "materialcategory": ContentType.objects.get_for_model(MaterialCategory),
            "materialcomponent": ContentType.objects.get_for_model(MaterialComponent),
            "materialcomponentgroup": ContentType.objects.get_for_model(
                MaterialComponentGroup
            ),
            "materialproperty": ContentType.objects.get_for_model(MaterialProperty),
            "analyticalmethod": ContentType.objects.get_for_model(AnalyticalMethod),
        }

        for model_name, ct in content_types.items():
            perm, _ = Permission.objects.get_or_create(
                codename=f"add_{model_name}",
                content_type=ct,
            )
            self.staff_user.user_permissions.add(perm)

    def _create_unused_category(self):
        """Create a category that is guaranteed not to be assigned to materials in this test."""
        return MaterialCategory.objects.create(
            name=f"unused-category-{uuid4()}",
            owner=self.staff_user,
            publication_status="published",
        )

    def test_material_list_empty_anonymous_shows_login_hint(self):
        """Anonymous users see generic options hint but no create CTA."""
        category = self._create_unused_category()
        response = self.client.get(
            reverse("material-list") + f"?scope=published&category={category.pk}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No items match your current filters.")
        self.assertContains(response, "Reset filters")
        self.assertContains(response, "Log in to enable export and additional options.")
        self.assertNotContains(response, "Create new material")

    def test_material_list_empty_staff_shows_create_cta(self):
        """Staff users with create permission see create CTA in options pane."""
        self.client.force_login(self.staff_user)
        category = self._create_unused_category()
        response = self.client.get(
            reverse("material-list-owned") + f"?scope=private&category={category.pk}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No items match your current filters.")
        self.assertContains(response, "Reset filters")
        self.assertContains(response, "Create new material")
        self.assertNotContains(response, "Log in to create")

    def test_material_list_empty_regular_no_create_cta(self):
        """Regular users without create permission don't see create CTA."""
        self.client.force_login(self.regular_user)
        category = self._create_unused_category()
        response = self.client.get(
            reverse("material-list-owned") + f"?scope=private&category={category.pk}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No items match your current filters.")
        self.assertContains(response, "Reset filters")
        self.assertNotContains(response, "Create your first material")
        self.assertNotContains(response, "Log in to create")

    def test_sample_detail_empty_properties_anonymous(self):
        """Anonymous users see login hint for empty properties section."""
        sample = Sample.objects.create(
            name="Test Sample",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )
        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "No properties recorded. Log in to add properties."
        )

    def test_sample_detail_empty_properties_owner_sees_actionable_message(self):
        """Sample owners see actionable empty-state message for properties."""
        sample = Sample.objects.create(
            name="Test Sample",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.regular_user,
            publication_status="published",
        )
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "No properties recorded. Add your first property."
        )

    def test_sample_detail_shows_default_composition(self):
        """New samples include a default composition instead of an empty-state message."""
        sample = Sample.objects.create(
            name="Test Sample",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )
        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "No compositions available")

    def test_analytical_method_list_empty_anonymous(self):
        """Anonymous users see login hint in empty analytical method list."""
        response = self.client.get(
            reverse("analyticalmethod-list") + "?scope=published&name=no-match-token"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No items match your current filters.")
        self.assertContains(response, "Log in to create new analytical methods.")

    def test_analytical_method_list_empty_staff_shows_create_cta(self):
        """Staff users see create CTA in empty analytical method list."""
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("analyticalmethod-list-owned")
            + "?scope=private&name=no-match-token"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Create your first analytical method to get started."
        )

    def test_reset_filter_link_preserves_scope(self):
        """Reset filter links preserve current scope correctly."""
        # Test different scopes
        scopes = ["published", "private", "review"]
        for scope in scopes:
            with self.subTest(scope=scope):
                self.client.force_login(self.staff_user)
                url = reverse("material-list") + f"?scope={scope}"
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

                # Check that reset link points to correct scope
                expected_reset_url = f"?scope={scope}"
                self.assertContains(response, expected_reset_url)

    def test_empty_state_with_existing_reset_behavior(self):
        """Ensure empty states don't break existing reset filter functionality."""
        # Create a material to test with non-empty list first
        Material.objects.create(
            name="Test Material",
            type="material",
            owner=self.staff_user,
            publication_status="published",
        )

        empty_category = self._create_unused_category()

        # Test with filter that returns no results
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("material-list") + f"?scope=published&category={empty_category.pk}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No items match your current filters.")
        self.assertContains(response, "Reset filters")

        # Verify reset link works by following it
        reset_url = reverse("material-list") + "?scope=published"
        response = self.client.get(reset_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Material")  # Should show the material again
