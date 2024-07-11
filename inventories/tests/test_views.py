from django.contrib.auth.models import User
from django.urls import reverse

from maps.models import Catchment, Region, GeoDataset
from materials.models import SampleSeries, Material
from utils.tests.testcases import ViewWithPermissionsTestCase
from ..models import Scenario, ScenarioConfiguration, Algorithm, Parameter, ParameterValue


# ----------- Scenario CRUD --------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ScenarioListViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        region = Region.objects.create(name='Test Region')
        catchment = Catchment.objects.create(name='Test Catchment', region=region, parent_region=region)
        Scenario.objects.create(name='Test Scenario', region=region, catchment=catchment)

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('scenario-list'))
        self.assertEqual(200, response.status_code)


class ScenarioCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'add_scenario'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.region = Region.objects.create(name='Test Region')
        cls.catchment = Catchment.objects.create(name='Test Catchment', region=cls.region, parent_region=cls.region)

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('scenario-create')
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('scenario-create'))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('scenario-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('scenario-create')
        response = self.client.post(url, {})
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('scenario-create'))
        self.assertEqual(response.status_code, 200)

    def test_post_success_and_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Test Scenario',
            'region': self.region.pk,
            'catchment': self.catchment.pk
        }
        response = self.client.post(reverse('scenario-create'), data, follow=True)
        created_pk = list(response.context.get('messages'))[0].message
        self.assertRedirects(response, reverse('scenario-detail', kwargs={'pk': created_pk}))


class ScenarioUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'change_scenario'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        region = Region.objects.create(name='Test Region')
        catchment = Catchment.objects.create(name='Test Catchment', region=region, parent_region=region)
        cls.scenario = Scenario.objects.create(
            name='Test Scenario', region=region, catchment=catchment, publication_status='published'
        )

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('scenario-update', kwargs={'pk': self.scenario.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('scenario-update', kwargs={'pk': self.scenario.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('scenario-update', kwargs={'pk': self.scenario.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('scenario-update', kwargs={'pk': self.scenario.pk})
        response = self.client.post(url, {})
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('scenario-update', kwargs={'pk': self.scenario.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_to_success_url_for_member(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Updated Test Scenario',
            'region': self.scenario.region.pk,
            'catchment': self.scenario.catchment.pk
        }
        response = self.client.post(reverse('scenario-update', kwargs={'pk': self.scenario.pk}), data)
        self.assertRedirects(response, reverse('scenario-detail', kwargs={'pk': self.scenario.pk}))


class ScenarioModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = 'delete_scenario'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.scenario = Scenario.objects.create(name='Test Scenario')

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('scenario-delete-modal', kwargs={'pk': self.scenario.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse('scenario-delete-modal', kwargs={'pk': self.scenario.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('scenario-delete-modal', kwargs={'pk': self.scenario.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse('scenario-delete-modal', kwargs={'pk': self.scenario.pk})
        response = self.client.post(url, {})
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse('scenario-delete-modal', kwargs={'pk': self.scenario.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_members(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse('scenario-delete-modal', kwargs={'pk': self.scenario.pk}))
        self.assertRedirects(response, reverse('scenario-list'))
        with self.assertRaises(Scenario.DoesNotExist):
            Scenario.objects.get(pk=self.scenario.pk)


class ScenarioResultDetailViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        region = Region.objects.create(name='Test Region')
        catchment = Catchment.objects.create(name='Test Catchment', region=region, parent_region=region)
        cls.scenario = Scenario.objects.create(name='Test Scenario', region=region, catchment=catchment)

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse('scenario-result', kwargs={'pk': self.scenario.pk}))
        self.assertEqual(response.status_code, 200)


# ----------- Scenario Configuration CRUD ------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class ScenarioConfigurationCreateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['view_scenario', 'view_scenarioconfiguration', 'add_scenarioconfiguration']
    url_name = 'scenarioconfiguration-create'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.owner = User.objects.create_user(username='owner', password='password')
        cls.region = Region.objects.create(name='Test Region')
        cls.catchment = Catchment.objects.create(name='Test Catchment', region=cls.region, parent_region=cls.region)
        cls.scenario = Scenario.objects.create(
            name='Test Scenario',
            owner=cls.owner,
            region=cls.region,
            catchment=cls.catchment)
        cls.feedstock = SampleSeries.objects.create(
            name='Test Feedstock',
            material=Material.objects.create(name='Test Material')
        )
        cls.geodataset = GeoDataset.objects.create(
            name='Test Dataset',
            region=cls.region
        )
        cls.algorithm = Algorithm.objects.create(
            name='Test Algorithm',
            geodataset=cls.geodataset
        )

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse(self.url_name, kwargs={'pk': self.scenario.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse(self.url_name, kwargs={'pk': self.scenario.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse(self.url_name, kwargs={'pk': self.scenario.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse(self.url_name, kwargs={'pk': self.scenario.pk})
        response = self.client.post(url, {})
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse(self.url_name, kwargs={'pk': self.scenario.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_success_and_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            'name': 'Test Configuration',
            'scenario': self.scenario.pk,
            'feedstock': self.feedstock.pk,
            'geodataset': self.geodataset.pk,
            'algorithm': self.algorithm.pk,
        }
        response = self.client.post(reverse(self.url_name, kwargs={'pk': self.scenario.pk}), data, follow=True)
        ScenarioConfiguration.objects.get(scenario__id=self.scenario.pk)
        self.assertRedirects(response, reverse('scenario-detail', kwargs={'pk': self.scenario.pk}))


class ScenarioConfigurationDetailViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['view_scenario', 'view_scenarioconfiguration']
    url_name = 'scenario-detail'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.owner = User.objects.create_user(username='owner', password='password')
        cls.region = Region.objects.create(name='Test Region')
        cls.catchment = Catchment.objects.create(name='Test Catchment', region=cls.region, parent_region=cls.region)
        cls.private_scenario = Scenario.objects.create(
            name='Test Scenario',
            owner=cls.owner,
            region=cls.region,
            catchment=cls.catchment
        )
        cls.published_scenario = Scenario.objects.create(
            name='Test Scenario',
            owner=cls.owner,
            region=cls.region,
            catchment=cls.catchment,
            publication_status='published'
        )
        cls.feedstock = SampleSeries.objects.create(
            name='Test Feedstock',
            material=Material.objects.create(name='Test Material')
        )
        cls.geodataset = GeoDataset.objects.create(
            name='Test Dataset',
            region=cls.region
        )
        cls.algorithm = Algorithm.objects.create(
            name='Test Algorithm',
            geodataset=cls.geodataset
        )
        cls.private_configuration = ScenarioConfiguration.objects.create(
            owner=cls.owner,
            scenario=cls.private_scenario,
            feedstock=cls.feedstock,
            geodataset=cls.geodataset,
            algorithm=cls.algorithm
        )
        cls.published_configuration = ScenarioConfiguration.objects.create(
            owner=cls.owner,
            scenario=cls.published_scenario,
            feedstock=cls.feedstock,
            geodataset=cls.geodataset,
            algorithm=cls.algorithm
        )

    def test_get_http_302_redirect_to_login_for_anonymous_accessing_private_scenario(self):
        url = reverse(self.url_name, kwargs={'pk': self.private_scenario.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders_accessing_private_scenario(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse(self.url_name, kwargs={'pk': self.private_scenario.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_owner_accessing_private_scenario(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse(self.url_name, kwargs={'pk': self.private_scenario.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_members_accessing_private_scenario(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse(self.url_name, kwargs={'pk': self.private_scenario.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_anonymous_accessing_published_scenario(self):
        response = self.client.get(reverse(self.url_name, kwargs={'pk': self.published_scenario.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_outsiders_accessing_published_scenario(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse(self.url_name, kwargs={'pk': self.published_scenario.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_owner_accessing_published_scenario(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse(self.url_name, kwargs={'pk': self.published_scenario.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_members_accessing_published_scenario(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse(self.url_name, kwargs={'pk': self.published_scenario.pk}))
        self.assertEqual(response.status_code, 200)


class ScenarioConfigurationUpdateViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['view_scenario', 'view_scenarioconfiguration', 'change_scenarioconfiguration']
    url_name = 'scenarioconfiguration-update'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.owner = User.objects.create_user(username='owner', password='password')
        cls.region = Region.objects.create(name='Test Region')
        cls.catchment = Catchment.objects.create(name='Test Catchment', region=cls.region, parent_region=cls.region)
        cls.scenario = Scenario.objects.create(
            name='Test Scenario',
            owner=cls.owner,
            region=cls.region,
            catchment=cls.catchment
        )
        cls.feedstock = SampleSeries.objects.create(
            name='Test Feedstock',
            material=Material.objects.create(name='Test Material')
        )
        cls.geodataset = GeoDataset.objects.create(
            name='Test Dataset',
            region=cls.region
        )
        cls.algorithm = Algorithm.objects.create(
            name='Test Algorithm',
            geodataset=cls.geodataset
        )
        cls.parameter = Parameter.objects.create(
            name='Test Parameter',
            algorithm=cls.algorithm
        )
        cls.value = ParameterValue.objects.create(parameter=cls.parameter, value=123.0)
        cls.parameter.default_value = cls.value
        cls.parameter.save()
        cls.configuration = ScenarioConfiguration.objects.create(
            owner=cls.owner,
            scenario=cls.scenario,
            feedstock=cls.feedstock,
            geodataset=cls.geodataset,
            algorithm=cls.algorithm
        )

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse(self.url_name, kwargs={'pk': self.configuration.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse(self.url_name, kwargs={'pk': self.configuration.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_owner(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse(self.url_name, kwargs={'pk': self.configuration.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse(self.url_name, kwargs={'pk': self.configuration.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse(self.url_name, kwargs={'pk': self.configuration.pk})
        response = self.client.post(url, {})
        self.assertRedirects(response, f'{reverse("auth_login")}?next={url}')

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse(self.url_name, kwargs={'pk': self.configuration.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_success_and_http_302_redirect_for_owner(self):
        self.client.force_login(self.owner)
        new_value = ParameterValue.objects.create(parameter=self.parameter, value=321.0)
        data = {
            'name': 'Updated Configuration',
            'scenario': self.scenario.pk,
            'feedstock': self.feedstock.pk,
            'geodataset': self.geodataset.pk,
            'algorithm': self.algorithm.pk,
            'scenarioparametersetting_set-INITIAL_FORMS': '1',
            'scenarioparametersetting_set-TOTAL_FORMS': '1',
            'scenarioparametersetting_set-0-scenario_configuration': self.configuration.pk,
            'scenarioparametersetting_set-0-id': self.configuration.scenarioparametersetting_set.first().pk,
            'scenarioparametersetting_set-0-parameter_value': new_value.pk,
        }
        response = self.client.post(reverse(self.url_name, kwargs={'pk': self.configuration.pk}), data)
        self.assertRedirects(response, reverse('scenario-detail', kwargs={'pk': self.scenario.pk}))

    def test_post_success_and_http_302_redirect_for_member(self):
        self.client.force_login(self.member)
        new_value = ParameterValue.objects.create(parameter=self.parameter, value=321.0)
        data = {
            'name': 'Updated Configuration',
            'scenario': self.scenario.pk,
            'feedstock': self.feedstock.pk,
            'geodataset': self.geodataset.pk,
            'algorithm': self.algorithm.pk,
            'scenarioparametersetting_set-INITIAL_FORMS': '1',
            'scenarioparametersetting_set-TOTAL_FORMS': '1',
            'scenarioparametersetting_set-0-scenario_configuration': self.configuration.pk,
            'scenarioparametersetting_set-0-id': self.configuration.scenarioparametersetting_set.first().pk,
            'scenarioparametersetting_set-0-parameter_value': new_value.pk,
        }
        response = self.client.post(reverse(self.url_name, kwargs={'pk': self.configuration.pk}), data)
        self.assertRedirects(response, reverse('scenario-detail', kwargs={'pk': self.scenario.pk}))


class ScenarioConfigurationModalDeleteViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ['view_scenario', 'view_scenarioconfiguration', 'delete_scenarioconfiguration']
    url_name = 'scenarioconfiguration-delete-modal'

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.owner = User.objects.create_user(username='owner', password='password')
        cls.region = Region.objects.create(name='Test Region')
        cls.catchment = Catchment.objects.create(name='Test Catchment', region=cls.region, parent_region=cls.region)
        cls.scenario = Scenario.objects.create(
            name='Test Scenario',
            owner=cls.owner,
            region=cls.region,
            catchment=cls.catchment
        )
        cls.feedstock = SampleSeries.objects.create(
            name='Test Feedstock',
            material=Material.objects.create(name='Test Material')
        )
        cls.geodataset = GeoDataset.objects.create(
            name='Test Dataset',
            region=cls.region
        )
        cls.algorithm = Algorithm.objects.create(
            name='Test Algorithm',
            geodataset=cls.geodataset
        )
        cls.configuration = ScenarioConfiguration.objects.create(
            owner=cls.owner,
            scenario=cls.scenario,
            feedstock=cls.feedstock,
            geodataset=cls.geodataset,
            algorithm=cls.algorithm
        )

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        url = reverse(self.url_name, kwargs={'pk': self.configuration.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse(self.url_name, kwargs={'pk': self.configuration.pk}))
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_owner(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse(self.url_name, kwargs={'pk': self.configuration.pk}))
        self.assertEqual(response.status_code, 200)

    def test_get_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse(self.url_name, kwargs={'pk': self.configuration.pk}))
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_to_login_for_anonymous(self):
        url = reverse(self.url_name, kwargs={'pk': self.configuration.pk})
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(reverse(self.url_name, kwargs={'pk': self.configuration.pk}))
        self.assertEqual(response.status_code, 403)

    def test_post_successful_delete_and_http_302_and_for_owner(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse(self.url_name, kwargs={'pk': self.configuration.pk}))
        self.assertRedirects(response, reverse('scenario-detail', kwargs={'pk': self.scenario.pk}))
        with self.assertRaises(ScenarioConfiguration.DoesNotExist):
            ScenarioConfiguration.objects.get(pk=self.configuration.pk)

    def test_post_successful_delete_and_http_302_and_for_member(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse(self.url_name, kwargs={'pk': self.configuration.pk}))
        self.assertRedirects(response, reverse('scenario-detail', kwargs={'pk': self.scenario.pk}))
        with self.assertRaises(ScenarioConfiguration.DoesNotExist):
            ScenarioConfiguration.objects.get(pk=self.configuration.pk)
