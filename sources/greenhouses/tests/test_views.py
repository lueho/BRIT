from django.test import SimpleTestCase
from django.urls import reverse

from distributions.models import TemporalDistribution, Timestep
from materials.models import (
    Composition,
    Material,
    MaterialComponentGroup,
    Sample,
    SampleSeries,
)
from utils.tests.testcases import AbstractTestCases, ViewWithPermissionsTestCase

from ..models import Culture, Greenhouse, GreenhouseGrowthCycle, GrowthTimeStepSet
from ..viewsets import NantesGreenhousesViewSet


class NantesGreenhousesViewSetTestCase(SimpleTestCase):
    def test_list_queryset_has_deterministic_ordering(self):
        self.assertEqual(NantesGreenhousesViewSet.queryset.query.order_by, ("pk",))


class CultureCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    dashboard_view = False
    add_scope_query_param_to_list_urls = True

    model = Culture

    view_create_name = "culture-create"
    view_published_list_name = "culture-list"
    view_private_list_name = "culture-list-owned"
    view_detail_name = "culture-detail"
    view_update_name = "culture-update"
    view_delete_name = "culture-delete-modal"

    create_object_data = {
        "name": "Test Culture",
        "description": "Test Description",
    }
    update_object_data = {
        "name": "Updated Test Culture",
        "description": "Updated Description",
    }

    @classmethod
    def create_related_objects(cls):
        material = Material.objects.create(
            name="Test Material", publication_status="published"
        )
        return {
            "residue": SampleSeries.objects.create(
                name="Test Residue", material=material, publication_status="published"
            ),
        }


class GreenhouseCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    dashboard_view = False
    public_list_view = False
    add_scope_query_param_to_list_urls = True

    model = Greenhouse

    view_create_name = "greenhouse-create"
    view_published_list_name = "greenhouse-list"
    view_private_list_name = "greenhouse-list-owned"
    view_detail_name = "greenhouse-detail"
    view_update_name = "greenhouse-update"
    view_delete_name = "greenhouse-delete-modal"

    create_object_data = {"name": "Test Greenhouse"}
    update_object_data = {"name": "Updated Test Greenhouse"}


class GrowthCycleCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    dashboard_view = False
    public_list_view = False
    private_list_view = False
    create_view = False  # TODO: Check whether a create view is necessary

    model = GreenhouseGrowthCycle

    view_create_name = "greenhousegrowthcycle-create"
    view_detail_name = "greenhousegrowthcycle-detail"
    view_update_name = "greenhousegrowthcycle-update"
    view_delete_name = "greenhousegrowthcycle-delete-modal"

    create_object_data = {"cycle_number": 1}
    update_object_data = {"cycle_number": 2}

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        distribution = TemporalDistribution.objects.create(name="Test Distribution")
        timestep = Timestep.objects.create(
            name="Test Timestep", distribution=distribution
        )
        GrowthTimeStepSet.objects.create(
            owner=cls.owner_user, growth_cycle=cls.published_object, timestep=timestep
        )
        GrowthTimeStepSet.objects.create(
            owner=cls.owner_user, growth_cycle=cls.unpublished_object, timestep=timestep
        )

    @classmethod
    def create_related_objects(cls):
        material = Material.objects.create(
            name="Test Material", publication_status="published"
        )
        sample = Sample.objects.create(
            owner=cls.owner_user,
            name="Published Test Sample",
            material=material,
            publication_status="published",
        )
        group = MaterialComponentGroup.objects.create(
            name="Test Group", publication_status="published"
        )
        return {
            "culture": Culture.objects.create(
                name="Test Culture", publication_status="published"
            ),
            "greenhouse": Greenhouse.objects.create(
                owner=cls.owner_user,
                name="Test Greenhouse",
                publication_status="published",
            ),
            "group_settings": Composition.objects.create(
                name="Test Composition",
                group=group,
                sample=sample,
                publication_status="published",
            ),
        }

    def get_update_success_url(self, pk=None):
        return reverse(
            "greenhouse-detail", kwargs={"pk": self.related_objects["greenhouse"].pk}
        )

    def get_delete_success_url(self, publication_status=None):
        return reverse(
            "greenhouse-detail", kwargs={"pk": self.related_objects["greenhouse"].pk}
        )


class GrowthCycleModalCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "add_greenhousegrowthcycle"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.greenhouse = Greenhouse.objects.create(owner=cls.member, name="Greenhouse")
        material = Material.objects.create(name="Crop residue")
        cls.residue = SampleSeries.objects.create(
            owner=cls.member, material=material, name="Residue"
        )
        cls.sample = cls.residue.samples.get(timestep=Timestep.objects.default())
        cls.base_composition = cls.sample.compositions.get(
            group=MaterialComponentGroup.objects.default()
        )
        cls.culture = Culture.objects.create(
            owner=cls.member, name="Crop", residue=cls.residue
        )
        distribution, _ = TemporalDistribution.objects.get_or_create(
            name="Months of the year"
        )
        cls.timestep, _ = Timestep.objects.get_or_create(
            name="January", distribution=distribution
        )

    def setUp(self):
        super().setUp()
        self.client.force_login(self.member)
        self.url = reverse(
            "greenhousegrowthcycle-create", kwargs={"pk": self.greenhouse.pk}
        )
        self.data = {"culture": self.culture.pk, "timesteps": [self.timestep.pk]}

    def assert_cycle_created(self, response, composition):
        self.assertRedirects(
            response, self.greenhouse.get_absolute_url(), fetch_redirect_response=False
        )
        cycle = GreenhouseGrowthCycle.objects.get(greenhouse=self.greenhouse)
        self.assertEqual(cycle.culture, self.culture)
        self.assertEqual(cycle.group_settings, composition)
        self.assertEqual(cycle.owner, self.member)
        self.assertEqual(list(cycle.timesteps), [self.timestep])
        self.assertEqual(cycle.cycle_number, 1)

    def test_missing_greenhouse_returns_404(self):
        missing_pk = self.greenhouse.pk + 1
        url = reverse("greenhousegrowthcycle-create", kwargs={"pk": missing_pk})
        response = self.client.post(url, self.data)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(GreenhouseGrowthCycle.objects.exists())

    def test_missing_macro_components_group_uses_default_composition(self):
        MaterialComponentGroup.objects.filter(name="Macro Components").delete()

        response = self.client.post(self.url, self.data)

        self.assert_cycle_created(response, self.base_composition)

    def test_macro_components_composition_is_preferred(self):
        group = MaterialComponentGroup.objects.create(name="Macro Components")
        composition = Composition.objects.create(
            owner=self.member, group=group, sample=self.sample
        )

        response = self.client.post(self.url, self.data)

        self.assert_cycle_created(response, composition)

    def test_missing_macro_composition_uses_default_composition(self):
        MaterialComponentGroup.objects.create(name="Macro Components")

        response = self.client.post(self.url, self.data)

        self.assert_cycle_created(response, self.base_composition)

    def test_missing_composition_returns_form_error_without_creating_cycle(self):
        Composition.objects.filter(sample__series=self.residue).delete()

        response = self.client.post(self.url, self.data)

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "culture",
            "The selected culture's residue has no Macro Components or default composition.",
        )
        self.assertFalse(GreenhouseGrowthCycle.objects.exists())
        self.assertFalse(GrowthTimeStepSet.objects.exists())

    def test_missing_residue_returns_form_error_without_creating_cycle(self):
        self.culture.residue = None
        self.culture.save()

        response = self.client.post(self.url, self.data)

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"], "culture", "The selected culture has no residue."
        )
        self.assertFalse(GreenhouseGrowthCycle.objects.exists())

    def test_ajax_validation_does_not_create_cycle(self):
        response = self.client.post(
            self.url, self.data, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(GreenhouseGrowthCycle.objects.exists())

    def test_get_forbidden_on_foreign_greenhouse(self):
        foreign = Greenhouse.objects.create(owner=self.owner, name="Foreign greenhouse")
        url = reverse("greenhousegrowthcycle-create", kwargs={"pk": foreign.pk})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

    def test_post_forbidden_on_foreign_greenhouse(self):
        foreign = Greenhouse.objects.create(owner=self.owner, name="Foreign greenhouse")
        url = reverse("greenhousegrowthcycle-create", kwargs={"pk": foreign.pk})

        response = self.client.post(url, self.data)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(GreenhouseGrowthCycle.objects.exists())

    def test_post_forbidden_on_own_published_greenhouse(self):
        self.greenhouse.publication_status = "published"
        self.greenhouse.save()

        response = self.client.post(self.url, self.data)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(GreenhouseGrowthCycle.objects.exists())

    def test_staff_can_add_cycle_to_published_greenhouse(self):
        self.greenhouse.publication_status = "published"
        self.greenhouse.save()
        self.culture.publication_status = "published"
        self.culture.save()
        self.base_composition.publication_status = "published"
        self.base_composition.save()
        self.client.force_login(self.staff)

        response = self.client.post(self.url, self.data)

        self.assertRedirects(
            response, self.greenhouse.get_absolute_url(), fetch_redirect_response=False
        )
        cycle = GreenhouseGrowthCycle.objects.get(greenhouse=self.greenhouse)
        self.assertEqual(cycle.owner, self.staff)
        self.assertEqual(cycle.group_settings, self.base_composition)

    def test_culture_field_excludes_foreign_private_cultures(self):
        foreign_culture = Culture.objects.create(
            owner=self.owner, name="Foreign culture", residue=self.residue
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        culture_queryset = response.context["form"].fields["culture"].queryset
        self.assertIn(self.culture, culture_queryset)
        self.assertNotIn(foreign_culture, culture_queryset)

    def test_post_rejects_foreign_private_culture(self):
        foreign_culture = Culture.objects.create(
            owner=self.owner, name="Foreign culture", residue=self.residue
        )
        data = {"culture": foreign_culture.pk, "timesteps": [self.timestep.pk]}

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(GreenhouseGrowthCycle.objects.exists())

    def test_foreign_private_composition_is_not_selected(self):
        group = MaterialComponentGroup.objects.create(name="Macro Components")
        Composition.objects.create(owner=self.owner, group=group, sample=self.sample)

        response = self.client.post(self.url, self.data)

        self.assert_cycle_created(response, self.base_composition)

    def test_published_greenhouse_rejects_unpublished_culture(self):
        self.greenhouse.publication_status = "published"
        self.greenhouse.save()
        self.client.force_login(self.staff)

        response = self.client.post(self.url, self.data)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(GreenhouseGrowthCycle.objects.exists())


class GreenhouseUpdateViewPermissionTestCase(ViewWithPermissionsTestCase):
    """#209: GreenhouseUpdateView must require change_greenhouse permission."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.greenhouse = Greenhouse.objects.create(
            owner=cls.owner, name="Test Greenhouse", publication_status="private"
        )

    def test_get_http_403_for_owner_without_change_permission(self):
        self.client.force_login(self.owner)
        url = reverse("greenhouse-update", kwargs={"pk": self.greenhouse.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_for_owner_with_change_permission(self):
        from django.contrib.auth.models import Permission

        perm = Permission.objects.get(codename="change_greenhouse")
        self.owner.user_permissions.add(perm)
        self.client.force_login(self.owner)
        url = reverse("greenhouse-update", kwargs={"pk": self.greenhouse.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_for_staff_without_explicit_permission(self):
        self.client.force_login(self.staff)
        url = reverse("greenhouse-update", kwargs={"pk": self.greenhouse.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class GreenhouseDetailPermissionRegressionTest(ViewWithPermissionsTestCase):
    member_permissions = "add_greenhousegrowthcycle"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.published_greenhouse = Greenhouse.objects.create(
            owner=cls.owner,
            name="Published greenhouse",
            publication_status="published",
        )
        cls.own_greenhouse = Greenhouse.objects.create(
            owner=cls.member, name="Own greenhouse"
        )
        cls.own_published_greenhouse = Greenhouse.objects.create(
            owner=cls.member,
            name="Own published greenhouse",
            publication_status="published",
        )

    def test_detail_shows_add_growth_cycle_link_on_own_greenhouse(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("greenhouse-detail", kwargs={"pk": self.own_greenhouse.pk})
        )

        self.assertContains(
            response,
            reverse(
                "greenhousegrowthcycle-create", kwargs={"pk": self.own_greenhouse.pk}
            ),
        )

    def test_detail_hides_add_growth_cycle_link_on_foreign_greenhouse(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("greenhouse-detail", kwargs={"pk": self.published_greenhouse.pk})
        )

        self.assertNotContains(
            response,
            reverse(
                "greenhousegrowthcycle-create",
                kwargs={"pk": self.published_greenhouse.pk},
            ),
        )

    def test_detail_hides_add_growth_cycle_link_on_own_published_greenhouse(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse(
                "greenhouse-detail", kwargs={"pk": self.own_published_greenhouse.pk}
            )
        )

        self.assertNotContains(
            response,
            reverse(
                "greenhousegrowthcycle-create",
                kwargs={"pk": self.own_published_greenhouse.pk},
            ),
        )

    def test_detail_shows_add_growth_cycle_link_for_staff(self):
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("greenhouse-detail", kwargs={"pk": self.published_greenhouse.pk})
        )

        self.assertContains(
            response,
            reverse(
                "greenhousegrowthcycle-create",
                kwargs={"pk": self.published_greenhouse.pk},
            ),
        )

    def test_detail_hides_add_growth_cycle_link_without_permission(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("greenhouse-detail", kwargs={"pk": self.published_greenhouse.pk})
        )

        self.assertNotContains(
            response,
            reverse(
                "greenhousegrowthcycle-create",
                kwargs={"pk": self.published_greenhouse.pk},
            ),
        )
