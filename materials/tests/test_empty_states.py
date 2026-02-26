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
        self.anonymous_user = None
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

    def test_material_list_empty_anonymous_shows_login_hint(self):
        """Anonymous users see login hint in empty material list."""
        response = self.client.get(reverse("material-list") + "?scope=published")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No items match your current filters.")
        self.assertContains(response, "Reset filters")
        self.assertContains(response, "Log in to create new materials.")
        self.assertNotContains(response, "Create your first material")

    def test_material_list_empty_staff_shows_create_cta(self):
        """Staff users with create permission see create CTA in empty material list."""
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("material-list-owned") + "?scope=private")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No items match your current filters.")
        self.assertContains(response, "Reset filters")
        self.assertContains(response, "Create your first material to get started.")
        self.assertNotContains(response, "Log in to create")

    def test_material_list_empty_regular_no_create_cta(self):
        """Regular users without create permission don't see create CTA."""
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse("material-list-owned") + "?scope=private")
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

    def test_sample_detail_empty_properties_with_permission(self):
        """Users with add property permission see actionable message."""
        sample = Sample.objects.create(
            name="Test Sample",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )
        # Grant add property permission
        perm = Permission.objects.get(
            codename="add_materialpropertyvalue",
            content_type=ContentType.objects.get_for_model(Material),
        )
        self.staff_user.user_permissions.add(perm)

        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "No properties recorded. Add your first property."
        )

    def test_sample_detail_empty_compositions_anonymous(self):
        """Anonymous users see login hint for empty compositions section."""
        sample = Sample.objects.create(
            name="Test Sample",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )
        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "No compositions available. Log in to create compositions."
        )

    def test_sample_detail_empty_compositions_with_permission(self):
        """Users with manage permission see actionable message."""
        sample = Sample.objects.create(
            name="Test Sample",
            material=Material.objects.create(name="Test Material", type="material"),
            owner=self.staff_user,
            publication_status="published",
        )
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("sample-detail", kwargs={"pk": sample.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "No compositions available. Create your first composition."
        )
        self.assertContains(response, "Add composition")

    def test_analytical_method_list_empty_anonymous(self):
        """Anonymous users see login hint in empty analytical method list."""
        response = self.client.get(
            reverse("analyticalmethod-list") + "?scope=published"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No items match your current filters.")
        self.assertContains(response, "Log in to create new analytical methods.")

    def test_analytical_method_list_empty_staff_shows_create_cta(self):
        """Staff users see create CTA in empty analytical method list."""
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("analyticalmethod-list-owned") + "?scope=private"
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

        # Test with filter that returns no results
        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("material-list") + "?scope=published&name=nonexistent"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No items match your current filters.")
        self.assertContains(response, "Reset filters")

        # Verify reset link works by following it
        reset_url = reverse("material-list") + "?scope=published"
        response = self.client.get(reset_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Material")  # Should show the material again
