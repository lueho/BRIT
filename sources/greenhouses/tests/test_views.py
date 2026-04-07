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


class GreenhouseDetailPermissionRegressionTest(ViewWithPermissionsTestCase):
    member_permissions = "add_greenhousegrowthcycle"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.greenhouse = Greenhouse.objects.create(
            owner=cls.owner,
            name="Published greenhouse",
            publication_status="published",
        )

    def test_detail_shows_add_growth_cycle_link_for_user_with_permission(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("greenhouse-detail", kwargs={"pk": self.greenhouse.pk})
        )

        self.assertContains(
            response,
            reverse("greenhousegrowthcycle-create", kwargs={"pk": self.greenhouse.pk}),
        )

    def test_detail_hides_add_growth_cycle_link_without_permission(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("greenhouse-detail", kwargs={"pk": self.greenhouse.pk})
        )

        self.assertNotContains(
            response,
            reverse("greenhousegrowthcycle-create", kwargs={"pk": self.greenhouse.pk}),
        )
